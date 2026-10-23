# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""A/B diagnostic of one cell of a release gate (suites/m2-mysql-ab.toml).

    python3 analysis/ab.py RUN_DIR --baseline vericto-enforce-4143 \\
        --candidate vericto-enforce-4150-off [--ab-curve ab-my-w3-05] \\
        [--swap-curve swap-my-w3-05] [--out DIR]

Uses the cells report.py uses (same validity selection).

- A/B curve: for every rate, the paired difference candidate minus baseline per
  repetition (both releases next to each other at that rate), per percentile,
  of the proxy's CPU per transaction (vCPU-µs per achieved transaction) and of
  its CFS throttled time per second, each with a Student t 95% interval. Also
  split by which release ran first, and the per-repetition values.
- Swap curve (each release twice back to back, AABB then BBAA, through alias
  variants "<name>-2nd"): per block, the release difference (mean of the
  candidate's two cells minus the baseline's two) and the position difference
  (second back-to-back run minus first, same release).

Writes ab.md and ab.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R  # noqa: E402

METRICS = ("p50", "p99", "p999", "cpu_us_per_tx", "throttled_ms_per_s")


def target_cpu(c: dict) -> dict:
    cont = ((c.get("cpu") or {}).get("containers") or {})
    return cont.get("target") or {}


def metric(c: dict, m: str) -> float | None:
    if m in R.PCTS:
        return R.pct(c, m)
    t = target_cpu(c)
    if m == "cpu_us_per_tx":
        rate = c.get("achieved_rate") or 0
        return t["vcpu"] / rate * 1e6 if t.get("vcpu") and rate > 0 else None
    if m == "throttled_ms_per_s":
        return t["throttled_ms"] / t["seconds"] if t.get("seconds") else None
    return None


def stat(xs: list[float]) -> dict:
    m, lo, hi = R.mean_ci(xs)
    return {"mean": m, "lo": lo, "hi": hi, "n": len(xs),
            "excludes_0": None if lo is None else not (lo <= 0 <= hi)}


def ab(used: list[dict], curve: str, base: str, cand: str) -> list[dict]:
    ok = [c for c in used if c.get("curve") == curve and c.get("status") == "ok"]
    by = {(c["offered_rate"], c["rep"], c["target"]): c for c in ok}
    rows = []
    for rate in sorted({c["offered_rate"] for c in ok}):
        pct = next(c.get("rate_pct") for c in ok if c["offered_rate"] == rate)
        diffs = {m: [] for m in METRICS}
        first = {base: {m: [] for m in METRICS}, cand: {m: [] for m in METRICS}}
        level = {base: {m: [] for m in METRICS}, cand: {m: [] for m in METRICS}}
        reps = []
        for rep in sorted({c["rep"] for c in ok if c["offered_rate"] == rate}):
            a, b = by.get((rate, rep, base)), by.get((rate, rep, cand))
            if not (a and b):
                continue
            who_first = base if a["seq"] < b["seq"] else cand
            r = {"rep": rep, "first": who_first}
            for m in METRICS:
                va, vb = metric(a, m), metric(b, m)
                for t, v in ((base, va), (cand, vb)):
                    if v is not None:
                        level[t][m].append(v)
                if va is None or vb is None:
                    continue
                diffs[m].append(vb - va)
                first[who_first][m].append(vb - va)
                r[m] = {"base": va, "cand": vb, "diff": vb - va}
            reps.append(r)
        rows.append({
            "offered_rate": rate, "rate_pct": pct, "n_pairs": len(diffs["p50"]),
            "diff": {m: stat(v) for m, v in diffs.items()},
            "level": {t: {m: stat(v) for m, v in d.items()} for t, d in level.items()},
            "diff_by_first": {t: {m: stat(v) for m, v in d.items()} for t, d in first.items()},
            "reps": reps,
        })
    return rows


def swap(used: list[dict], curve: str, base: str, cand: str) -> dict:
    ok = sorted((c for c in used if c.get("curve") == curve and c.get("status") == "ok"), key=lambda c: c["seq"])
    release = {base: base, f"{base}-2nd": base, cand: cand, f"{cand}-2nd": cand}
    blocks = []
    for rep in sorted({c["rep"] for c in ok}):
        cells = [c for c in ok if c["rep"] == rep and c["target"] in release]
        seq = [(release[c["target"]], c) for c in cells]
        out = {"rep": rep, "order": [c["target"] for c in cells], "cells": [], "release_diff": {}, "position_diff": {}}
        for rel, c in seq:
            out["cells"].append({"target": c["target"], "release": rel, "seq": c["seq"],
                                 **{m: metric(c, m) for m in METRICS}})
        for m in METRICS:
            va = [metric(c, m) for r, c in seq if r == base]
            vb = [metric(c, m) for r, c in seq if r == cand]
            if len(va) == 2 and len(vb) == 2 and None not in va + vb:
                out["release_diff"][m] = sum(vb) / 2 - sum(va) / 2
                out["position_diff"][m] = {base: va[1] - va[0], cand: vb[1] - vb[0]}
        blocks.append(out)
    pooled = {m: stat([b["release_diff"][m] for b in blocks if m in b["release_diff"]]) for m in METRICS}
    pos = {m: stat([v for b in blocks if m in b["position_diff"] for v in b["position_diff"][m].values()])
           for m in METRICS}
    return {"blocks": blocks, "release_diff": pooled, "position_diff": pos}


def f(x, d=3) -> str:
    return "n/a" if x is None else f"{x:+.{d}f}"


def s(st: dict, d=3) -> str:
    if st["mean"] is None:
        return "n/a"
    if st["lo"] is None:
        return f"{f(st['mean'], d)} (n={st['n']})"
    return f"{f(st['mean'], d)} [{st['lo']:+.{d}f}, {st['hi']:+.{d}f}]"


def markdown(res: dict, names: dict) -> str:
    b, c = res["baseline"], res["candidate"]
    md = [f"# A/B: {names.get(c, c)} minus {names.get(b, b)}", "",
          "Paired per repetition; means with Student t 95% intervals. Latency per transaction in ms; "
          "CPU in vCPU-µs per achieved transaction; throttled = the proxy's CFS throttled ms per second.", "",
          "## Paired differences", "",
          "| Rate (% of S) | n | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["ab"]:
        d = r["diff"]
        md.append(f"| {r['offered_rate']:g} ({r['rate_pct']:g}%) | {r['n_pairs']} | {s(d['p50'])} | {s(d['p99'])} "
                  f"| {s(d['p999'])} | {s(d['cpu_us_per_tx'], 1)} | {s(d['throttled_ms_per_s'], 2)} |")
    md += ["", "## Levels (mean over repetitions)", "",
           "| Rate | Release | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["ab"]:
        for t in (b, c):
            lv = r["level"][t]
            md.append(f"| {r['offered_rate']:g} | {names.get(t, t)} | " + " | ".join(
                "n/a" if lv[m]["mean"] is None else f"{lv[m]['mean']:.3f}" for m in METRICS) + " |")
    md += ["", "## Paired difference by which release ran first", "",
           "| Rate | First | n | p50 | p99 | CPU µs/tx |", "| --- | --- | --- | --- | --- | --- |"]
    for r in res["ab"]:
        for t in (b, c):
            d = r["diff_by_first"][t]
            md.append(f"| {r['offered_rate']:g} | {names.get(t, t)} | {d['p50']['n']} | {s(d['p50'])} | {s(d['p99'])} "
                      f"| {s(d['cpu_us_per_tx'], 1)} |")
    md += ["", "## Per repetition (diff, ms)", "", "| Rate | Rep | First | p50 | p99 | p99.9 | CPU µs/tx |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["ab"]:
        for x in r["reps"]:
            md.append(f"| {r['offered_rate']:g} | {x['rep']} | {names.get(x['first'], x['first'])} | "
                      + " | ".join(f(x[m]["diff"], 1 if m == "cpu_us_per_tx" else 3) if m in x else "n/a"
                                   for m in ("p50", "p99", "p999", "cpu_us_per_tx")) + " |")
    sw = res.get("swap")
    if sw:
        md += ["", "## Back-to-back control (each release twice in a row, then the mirror order)", ""]
        for blk in sw["blocks"]:
            md += [f"Block {blk['rep']}: " + ", ".join(blk["order"]), "",
                   "| Seq | Target | p50 | p99 | p99.9 | CPU µs/tx |", "| --- | --- | --- | --- | --- | --- |"]
            for x in blk["cells"]:
                md.append(f"| {x['seq']} | {x['target']} | " + " | ".join(
                    "n/a" if x[m] is None else f"{x[m]:.3f}" for m in ("p50", "p99", "p999", "cpu_us_per_tx")) + " |")
            md.append("")
        md += ["| Measure | p50 | p99 | p99.9 | CPU µs/tx |", "| --- | --- | --- | --- | --- |",
               "| Release diff (candidate minus baseline), per block mean | "
               + " | ".join(s(sw["release_diff"][m], 1 if m == "cpu_us_per_tx" else 3) for m in ("p50", "p99", "p999", "cpu_us_per_tx")) + " |",
               "| Position diff (second run minus first, same release) | "
               + " | ".join(s(sw["position_diff"][m], 1 if m == "cpu_us_per_tx" else 3) for m in ("p50", "p99", "p999", "cpu_us_per_tx")) + " |"]
    return "\n".join(md) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--ab-curve", default="ab-my-w3-05")
    ap.add_argument("--swap-curve", default="swap-my-w3-05")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    man, cells = R.load_run(a.run)
    names = {n: v.get("label") or n for n, v in (man.get("proxy_variants") or {}).items()}
    used, invalid = R.select(cells)
    res = {"baseline": a.baseline, "candidate": a.candidate, "saturation": man.get("saturation"),
           "cells_used": len(used), "cells_invalid": [c.get("cell") for c in invalid],
           "ab": ab(used, a.ab_curve, a.baseline, a.candidate),
           "swap": swap(used, a.swap_curve, a.baseline, a.candidate)}
    out = a.out or os.path.join(a.run, "report")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "ab.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    with open(os.path.join(out, "ab.md"), "w") as fh:
        fh.write(markdown(res, names))
    print(f"ab: {os.path.join(out, 'ab.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
