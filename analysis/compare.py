# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Paired comparison of two vericto targets of one run (a release gate).

    python3 analysis/compare.py RUN_DIR --baseline vericto-enforce-4143 \\
        --candidate vericto-enforce-4150-off [--extra vericto-enforce-4150-observe] \\
        [--gate-below 70] [--out DIR]

Uses the cells report.py uses (same validity selection). For every open-loop
curve and offered rate:

- the added latency of each target against `direct` (paired per repetition;
  mean and Student t 95% interval), as in report.py;
- the paired difference candidate minus baseline per repetition (both run at
  the same rate in the same repetition, next to each other in the Williams
  order), per percentile, with its Student t 95% interval;
- the proxy's vCPU per 1,000 achieved statements/s of each target, and its
  paired difference.

Gate, per cell below --gate-below % of S (cells at absolute rates count as
below): for each of p50, p99 and p99.9, the two targets' 95% intervals of added
latency overlap, or the paired difference's interval contains 0. The gate
passes if every such cell passes. Writes compare.md and compare.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R  # noqa: E402


def vcpu(c: dict) -> float:
    cont = ((c.get("cpu") or {}).get("containers") or {})
    return sum(x["vcpu"] for k, x in cont.items() if k.startswith("target"))


def kqps(c: dict) -> float:
    return (c.get("statements_per_s") or c.get("achieved_rate") or 0) / 1000.0


def overlap(a, b) -> bool | None:
    if a[0] is None or b[0] is None:
        return None
    return a[0] <= b[1] and b[0] <= a[1]


def compare(used: list[dict], base: str, cand: str, gate_below: float) -> dict:
    ok = [c for c in used if c.get("loop") == "open" and c.get("status") == "ok"]
    by = {(c["curve"], c["offered_rate"], c["rep"], c["target"]): c for c in ok}
    drows = {(r["curve"], r["target"], r["offered_rate"]): r for r in R.deltas(used)}
    cells = sorted({(c["curve"], c["offered_rate"], c.get("rate_pct")) for c in ok if c["target"] in (base, cand)},
                   key=lambda x: (x[0], x[1]))
    rows = []
    for curve, rate, pct in cells:
        reps = sorted({c["rep"] for c in ok if c["curve"] == curve and c["offered_rate"] == rate})
        diffs = {p: [] for p in R.PCTS}
        cpu = {base: [], cand: []}
        cpu_diff = []
        for rep in reps:
            a, b = by.get((curve, rate, rep, base)), by.get((curve, rate, rep, cand))
            for t, x in ((base, a), (cand, b)):
                if x and vcpu(x) > 0 and kqps(x) > 0:
                    cpu[t].append(vcpu(x) / kqps(x))
            if not (a and b):
                continue
            for p in R.PCTS:
                va, vb = R.pct(a, p), R.pct(b, p)
                if va is not None and vb is not None:
                    diffs[p].append(vb - va)
            if vcpu(a) > 0 and vcpu(b) > 0 and kqps(a) > 0 and kqps(b) > 0:
                cpu_diff.append(vcpu(b) / kqps(b) - vcpu(a) / kqps(a))
        row = {"curve": curve, "offered_rate": rate, "rate_pct": pct, "n_pairs": len(diffs["p50"]),
               "gated": pct is None or pct < gate_below, "checks": {}}
        cell_pass = True
        for p in R.PCTS:
            da, dc = drows.get((curve, base, rate)), drows.get((curve, cand, rate))
            ia = (da[f"added_{p}_lo"], da[f"added_{p}_hi"]) if da else (None, None)
            ic = (dc[f"added_{p}_lo"], dc[f"added_{p}_hi"]) if dc else (None, None)
            m, lo, hi = R.mean_ci(diffs[p])
            ov = overlap(ia, ic)
            zero = (lo <= 0 <= hi) if lo is not None else None
            passed = bool(ov) or bool(zero)
            row["checks"][p] = {
                "base_added": da[f"added_{p}_ms"] if da else None, "base_ci": ia,
                "cand_added": dc[f"added_{p}_ms"] if dc else None, "cand_ci": ic,
                "diff": m, "diff_ci": (lo, hi), "intervals_overlap": ov, "diff_ci_contains_0": zero, "pass": passed}
            cell_pass = cell_pass and passed
        cm = {t: R.mean_ci(v) for t, v in cpu.items()}
        row["vcpu_per_kqps"] = {t: {"mean": v[0], "lo": v[1], "hi": v[2], "n": len(cpu[t])} for t, v in cm.items()}
        dm = R.mean_ci(cpu_diff)
        row["vcpu_per_kqps_diff"] = {"mean": dm[0], "lo": dm[1], "hi": dm[2], "n": len(cpu_diff)}
        row["pass"] = cell_pass
        rows.append(row)
    gated = [r for r in rows if r["gated"]]
    return {"baseline": base, "candidate": cand, "gate_below_pct_of_S": gate_below, "cells": rows,
            "gate_pass": bool(gated) and all(r["pass"] for r in gated) and all(r["n_pairs"] >= 2 for r in gated),
            "failing_cells": [f"{r['curve']}@{r['offered_rate']:g}" for r in gated if not r["pass"]]}


def saturation(used: list[dict]) -> dict:
    out: dict = {}
    for c in used:
        if c.get("loop") != "closed":
            continue
        v = c.get("statements_per_s") or c.get("achieved_rate") or 0
        k = f"{c['curve']}|{c['target']}"
        out[k] = max(out.get(k, 0), v)
    return out


def f3(x, d=3) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def ci(lo, hi, d=3) -> str:
    return "n/a" if lo is None else f"[{lo:.{d}f}, {hi:.{d}f}]"


def markdown(res: dict, extra: list[dict], fits: list[dict], sat: dict, names: dict) -> str:
    b, c = res["baseline"], res["candidate"]
    md = [f"# Paired comparison: {names.get(c, c)} against {names.get(b, b)}", "",
          f"Gate (cells below {res['gate_below_pct_of_S']:g}% of S; absolute-rate cells included): "
          f"**{'PASS' if res['gate_pass'] else 'FAIL'}**"
          + (f"; failing: {', '.join(res['failing_cells'])}" if res["failing_cells"] else ""), "",
          "Added = target minus direct, paired per repetition. Diff = candidate minus baseline, paired per repetition. "
          "Means with Student t 95% intervals; ms.", ""]
    md += ["| Curve | Rate (% of S) | n | pct | Added baseline [95%] | Added candidate [95%] | Diff [95%] | Overlap | 0 in diff | Gated | Pass |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["cells"]:
        for p in R.PCTS:
            k = r["checks"][p]
            where = "absolute" if r["rate_pct"] is None else f"{r['rate_pct']:g}%"
            md.append(f"| {r['curve']} | {r['offered_rate']:g} ({where}) "
                      f"| {r['n_pairs']} | {p} | {f3(k['base_added'])} {ci(*k['base_ci'])} | {f3(k['cand_added'])} {ci(*k['cand_ci'])} "
                      f"| {f3(k['diff'])} {ci(*k['diff_ci'])} | {k['intervals_overlap']} | {k['diff_ci_contains_0']} "
                      f"| {'yes' if r['gated'] else 'no'} | {'yes' if k['pass'] else 'NO'} |")
    md += ["", "## Proxy vCPU per 1,000 statements/s (per cell, mean over repetitions)", "",
           "| Curve | Rate | Baseline [95%] | Candidate [95%] | Paired diff [95%] |", "| --- | --- | --- | --- | --- |"]
    for r in res["cells"]:
        v = r["vcpu_per_kqps"]
        d = r["vcpu_per_kqps_diff"]
        md.append(f"| {r['curve']} | {r['offered_rate']:g} | {f3(v[b]['mean'], 4)} {ci(v[b]['lo'], v[b]['hi'], 4)} "
                  f"| {f3(v[c]['mean'], 4)} {ci(v[c]['lo'], v[c]['hi'], 4)} | {f3(d['mean'], 4)} {ci(d['lo'], d['hi'], 4)} |")
    md += ["", "## CPU fit (vCPU against achieved kQPS, open-loop cells below 80% of S)", "",
           "| Curve | Target | n | vCPU per 1,000 QPS [95%] | Intercept vCPU |", "| --- | --- | --- | --- | --- |"]
    for f in fits:
        if "slope" in f:
            md.append(f"| {f['curve']} | {names.get(f['target'], f['target'])} | {f['n']} | {f['slope']:.4f} "
                      f"[{f['slope_lo']:.4f}, {f['slope_hi']:.4f}] | {f['intercept']:.4f} |")
    for e in extra:
        md += ["", f"## Informational: {names.get(e['candidate'], e['candidate'])} against {names.get(b, b)}", "",
               "| Curve | Rate | n | Diff p50 [95%] | Diff p99 [95%] | Diff p99.9 [95%] | Diff vCPU/kQPS [95%] |",
               "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in e["cells"]:
            k = r["checks"]
            d = r["vcpu_per_kqps_diff"]
            md.append(f"| {r['curve']} | {r['offered_rate']:g} | {r['n_pairs']} | "
                      + " | ".join(f"{f3(k[p]['diff'])} {ci(*k[p]['diff_ci'])}" for p in R.PCTS)
                      + f" | {f3(d['mean'], 4)} {ci(d['lo'], d['hi'], 4)} |")
    md += ["", "## Closed-loop maximum throughput (statements/s; 1 repetition)", "", "| Curve | Target | Max |", "| --- | --- | --- |"]
    for k, v in sorted(sat.items()):
        curve, t = k.split("|")
        md.append(f"| {curve} | {names.get(t, t)} | {v:,.0f} |")
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--extra", action="append", default=[], help="further candidates, informational")
    ap.add_argument("--gate-below", type=float, default=70.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    cells, names = [], {}
    for r in a.runs:
        m, cs = R.load_run(r)
        cells += cs
        names.update({n: v.get("label") or n for n, v in (m.get("proxy_variants") or {}).items()})
    used, _ = R.select(cells)
    res = compare(used, a.baseline, a.candidate, a.gate_below)
    extra = [compare(used, a.baseline, e, a.gate_below) for e in a.extra]
    fits = [f for f in R.cpu_fits(used, {}) if f["target"] in (a.baseline, a.candidate, *a.extra)]
    sat = saturation(used)
    out = a.out or os.path.join(a.runs[0], "report")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "compare.json"), "w") as f:
        json.dump({"gate": res, "extra": extra, "cpu_fits": fits, "closed_loop_max": sat}, f, indent=2, default=str)
    with open(os.path.join(out, "compare.md"), "w") as f:
        f.write(markdown(res, extra, fits, sat, names))
    print(f"compare: gate {'PASS' if res['gate_pass'] else 'FAIL'} ({os.path.join(out, 'compare.md')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
