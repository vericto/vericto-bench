# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""vericto-bench report generator (pre-registered analysis, design section 8).

    python3 analysis/report.py RUN_DIR [RUN_DIR ...] [--out DIR] [--publishable]

Reads each run's manifest.json and cells.jsonl and writes, into --out (default
RUN_DIR/report): report.md, report.html, cells.csv, deltas.csv, cpu_fit.csv,
traffic.csv, summary.json and charts/*.png.

Rules, fixed before any run:
- latency only from open-loop cells with status ok; saturated cells end a
  curve and are never quoted as latency; closed-loop figures are throughput;
- added latency = target minus direct at the same rate in the same repetition
  (paired), per percentile; across repetitions the mean with a Student t 95%
  interval; an interval containing zero reads "not distinguishable";
- per-cell percentile intervals by block bootstrap over the histogram intervals;
- no outlier removal: invalid repetitions (pre-registered rules, applied by the
  runner) are listed and excluded; a valid rerun replaces its original;
- cost per 1,000 QPS: linear fit of the proxy container's vCPU against achieved
  statements/s over the open-loop cells below 80% of S.

--publishable refuses any run whose manifest says profile=smoke (exit 2), and any
run whose profile is not "published". Smoke reports carry the banner
"SMOKE RUN: NOT FOR PUBLISHED NUMBERS" in the report, every chart and every CSV.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import random
import statistics
import sys

SMOKE = "SMOKE RUN: NOT FOR PUBLISHED NUMBERS"
FARGATE_ARM_VCPU_HOUR = 0.03238  # USD, us-east-1 list price (design section 8)
# Fixed hue per target (validated categorical palette, slots 1-6, light mode);
# colour follows the target, never its rank. Markers are the secondary encoding.
TARGET_STYLE = {
    "direct": ("#2a78d6", "o"), "haproxy-tcp": ("#eb6834", "s"), "pgbouncer-session": ("#1baf7a", "^"),
    "proxysql": ("#1baf7a", "^"), "vericto-offline": ("#eda100", "D"), "vericto-enforce": ("#e87ba4", "v"),
    "vericto-observe": ("#008300", "P"),
}
TARGET_ORDER = list(TARGET_STYLE)
T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
        2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]
PCTS = ("p50", "p99", "p999")


def t975(df: int) -> float:
    return T975[df - 1] if 1 <= df <= len(T975) else 1.96


def mean_ci(xs: list[float]) -> tuple[float, float | None, float | None]:
    if not xs:
        return math.nan, None, None
    m = statistics.mean(xs)
    if len(xs) < 2:
        return m, None, None
    h = t975(len(xs) - 1) * statistics.stdev(xs) / math.sqrt(len(xs))
    return m, m - h, m + h


def verdict(lo, hi) -> str:
    if lo is None:
        return "n=1, no interval"
    if lo <= 0 <= hi:
        return "not distinguishable from the direct path"
    return ""


# ---- loading -----------------------------------------------------------------------

def load_run(path: str) -> tuple[dict, list[dict]]:
    with open(os.path.join(path, "manifest.json")) as f:
        man = json.load(f)
    cells = []
    cp = os.path.join(path, "cells.jsonl")
    if not os.path.exists(cp):
        open(cp, "a").close()  # a run that failed in setup has no cells; the report says so
    with open(cp) as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                c["_run"] = path
                c["_profile"] = man.get("profile")
                cells.append(c)
    return man, cells


def key(c: dict) -> tuple:
    return (c.get("_run"), c.get("curve"), c.get("target"), c.get("offered_rate"), c.get("conc"), c.get("rep"), c.get("day"))


def select(cells: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cells used by the analysis, and the invalid ones (listed, not used). A
    valid rerun replaces its invalid original; the original stays in the raw data."""
    used, invalid = {}, []
    for c in cells:
        if c.get("status") == "not_run" or str(c.get("cell", "")).endswith(".netprobe"):
            continue
        if c.get("invalid_reasons"):
            invalid.append(c)
            continue
        used[key(c)] = c
    return list(used.values()), invalid


def merge_buckets(rows: list[list]) -> dict[int, int]:
    out: dict[int, int] = {}
    for r in rows:
        for v, k in r or []:
            out[v] = out.get(v, 0) + k
    return out


def quantile(counts: dict[int, int], q: float) -> float:
    n = sum(counts.values())
    if not n:
        return math.nan
    rank = max(1, math.ceil(q * n))
    acc = 0
    for v in sorted(counts):
        acc += counts[v]
        if acc >= rank:
            return v / 1000.0
    return max(counts) / 1000.0


def intervals(c: dict) -> list[list]:
    p = c.get("intervals")
    if not p:
        return []
    try:
        with open(os.path.join(c["_run"], p)) as f:
            return [json.loads(l)["buckets_us"] or [] for l in f if l.strip()]
    except FileNotFoundError:
        return []


def bootstrap(c: dict, B: int = 400, seed: int = 1) -> dict:
    """Block bootstrap over the cell's histogram intervals: 95% interval of each
    percentile. Fewer than 3 intervals: no interval."""
    iv = [x for x in intervals(c) if x]
    if len(iv) < 3:
        return {}
    rng = random.Random(seed)
    qs = {"p50": 0.5, "p99": 0.99, "p999": 0.999}
    samples = {k: [] for k in qs}
    for _ in range(B):
        m = merge_buckets([iv[rng.randrange(len(iv))] for _ in iv])
        for k, q in qs.items():
            samples[k].append(quantile(m, q))
    out = {}
    for k, xs in samples.items():
        xs.sort()
        out[k] = (xs[int(0.025 * B)], xs[int(0.975 * B) - 1])
    return out


def pct(c: dict, p: str) -> float | None:
    lat = c.get("latency") or {}
    return lat.get(f"{p}_ms")


# ---- analysis ----------------------------------------------------------------------

def deltas(used: list[dict]) -> list[dict]:
    """Paired deltas: target minus direct, same curve, rate, repetition and day."""
    open_ok = [c for c in used if c.get("loop") == "open" and c.get("status") == "ok"]
    direct = {(c["_run"], c["curve"], c["offered_rate"], c["rep"], c.get("day")): c for c in open_ok if c["target"] == "direct"}
    groups: dict[tuple, dict[str, list[float]]] = {}
    for c in open_ok:
        if c["target"] == "direct":
            continue
        d = direct.get((c["_run"], c["curve"], c["offered_rate"], c["rep"], c.get("day")))
        if not d:
            continue
        g = groups.setdefault((c["curve"], c["engine"], c["target"], c["offered_rate"], c.get("rate_pct")), {p: [] for p in PCTS})
        for p in PCTS:
            a, b = pct(c, p), pct(d, p)
            if a is not None and b is not None:
                g[p].append(a - b)
    rows = []
    for (curve, engine, target, rate, rpct), g in sorted(groups.items(), key=lambda x: (x[0][0], x[0][2], x[0][3])):
        row = {"curve": curve, "engine": engine, "target": target, "offered_rate": rate, "rate_pct": rpct, "n": len(g["p50"])}
        for p in PCTS:
            m, lo, hi = mean_ci(g[p])
            row[f"added_{p}_ms"], row[f"added_{p}_lo"], row[f"added_{p}_hi"] = m, lo, hi
            row[f"{p}_note"] = verdict(lo, hi)
        rows.append(row)
    return rows


def ols(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    if n < 3:
        return {"n": n}
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return {"n": n}
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in res) / (n - 2)
    se_b = math.sqrt(s2 / sxx)
    se_a = math.sqrt(s2 * (1 / n + mx * mx / sxx))
    t = t975(n - 2)
    return {"n": n, "slope": b, "slope_lo": b - t * se_b, "slope_hi": b + t * se_b, "intercept": a,
            "intercept_lo": a - t * se_a, "intercept_hi": a + t * se_a}


def cpu_fits(used: list[dict], saturation: dict[str, float]) -> list[dict]:
    pts: dict[tuple, list[tuple[float, float]]] = {}
    for c in used:
        if c.get("loop") != "open" or c.get("status") != "ok" or not str(c.get("target", "")).startswith("vericto"):
            continue
        if c.get("rate_pct") is not None and c["rate_pct"] >= 80:
            continue
        cont = ((c.get("cpu") or {}).get("containers") or {})
        v = sum(x["vcpu"] for k, x in cont.items() if k.startswith("target"))
        qps = c.get("statements_per_s") or c.get("achieved_rate") or 0
        if v > 0 and qps > 0:
            pts.setdefault((c["curve"], c["engine"], c["target"], c.get("size")), []).append((qps / 1000.0, v))
    rows = []
    for (curve, engine, target, size), p in sorted(pts.items()):
        f = ols([x for x, _ in p], [y for _, y in p])
        row = {"curve": curve, "engine": engine, "target": target, "size": size, **f}
        if "slope" in f:
            row["usd_per_month_per_1000qps_at_100pct"] = f["slope"] * FARGATE_ARM_VCPU_HOUR * 730
            row["usd_per_month_per_1000qps_at_70pct"] = row["usd_per_month_per_1000qps_at_100pct"] / 0.7
            row["usd_per_month_per_1000qps_at_50pct"] = row["usd_per_month_per_1000qps_at_100pct"] / 0.5
        rows.append(row)
    return rows


def traffic_rows(cells: list[dict]) -> list[dict]:
    rows = []
    for c in cells:
        net = c.get("net") or {}
        if not net:
            continue
        rows.append({"cell": c.get("cell"), "target": c.get("target"), "offered_rate": c.get("offered_rate"),
                     "max_aggregate_mbps": net.get("max_aggregate_mbps"),
                     **{f"max_{k}_mbps": v for k, v in (net.get("max_mbps") or {}).items()},
                     "warned": ",".join(net.get("warned") or []), "aborted_by_cap": bool(c.get("net_aborted"))})
    return rows


# ---- charts ------------------------------------------------------------------------

def charts(out: str, used: list[dict], drows: list[dict], fits: list[dict], smoke: bool) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    os.makedirs(os.path.join(out, "charts"), exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e",
                         "ytick.color": "#52514e", "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6,
                         "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                         "axes.facecolor": "#fcfcfb", "lines.linewidth": 2, "lines.markersize": 6})
    files = []

    def finish(fig, name, title):
        fig.suptitle(title, fontsize=10, color="#0b0b0b")
        if smoke:
            fig.text(0.5, 0.5, SMOKE, ha="center", va="center", fontsize=16, color="#d03b3b", alpha=0.25, rotation=20)
            fig.text(0.01, 0.01, SMOKE, fontsize=8, color="#d03b3b")
        fig.tight_layout(rect=(0, 0.03, 1, 0.95))
        p = os.path.join(out, "charts", name)
        fig.savefig(p, dpi=130)
        plt.close(fig)
        files.append(os.path.relpath(p, out))

    # Added latency against offered rate, one panel per percentile.
    for curve in sorted({r["curve"] for r in drows}):
        rs = [r for r in drows if r["curve"] == curve]
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharex=True)
        for ax, p in zip(axes, PCTS):
            for t in [x for x in TARGET_ORDER if any(r["target"] == x for r in rs)]:
                pts = sorted((r["offered_rate"], r[f"added_{p}_ms"], r[f"added_{p}_lo"], r[f"added_{p}_hi"]) for r in rs if r["target"] == t)
                col, mk = TARGET_STYLE[t]
                xs = [x[0] for x in pts]
                ys = [x[1] for x in pts]
                err = [[(y - lo) if lo is not None else 0 for _, y, lo, _ in pts], [(hi - y) if hi is not None else 0 for _, y, _, hi in pts]]
                ax.errorbar(xs, ys, yerr=err, color=col, marker=mk, capsize=3, label=t)
            ax.axhline(0, color="#52514e", linewidth=0.8)
            ax.set_title(f"added {p}", fontsize=9)
            ax.set_xlabel("offered rate (requests/s)")
        axes[0].set_ylabel("ms over the direct path")
        axes[-1].legend(fontsize=7, frameon=False)
        finish(fig, f"added-latency-{curve}.png", f"{curve}: added latency vs offered rate (95% intervals)")

    # Proxy CPU against achieved QPS with the fit.
    for f in fits:
        if "slope" not in f:
            continue
        pts = []
        for c in used:
            if c.get("curve") == f["curve"] and c.get("target") == f["target"] and c.get("loop") == "open" and c.get("status") == "ok":
                cont = ((c.get("cpu") or {}).get("containers") or {})
                v = sum(x["vcpu"] for k, x in cont.items() if k.startswith("target"))
                q = (c.get("statements_per_s") or c.get("achieved_rate") or 0) / 1000.0
                pts.append((q, v))
        fig, ax = plt.subplots(figsize=(5, 3.4))
        col, mk = TARGET_STYLE[f["target"]]
        ax.scatter([x for x, _ in pts], [y for _, y in pts], color=col, marker=mk, s=40, label=f["target"])
        xs = [0, max(x for x, _ in pts) * 1.05]
        ax.plot(xs, [f["intercept"] + f["slope"] * x for x in xs], color="#52514e", linewidth=1.2,
                label=f"fit: {f['slope']:.3f} vCPU per 1,000 QPS")
        ax.set_xlabel("achieved kQPS (statements/s / 1000)")
        ax.set_ylabel("proxy vCPU used")
        ax.legend(fontsize=7, frameon=False)
        finish(fig, f"cpu-{f['curve']}-{f['target']}.png", f"{f['curve']}: proxy CPU vs throughput ({f['size']} vCPU)")

    # Closed-loop throughput per target.
    closed = [c for c in used if c.get("loop") == "closed"]
    for curve in sorted({c["curve"] for c in closed}):
        cs = [c for c in closed if c["curve"] == curve]
        fig, ax = plt.subplots(figsize=(5.5, 3.4))
        for t in [x for x in TARGET_ORDER if any(c["target"] == x for c in cs)]:
            pts = {}
            for c in cs:
                if c["target"] == t:
                    pts.setdefault(c["conc"], []).append(c.get("statements_per_s") or c.get("achieved_rate") or 0)
            xs = sorted(pts)
            col, mk = TARGET_STYLE[t]
            ax.plot(xs, [statistics.mean(pts[x]) for x in xs], color=col, marker=mk, label=t)
        ax.set_xscale("log", base=2)
        ax.set_xlabel("concurrency (closed loop)")
        ax.set_ylabel("throughput (statements/s)")
        ax.legend(fontsize=7, frameon=False)
        finish(fig, f"throughput-{curve}.png", f"{curve}: closed-loop throughput (latency here is at saturation)")

    # Percentile spectrum of each open-loop cell of the first repetition, per curve.
    for curve in sorted({c["curve"] for c in used if c.get("loop") == "open"}):
        cs = [c for c in used if c["curve"] == curve and c.get("loop") == "open" and c.get("rep") == 1 and c.get("status") == "ok"]
        rates = sorted({c["offered_rate"] for c in cs})
        if not rates:
            continue
        rate = rates[len(rates) // 2]
        fig, ax = plt.subplots(figsize=(5.5, 3.4))
        qs = [0.5, 0.75, 0.9, 0.95, 0.99, 0.995, 0.999, 0.9999]
        drawn = False
        for t in TARGET_ORDER:
            c = next((x for x in cs if x["target"] == t and x["offered_rate"] == rate), None)
            if not c:
                continue
            m = merge_buckets(intervals(c))
            if not m:
                continue
            col, mk = TARGET_STYLE[t]
            ax.plot([1 / (1 - q) for q in qs], [quantile(m, q) for q in qs], color=col, marker=mk, label=t)
            drawn = True
        if not drawn:
            plt.close(fig)
            continue
        ax.set_xscale("log")
        ax.set_xticks([1 / (1 - q) for q in qs])
        ax.set_xticklabels([f"p{q * 100:g}" for q in qs], fontsize=7)
        ax.set_ylabel("latency from intended send (ms)")
        ax.legend(fontsize=7, frameon=False)
        finish(fig, f"spectrum-{curve}.png", f"{curve}: percentile spectrum at {rate:g} requests/s (rep 1)")
    return files


# ---- output ------------------------------------------------------------------------

def write_csv(path: str, rows: list[dict], smoke: bool):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys and not k.startswith("_"):
                keys.append(k)
    with open(path, "w", newline="") as f:
        if smoke:
            f.write(f"# {SMOKE}\n")
        w = csv.DictWriter(f, fieldnames=keys or ["empty"], extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})


def fmt(x, d=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.{d}f}" if isinstance(x, float) else str(x)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="")
    ap.add_argument("--publishable", action="store_true", help="refuse anything but profile=published runs")
    a = ap.parse_args(argv)
    mans, cells = [], []
    for r in a.runs:
        m, cs = load_run(r)
        mans.append(m)
        cells += cs
    profiles = {m.get("profile") for m in mans}
    smoke = "smoke" in profiles
    if a.publishable and (smoke or profiles != {"published"}):
        print(f"report: refusing a publishable report from profile(s) {sorted(p or '?' for p in profiles)}; "
              f"only profile=published runs can produce one", file=sys.stderr)
        return 2
    out = a.out or os.path.join(a.runs[0], "report")
    os.makedirs(out, exist_ok=True)
    used, invalid = select(cells)
    drows = deltas(used)
    sat = {}
    fits = cpu_fits(used, sat)
    traffic = traffic_rows(cells)
    for c in used:
        if c.get("loop") == "open" and c.get("status") == "ok" and c.get("intervals"):
            c["bootstrap"] = bootstrap(c)
    flat = []
    for c in cells:
        row = {k: c.get(k) for k in ("cell", "curve", "engine", "tool", "workload", "mode", "tls", "size", "target", "loop",
                                     "offered_rate", "rate_pct", "conc", "rep", "day", "status", "reason", "achieved_rate",
                                     "statements_per_s", "completed", "errors", "blocked", "unsent", "incomplete")}
        for p in ("p50", "p90", "p99", "p999", "max"):
            row[f"{p}_ms"] = pct(c, p)
        bs = c.get("bootstrap") or {}
        for p in PCTS:
            if p in bs:
                row[f"{p}_lo"], row[f"{p}_hi"] = bs[p]
        cont = ((c.get("cpu") or {}).get("containers") or {})
        row["proxy_vcpu"] = sum(x["vcpu"] for k, x in cont.items() if k.startswith("target")) or None
        row["load_vcpu"] = (cont.get("load") or {}).get("vcpu")
        net = c.get("net") or {}
        row["max_aggregate_mbps"] = net.get("max_aggregate_mbps")
        row["invalid_reasons"] = "; ".join(c.get("invalid_reasons") or [])
        flat.append(row)
    write_csv(os.path.join(out, "cells.csv"), flat, smoke)
    write_csv(os.path.join(out, "deltas.csv"), drows, smoke)
    write_csv(os.path.join(out, "cpu_fit.csv"), fits, smoke)
    write_csv(os.path.join(out, "traffic.csv"), traffic, smoke)
    files = charts(out, used, drows, fits, smoke)
    validation = [c for c in cells if c.get("validation")]
    summary = {"banner": SMOKE if smoke else None, "runs": [m.get("run_id") for m in mans], "profiles": sorted(p or "?" for p in profiles),
               "cells": len(cells), "used": len(used), "invalid": len(invalid), "deltas": drows, "cpu_fits": fits,
               "validation": [c["validation"] | {"cell": c["cell"]} for c in validation],
               "aborted_by_cap": [c["cell"] for c in cells if c.get("net_aborted")], "charts": files}
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    md = []
    if smoke:
        md += [f"# {SMOKE}", "", f"**{SMOKE}.** This report proves the pipeline only. No figure in it is a measurement "
               "of anything: it ran on one shared Docker host with no CPU isolation and seconds-long cells.", ""]
    md += [f"# vericto-bench report: {', '.join(str(m.get('suite')) for m in mans)}", "",
           "| Run | Profile | Topology | Proxy image | Harness commit | Started | Finished |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for m in mans:
        md.append(f"| {m.get('run_id')} | {m.get('profile')} | {m.get('topology')} | `{m.get('proxy_image')}` | "
                  f"`{str(m.get('harness_commit'))[:12]}` | {m.get('started_at')} | {m.get('finished_at')} |")
    md += ["", f"Cells: {len(cells)} recorded, {len(used)} used, {len(invalid)} invalid (listed at the end, not used).", ""]
    md += ["## Added latency (open loop, from intended send time; target minus direct, paired)", "",
           "| Curve | Target | Rate/s | % of S | n | added p50 ms [95%] | added p99 ms [95%] | added p99.9 ms [95%] | Note |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in drows:
        cells_ = []
        for p in PCTS:
            ci = f" [{fmt(r[f'added_{p}_lo'])}, {fmt(r[f'added_{p}_hi'])}]" if r[f"added_{p}_lo"] is not None else ""
            cells_.append(f"{fmt(r[f'added_{p}_ms'])}{ci}")
        note = "; ".join(sorted({r[f'{p}_note'] for p in PCTS if r[f'{p}_note']}))
        md.append(f"| {r['curve']} | {r['target']} | {fmt(r['offered_rate'], 0)} | {fmt(r['rate_pct'], 0)} | {r['n']} | "
                  + " | ".join(cells_) + f" | {note} |")
    md += ["", "## Every cell", "", "| Cell | Status | Achieved/s | p50 ms | p99 ms | p99.9 ms | max ms | proxy vCPU | max aggregate Mbps |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in flat:
        md.append(f"| {r['cell']} | {r['status']}{' (' + str(r['reason']) + ')' if r.get('reason') else ''} | {fmt(r['achieved_rate'], 1)} | "
                  f"{fmt(r['p50_ms'])} | {fmt(r['p99_ms'])} | {fmt(r['p999_ms'])} | {fmt(r['max_ms'])} | {fmt(r['proxy_vcpu'])} | "
                  f"{fmt(r['max_aggregate_mbps'], 1)} |")
    if fits:
        md += ["", "## Proxy CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S)", "",
               "| Curve | Target | Size | n | vCPU per 1,000 QPS [95%] | intercept vCPU | USD/month per 1,000 QPS at 70% utilisation |",
               "| --- | --- | --- | --- | --- | --- | --- |"]
        for f in fits:
            if "slope" in f:
                md.append(f"| {f['curve']} | {f['target']} | {f['size']} | {f['n']} | {fmt(f['slope'], 4)} [{fmt(f['slope_lo'], 4)}, "
                          f"{fmt(f['slope_hi'], 4)}] | {fmt(f['intercept'], 4)} | {fmt(f.get('usd_per_month_per_1000qps_at_70pct'), 2)} |")
    md += ["", "## Network traffic (owner caps: 400 Mbps per component, 800 Mbps aggregate)", "",
           f"Cells aborted by a cap: {len(summary['aborted_by_cap'])}. Per-cell maxima are in traffic.csv.", ""]
    if validation:
        md += ["## Generator validation", ""]
        for c in validation:
            v = c["validation"]
            md.append(f"- {c['cell']}: {v.get('pauses')} pauses of {v.get('pause_s')} s every {v.get('every_s')} s; "
                      f"max {fmt(v.get('max_ms'), 1)} ms, p99.9 {fmt(v.get('p999_ms'), 1)} ms, fraction above 500 ms "
                      f"{fmt(v.get('observed_fraction_above_500ms'), 4)} (expected {fmt(v.get('expected_fraction_above_500ms'), 4)}): "
                      f"{'PASS' if v.get('pass') else 'FAIL'}")
        md.append("")
    if invalid:
        md += ["## Invalid repetitions (pre-registered rules; kept in the raw data)", ""]
        for c in invalid:
            md.append(f"- {c.get('cell')}: {'; '.join(c.get('invalid_reasons'))}")
        md.append("")
    md += ["## Charts", ""] + [f"![{f}]({f})" for f in files]
    text = "\n".join(md) + "\n"
    with open(os.path.join(out, "report.md"), "w") as f:
        f.write(text)
    body = "".join(f"<pre>{html.escape(line)}</pre>" if not line.startswith("![") else
                   f"<p><img src='{html.escape(line[line.index('(') + 1:-1])}' style='max-width:100%'></p>" for line in md)
    banner = f"<h1 style='color:#d03b3b'>{SMOKE}</h1>" if smoke else ""
    with open(os.path.join(out, "report.html"), "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><title>vericto-bench report</title>"
                f"<body style='font-family:system-ui;background:#fcfcfb;color:#0b0b0b'>{banner}{body}</body>")
    print(f"report: {out}/report.md ({len(drows)} delta rows, {len(files)} charts){' - ' + SMOKE if smoke else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
