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
LABEL = ""  # --label, e.g. "day 1 of 2": on the report, every chart and every CSV


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
                # Day 2 repeats day 1's headline curves under "<id>-day2": the
                # same curve for the analysis (pooled n = 6, between-day row).
                if str(c.get("curve", "")).endswith("-day2"):
                    c["curve_id"] = c["curve"]
                    c["curve"] = c["curve"][: -len("-day2")]
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

def deltas(used: list[dict], by_day: bool = False) -> list[dict]:
    """Paired deltas: target minus direct, same curve, rate, repetition and day
    (and run). Pooled across days unless by_day."""
    open_ok = [c for c in used if c.get("loop") == "open" and c.get("status") == "ok"]
    direct = {(c["_run"], c["curve"], c["offered_rate"], c["rep"], c.get("day")): c for c in open_ok if c["target"] == "direct"}
    groups: dict[tuple, dict[str, list[float]]] = {}
    for c in open_ok:
        if c["target"] == "direct":
            continue
        d = direct.get((c["_run"], c["curve"], c["offered_rate"], c["rep"], c.get("day")))
        if not d:
            continue
        gk = (c["curve"], c["engine"], c["target"], c["offered_rate"], c.get("rate_pct")) + ((c.get("day"),) if by_day else ())
        g = groups.setdefault(gk, {p: [] for p in PCTS})
        for p in PCTS:
            a, b = pct(c, p), pct(d, p)
            if a is not None and b is not None:
                g[p].append(a - b)
    rows = []
    for gk, g in sorted(groups.items(), key=lambda x: (x[0][0], x[0][2], x[0][3], x[0][5:])):
        curve, engine, target, rate, rpct = gk[:5]
        row = {"curve": curve, "engine": engine, "target": target, "offered_rate": rate, "rate_pct": rpct, "n": len(g["p50"])}
        if by_day:
            row["day"] = gk[5]
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


# ---- traffic per direction, statement size, large results -------------------------

DIRECTIONS = (("client_to_target", "client to target"), ("target_to_client", "target to client"),
              ("target_to_db", "target to database"), ("db_to_target", "database to target"),
              ("telemetry_out", "telemetry (proxy to stub)"), ("telemetry_in", "stub to proxy"))


def _window_counters(c: dict) -> tuple[dict[str, float], float]:
    """Bytes per counter over the cell's measured window, from the guard's raw
    copy of the 1-s samples (cumulative counters): last minus first sample of
    each host inside [measure_from, end], divided by the time between them."""
    path = os.path.join(c.get("_run", ""), "cells", str(c.get("cell")), "samples.jsonl")
    t0, t1 = _ts(c.get("measure_from")), _ts(c.get("end"))
    if not os.path.exists(path) or t0 is None or t1 is None:
        return {}, 0.0
    first: dict[str, tuple[float, dict]] = {}
    last: dict[str, tuple[float, dict]] = {}
    with open(path) as f:
        for line in f:
            try:
                x = json.loads(line)
                t = _ts(x["t"])
            except (ValueError, KeyError, TypeError):
                continue
            if t is None or t < t0 or t > t1 or not x.get("c"):
                continue
            h = x.get("host", "")
            first.setdefault(h, (t, x["c"]))
            last[h] = (t, x["c"])
    rates, secs = {}, 0.0
    for h, (ta, a) in first.items():
        tb, b = last[h]
        if tb - ta < 1:
            continue
        secs = max(secs, tb - ta)
        for k, v in b.items():
            if k in a:
                rates[k] = (v - a[k]) / (tb - ta)
    return rates, secs


def _ts(s) -> float | None:
    if not s:
        return None
    from datetime import datetime
    v = str(s).replace("Z", "+00:00")
    if "." in v:
        v = _trim_frac(v)
    try:
        return datetime.fromisoformat(v).timestamp()
    except ValueError:
        return None


def _trim_frac(s: str) -> str:
    """fromisoformat (3.10/3.11) takes at most 6 fractional digits; Go writes 9."""
    import re
    return re.sub(r"\.(\d{1,6})\d*", r".\1", s, count=1)


DB_PORT = {"pg": 5432, "mysql": 3306}


def direction_rows(cells: list[dict]) -> list[dict]:
    """Bytes/s per direction in every measured cell (design section 8a,
    "what is reported instead of high traffic"): client to target, target to
    client, target to database, database to target, telemetry egress, and the
    NICs; plus bytes per request. Intermediary listen ports from the cell's
    components.json."""
    rows = []
    for c in cells:
        if c.get("status") in ("not_run", None) or str(c.get("cell", "")).endswith(".netprobe"):
            continue
        rates, secs = _window_counters(c)
        if not rates:
            continue
        dbp = DB_PORT.get(c.get("engine"), 0)
        comp_path = os.path.join(c["_run"], "cells", str(c["cell"]), "components.json")
        listen = []
        try:
            comps = json.load(open(comp_path))
            listen = sorted({k.split(":")[-1][1:].rsplit("_", 1)[0] for k in comps.get("intermediary", []) if ":nft:p" in k})
        except (OSError, ValueError):
            pass
        g = lambda k: sum(v for kk, v in rates.items() if kk.endswith(":nft:" + k))  # noqa: E731
        if c.get("target") == "direct":
            d = {"client_to_target": g(f"db{dbp}_in") + g(f"db{dbp}_lo_in"), "target_to_client": g(f"db{dbp}_out") + g(f"db{dbp}_lo_out"),
                 "target_to_db": 0.0, "db_to_target": 0.0, "telemetry_out": 0.0, "telemetry_in": 0.0}
        else:
            d = {"client_to_target": sum(g(f"p{p}_in") for p in listen), "target_to_client": sum(g(f"p{p}_out") for p in listen),
                 "target_to_db": g(f"db{dbp}_lo_in"), "db_to_target": g(f"db{dbp}_lo_out"),
                 "telemetry_out": g("cp9090_in"), "telemetry_in": g("cp9090_out")}
        nic = {k.replace(":iface:default:", "_nic_"): v for k, v in rates.items() if ":iface:" in k}
        req = c.get("achieved_rate") or 0
        row = {"cell": c["cell"], "curve": c.get("curve"), "engine": c.get("engine"), "workload": c.get("workload"),
               "target": c.get("target"), "size": c.get("size"), "tls": c.get("tls"), "loop": c.get("loop"),
               "offered_rate": c.get("offered_rate"), "conc": c.get("conc"), "rep": c.get("rep"), "achieved_rate": req,
               "window_s": round(secs, 1)}
        for k, v in d.items():
            row[f"{k}_mbps"] = v * 8 / 1e6
        for k, v in sorted(nic.items()):
            row[f"{k}_mbps"] = v * 8 / 1e6
        row["target_total_mbps"] = sum(d.values()) * 8 / 1e6
        if req > 0:
            row["result_bytes_per_request"] = d["target_to_client"] / req
            row["request_bytes_per_request"] = d["client_to_target"] / req
        rows.append(row)
    return rows


def statement_bytes(runs: list[str]) -> dict[tuple[str, str], int]:
    """(engine, workload) -> bytes of the statement text the proxy sees, from
    the run's statements.jsonl (vbench dump, written by the verdict pre-flight)."""
    out: dict[tuple[str, str], int] = {}
    for r in runs:
        try:
            f = open(os.path.join(r, "statements.jsonl"))
        except OSError:
            continue
        with f:
            for line in f:
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                eng = {"postgres": "pg", "mysql": "mysql"}.get(x.get("dialect"), x.get("dialect"))
                k = (eng, x.get("workload"))
                out[k] = max(out.get(k, 0), int(x.get("bytes") or 0))
    return out


def size_rows(drows: list[dict], sizes: dict[tuple[str, str], int]) -> tuple[list[dict], list[dict]]:
    """Statement-size curve (W5): added latency against KB of SQL per engine,
    statement family (multi-row INSERT, IN list) and proxy size; a linear fit
    of added p50 against KB (the ms/KB slope) and the size where the fit
    passes 1 ms."""
    import re
    pts, fits = [], []
    for r in drows:
        m = re.match(r"size-(pg|mysql)-(batch|inlist)(\d+)-(05|1)$", str(r["curve"]))
        if not m or r["target"] != "vericto-enforce":
            continue
        eng, fam, n, tag = m.groups()
        wl = f"{fam}{n}"
        kb = sizes.get((eng, wl), 0) / 1024.0
        pts.append({"engine": eng, "family": fam, "n": int(n), "size": "0.5" if tag == "05" else "1", "kb": kb,
                    **{k: r[k] for k in r if k.startswith("added_")}, "reps": r["n"]})
    for key in sorted({(p["engine"], p["family"], p["size"]) for p in pts}):
        ps = sorted([p for p in pts if (p["engine"], p["family"], p["size"]) == key], key=lambda p: p["kb"])
        row = {"engine": key[0], "family": key[1], "size": key[2], "points": len(ps)}
        for q in ("p50", "p99"):
            f = ols([p["kb"] for p in ps], [p[f"added_{q}_ms"] for p in ps])
            if "slope" in f:
                row[f"{q}_ms_per_kb"], row[f"{q}_ms_per_kb_lo"], row[f"{q}_ms_per_kb_hi"] = f["slope"], f["slope_lo"], f["slope_hi"]
                row[f"{q}_intercept_ms"] = f["intercept"]
                row[f"{q}_kb_at_1ms"] = (1.0 - f["intercept"]) / f["slope"] if f["slope"] > 0 else None
        first_over = next((p["kb"] for p in ps if p["added_p50_ms"] > 1.0), None)
        row["first_measured_kb_with_added_p50_over_1ms"] = first_over
        fits.append(row)
    return pts, fits


def bytes_rows(used: list[dict], drows: list[dict], dirs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Large results (W8), plain against masked: added latency and proxy CPU
    per rate, and the per-byte cost (slope of proxy vCPU against result MB/s,
    i.e. CPU-seconds per MB relayed, and added p50 per KB of result)."""
    import re
    dir_by_cell = {d["cell"]: d for d in dirs}
    table = []
    for r in drows:
        m = re.match(r"bytes-(pg|mysql)-payload-(10k|100k|1m)(-masked)?$", str(r["curve"]))
        if not m:
            continue
        table.append({"engine": m.group(1), "result": m.group(2), "masked": bool(m.group(3)), "rate": r["offered_rate"],
                      "n": r["n"], "added_p50_ms": r["added_p50_ms"], "added_p50_lo": r["added_p50_lo"], "added_p50_hi": r["added_p50_hi"],
                      "added_p99_ms": r["added_p99_ms"], "added_p99_lo": r["added_p99_lo"], "added_p99_hi": r["added_p99_hi"]})
    cpu_pts: dict[tuple, list[tuple[float, float]]] = {}
    for c in used:
        m = re.match(r"bytes-(pg|mysql)-payload-(10k|100k|1m)(-masked)?$", str(c.get("curve")))
        if not m or c.get("target") != "vericto-enforce" or c.get("status") != "ok":
            continue
        cont = ((c.get("cpu") or {}).get("containers") or {})
        v = sum(x["vcpu"] for k, x in cont.items() if k.startswith("target"))
        d = dir_by_cell.get(c["cell"])
        if not d or v <= 0:
            continue
        mbps = (d["target_to_client_mbps"] or 0) / 8.0  # MB/s of results relayed to the client
        cpu_pts.setdefault((m.group(1), bool(m.group(3))), []).append((mbps, v))
        for t in table:
            if (t["engine"], t["result"], t["masked"], t["rate"]) == (m.group(1), m.group(2), bool(m.group(3)), c.get("offered_rate")):
                t.setdefault("_vcpu", []).append(v)
                t.setdefault("_mbs", []).append(mbps)
    for t in table:
        t["proxy_vcpu"] = statistics.mean(t.pop("_vcpu")) if t.get("_vcpu") else None
        t["result_mb_per_s"] = statistics.mean(t.pop("_mbs")) if t.get("_mbs") else None
    fits = []
    for (eng, masked), p in sorted(cpu_pts.items()):
        f = ols([x for x, _ in p], [y for _, y in p])
        fits.append({"engine": eng, "masked": masked, **f, "unit": "vCPU-seconds per MB of result relayed (slope of vCPU against MB/s)"})
    table.sort(key=lambda t: (t["engine"], {"10k": 0, "100k": 1, "1m": 2}[t["result"]], t["rate"], t["masked"]))
    return table, fits


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
        if LABEL:
            fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, color="#52514e")
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


def scaling_rows(cells: list[dict], drows: list[dict]) -> list[dict]:
    """P-2tasks: 1 x 0.5, 1 x 1 and 2 x 0.5 vCPU of vericto-enforce at the same
    absolute rates (h2-<engine>-<workload>-<size>). Per size and rate: cells ok /
    saturated, achieved rate, added p50 / p99 (paired), and each task's vCPU,
    so an uneven split between the two tasks shows (staging P3 saw PG with two
    tasks saturate below one task, cause unexplained)."""
    import re
    d_by = {(r["curve"], r["offered_rate"]): r for r in drows if r["target"] == "vericto-enforce"}
    groups: dict[tuple, list[dict]] = {}
    for c in cells:
        m = re.match(r"h2-(pg|mysql)-(w1|w3)-(05|1|2x05)$", str(c.get("curve")))
        if not m or c.get("target") != "vericto-enforce" or c.get("status") in (None, "not_run") or c.get("invalid_reasons") \
                or str(c.get("cell", "")).endswith(".netprobe"):
            continue
        groups.setdefault((m.group(1), m.group(3), c.get("offered_rate")), []).append(c)
    rows = []
    for (eng, size, rate), cs in sorted(groups.items(), key=lambda x: (x[0][0], x[0][2], {"05": 0, "1": 1, "2x05": 2}[x[0][1]])):
        def vc(c, k):
            return (((c.get("cpu") or {}).get("containers") or {}).get(k) or {}).get("vcpu")
        t1 = [v for v in (vc(c, "target") for c in cs) if v is not None]
        t2 = [v for v in (vc(c, "target2") for c in cs) if v is not None]
        curve = f"h2-{eng}-{'w1' if eng == 'pg' else 'w3'}-{size}"
        d = d_by.get((curve, rate)) or {}
        thr = [((c.get("cpu") or {}).get("containers") or {}).get("target", {}).get("throttled_ms", 0) for c in cs]
        rows.append({"engine": eng, "size": {"05": "1x0.5", "1": "1x1", "2x05": "2x0.5"}[size], "offered_rate": rate, "cells": len(cs),
                     "saturated": sum(1 for c in cs if c.get("status") == "saturated"),
                     "achieved_rate": statistics.mean(c.get("achieved_rate") or 0 for c in cs),
                     "added_p50_ms": d.get("added_p50_ms"), "added_p99_ms": d.get("added_p99_ms"), "n_paired": d.get("n"),
                     "task1_vcpu": statistics.mean(t1) if t1 else None, "task2_vcpu": statistics.mean(t2) if t2 else None,
                     "task1_throttled_ms": statistics.mean(thr) if thr else None})
    return rows


def charts_extra(out: str, smoke: bool, dirs: list[dict], size_pts: list[dict], btable: list[dict]) -> list[str]:
    """Size curve, bytes/s per direction, large results plain against masked."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    os.makedirs(os.path.join(out, "charts"), exist_ok=True)
    files = []

    def finish(fig, name, title):
        fig.suptitle(title, fontsize=10, color="#0b0b0b")
        if LABEL:
            fig.text(0.99, 0.01, LABEL, ha="right", fontsize=7, color="#52514e")
        if smoke:
            fig.text(0.5, 0.5, SMOKE, ha="center", va="center", fontsize=16, color="#d03b3b", alpha=0.25, rotation=20)
            fig.text(0.01, 0.01, SMOKE, fontsize=8, color="#d03b3b")
        fig.tight_layout(rect=(0, 0.03, 1, 0.95))
        p = os.path.join(out, "charts", name)
        fig.savefig(p, dpi=130)
        plt.close(fig)
        files.append(os.path.relpath(p, out))

    # Size curve: added p50 and p99 against KB of SQL, the 1-ms line.
    series = sorted({(p["engine"], p["family"], p["size"]) for p in size_pts})
    if series:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=False)
        styles = ["#2a78d6", "#eb6834", "#1baf7a", "#e87ba4", "#eda100", "#008300", "#52514e", "#7d4cc2"]
        marks = ["o", "s", "^", "v", "D", "P", "X", "*"]
        for ax, q in zip(axes, ("p50", "p99")):
            for i, key in enumerate(series):
                ps = sorted([p for p in size_pts if (p["engine"], p["family"], p["size"]) == key], key=lambda p: p["kb"])
                ys = [p[f"added_{q}_ms"] for p in ps]
                err = [[(p[f"added_{q}_ms"] - p[f"added_{q}_lo"]) if p[f"added_{q}_lo"] is not None else 0 for p in ps],
                       [(p[f"added_{q}_hi"] - p[f"added_{q}_ms"]) if p[f"added_{q}_hi"] is not None else 0 for p in ps]]
                ax.errorbar([p["kb"] for p in ps], ys, yerr=err, color=styles[i % 8], marker=marks[i % 8], capsize=3,
                            label=f"{key[0]} {'INSERT rows' if key[1] == 'batch' else 'IN list'}, {key[2]} vCPU")
            ax.axhline(1.0, color="#d03b3b", linewidth=0.9, linestyle="--")
            ax.text(0.01, 1.0, " 1 ms", color="#d03b3b", fontsize=7, va="bottom", transform=ax.get_yaxis_transform())
            ax.axhline(0, color="#52514e", linewidth=0.8)
            ax.set_xlabel("statement size (KB of SQL text the proxy evaluates)")
            ax.set_title(f"added {q}", fontsize=9)
        axes[0].set_ylabel("ms over the direct path")
        axes[-1].legend(fontsize=6.5, frameon=False)
        finish(fig, "size-curve.png", "Statement size: added latency vs KB of SQL (10 statements/s, 1 connection, TLS)")

    # Bytes/s per direction: vericto-enforce cells of each open-loop curve, against offered rate.
    by_curve: dict[str, list[dict]] = {}
    for d in dirs:
        if d["target"] == "vericto-enforce" and d["loop"] == "open":
            by_curve.setdefault(d["curve"], []).append(d)
    keep = [c for c in sorted(by_curve) if c.startswith(("head-", "bytes-", "orm-"))]
    for curve in keep:
        rs = by_curve[curve]
        rates = sorted({r["offered_rate"] for r in rs})
        fig, ax = plt.subplots(figsize=(6, 3.6))
        cols = ["#2a78d6", "#eb6834", "#1baf7a", "#e87ba4", "#eda100", "#008300"]
        for (k, name), col in zip(DIRECTIONS, cols):
            ys = [statistics.mean([r[f"{k}_mbps"] for r in rs if r["offered_rate"] == x]) for x in rates]
            # Upstream hop dashed: it often equals the client hop and would hide it.
            ax.plot(rates, ys, color=col, marker="o" if "db" not in k else "s", linestyle="--" if "db" in k else "-", label=name)
        tot = [statistics.mean([r["target_total_mbps"] for r in rs if r["offered_rate"] == x]) for x in rates]
        ax.plot(rates, tot, color="#0b0b0b", linestyle=":", label="proxy total (both hops, both directions)")
        ax.axhline(400, color="#d03b3b", linewidth=0.9, linestyle="--")
        ax.text(0.01, 400, " 400 Mbps cap", color="#d03b3b", fontsize=7, va="bottom", transform=ax.get_yaxis_transform())
        ax.set_xlabel("offered rate (requests/s)")
        ax.set_ylabel("Mbps (measured window mean)")
        ax.legend(fontsize=6.5, frameon=False)
        finish(fig, f"traffic-{curve}.png", f"{curve}: vericto-enforce bytes/s per direction")

    # Large results: added p50 plain vs masked, per result size.
    if btable:
        groups = sorted({(t["engine"], t["result"]) for t in btable}, key=lambda g: (g[0], {"10k": 0, "100k": 1, "1m": 2}[g[1]]))
        fig, axes = plt.subplots(1, len(groups), figsize=(3.4 * len(groups), 3.4), squeeze=False)
        for ax, g in zip(axes[0], groups):
            for masked, col, mk in ((False, "#2a78d6", "o"), (True, "#e87ba4", "v")):
                ts = sorted([t for t in btable if (t["engine"], t["result"]) == g and t["masked"] == masked], key=lambda t: t["rate"])
                if not ts:
                    continue
                err = [[(t["added_p50_ms"] - t["added_p50_lo"]) if t["added_p50_lo"] is not None else 0 for t in ts],
                       [(t["added_p50_hi"] - t["added_p50_ms"]) if t["added_p50_hi"] is not None else 0 for t in ts]]
                ax.errorbar([t["rate"] for t in ts], [t["added_p50_ms"] for t in ts], yerr=err, color=col, marker=mk, capsize=3,
                            label="masked column" if masked else "plain")
            ax.axhline(0, color="#52514e", linewidth=0.8)
            ax.set_title(f"{g[0]}, {g[1]} result", fontsize=9)
            ax.set_xlabel("offered rate (requests/s)")
        axes[0][0].set_ylabel("added p50 (ms)")
        axes[0][-1].legend(fontsize=7, frameon=False)
        finish(fig, "bytes-masked-vs-plain.png", "Large results: added p50, plain vs one masked column (vericto-enforce, 0.5 vCPU)")
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
        if LABEL:
            f.write(f"# {LABEL}\n")
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
    ap.add_argument("--label", default="", help='shown on the report, every chart and every CSV, e.g. "day 1 of 2"')
    a = ap.parse_args(argv)
    global LABEL
    LABEL = a.label
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
    days = sorted({c.get("day") for c in used if c.get("day") is not None})
    between = []
    if len(days) > 1:
        per_day = deltas(used, by_day=True)
        idx = {(r["curve"], r["target"], r["offered_rate"], r["day"]): r for r in per_day}
        for (curve, target, rate, day), r in sorted(idx.items(), key=lambda x: (str(x[0][0]), str(x[0][1]), x[0][2], x[0][3])):
            if day != days[0] or not all((curve, target, rate, d) in idx for d in days[1:]):
                continue
            row = {"curve": curve, "target": target, "offered_rate": rate}
            for d in days:
                x = idx[(curve, target, rate, d)]
                for p in ("p50", "p99"):
                    row[f"day{d}_added_{p}_ms"], row[f"day{d}_n"] = x[f"added_{p}_ms"], x["n"]
            first = idx[(curve, target, rate, days[0])]
            flags = []
            for p in ("p50", "p99"):
                row[f"between_day_diff_{p}_ms"] = row[f"day{days[-1]}_added_{p}_ms"] - row[f"day{days[0]}_added_{p}_ms"]
                lo, hi = first[f"added_{p}_lo"], first[f"added_{p}_hi"]
                row[f"day{days[0]}_added_{p}_lo"], row[f"day{days[0]}_added_{p}_hi"] = lo, hi
                for d in days[1:]:
                    v = row[f"day{d}_added_{p}_ms"]
                    if lo is not None and v is not None and not (lo <= v <= hi):
                        flags.append(f"day {d} {p} outside day {days[0]}'s 95% interval")
            row["flag"] = "; ".join(flags)
            between.append(row)
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
    dirs = direction_rows(used)
    sizes = statement_bytes(a.runs)
    size_pts, size_fits = size_rows(drows, sizes)
    btable, bfits = bytes_rows(used, drows, dirs)
    scaling = scaling_rows(cells, drows)
    if scaling:
        write_csv(os.path.join(out, "scaling.csv"), scaling, smoke)
    write_csv(os.path.join(out, "traffic_directions.csv"), dirs, smoke)
    if between:
        write_csv(os.path.join(out, "between_days.csv"), between, smoke)
    write_csv(os.path.join(out, "size_curve.csv"), size_pts, smoke)
    write_csv(os.path.join(out, "size_fit.csv"), size_fits, smoke)
    write_csv(os.path.join(out, "large_results.csv"), btable, smoke)
    write_csv(os.path.join(out, "large_results_cpu_fit.csv"), bfits, smoke)
    files = charts(out, used, drows, fits, smoke)
    files += charts_extra(out, smoke, dirs, size_pts, btable)
    validation = [c for c in cells if c.get("validation")]
    summary = {"banner": SMOKE if smoke else None, "runs": [m.get("run_id") for m in mans], "profiles": sorted(p or "?" for p in profiles),
               "cells": len(cells), "used": len(used), "invalid": len(invalid), "deltas": drows, "cpu_fits": fits,
               "validation": [c["validation"] | {"cell": c["cell"]} for c in validation],
               "aborted_by_cap": [c["cell"] for c in cells if c.get("net_aborted")], "charts": files,
               "label": LABEL or None, "size_fits": size_fits, "large_results": btable, "large_results_cpu_fits": bfits}
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    md = []
    if smoke:
        md += [f"# {SMOKE}", "", f"**{SMOKE}.** This report proves the pipeline only. No figure in it is a measurement "
               "of anything: it ran on one shared Docker host with no CPU isolation and seconds-long cells.", ""]
    if LABEL:
        md += [f"**{LABEL}.**", ""]
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
    if between:
        md += ["", f"## Between days (days {', '.join(str(d) for d in days)}; the pooled rows above use every day)", "",
               f"Day {days[0]} intervals are Student t 95% over its repetitions; a later day's value outside them is flagged.", "",
               "| Curve | Target | Rate/s | " + " | ".join(f"day {d} added p50 / p99 ms (n)" for d in days)
               + f" | day {days[0]} p50 [95%] | day {days[0]} p99 [95%] | difference p50 / p99 ms | flag |",
               "| --- | --- | --- | " + " | ".join("---" for _ in days) + " | --- | --- | --- | --- |"]
        for b in between:
            d0 = days[0]
            md.append(f"| {b['curve']} | {b['target']} | {fmt(b['offered_rate'], 0)} | "
                      + " | ".join(f"{fmt(b[f'day{d}_added_p50_ms'])} / {fmt(b[f'day{d}_added_p99_ms'])} ({b[f'day{d}_n']})" for d in days)
                      + f" | [{fmt(b[f'day{d0}_added_p50_lo'])}, {fmt(b[f'day{d0}_added_p50_hi'])}]"
                      + f" | [{fmt(b[f'day{d0}_added_p99_lo'])}, {fmt(b[f'day{d0}_added_p99_hi'])}]"
                      + f" | {fmt(b['between_day_diff_p50_ms'])} / {fmt(b['between_day_diff_p99_ms'])} | {b['flag'] or 'within'} |")
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
           f"Cells aborted by a cap: {len(summary['aborted_by_cap'])}. Per-cell maxima are in traffic.csv; "
           "bytes/s per direction over each measured window in traffic_directions.csv.", ""]
    hd = [d for d in dirs if d["loop"] == "open" and d["target"] == "vericto-enforce"]
    if hd:
        md += ["Bytes per direction at vericto-enforce, highest offered rate of each open-loop curve (saturated cells included; Mbps, window mean):", "",
               "| Curve | Rate/s | client to proxy | proxy to client | proxy to DB | DB to proxy | telemetry out | proxy total | result bytes per request |",
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for curve in sorted({d["curve"] for d in hd}):
            rs = [d for d in hd if d["curve"] == curve]
            top = max(r["offered_rate"] for r in rs)
            rs = [r for r in rs if r["offered_rate"] == top]
            mm = lambda k: statistics.mean(r[k] for r in rs)  # noqa: E731
            md.append(f"| {curve} | {fmt(top, 0)} | {fmt(mm('client_to_target_mbps'), 1)} | {fmt(mm('target_to_client_mbps'), 1)} | "
                      f"{fmt(mm('target_to_db_mbps'), 1)} | {fmt(mm('db_to_target_mbps'), 1)} | {fmt(mm('telemetry_out_mbps'), 2)} | "
                      f"{fmt(mm('target_total_mbps'), 1)} | {fmt(statistics.mean(r.get('result_bytes_per_request') or 0 for r in rs), 0)} |")
        md.append("")
    if size_fits:
        md += ["## Statement size (W5): added latency per KB of SQL", "",
               "| Engine | Statement | Proxy size | points | added p50 ms/KB [95%] | added p99 ms/KB [95%] | KB where the p50 fit passes 1 ms | first measured KB with added p50 > 1 ms |",
               "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for f in size_fits:
            md.append(f"| {f['engine']} | {'multi-row INSERT' if f['family'] == 'batch' else 'IN list'} | {f['size']} | {f['points']} | "
                      f"{fmt(f.get('p50_ms_per_kb'), 4)} [{fmt(f.get('p50_ms_per_kb_lo'), 4)}, {fmt(f.get('p50_ms_per_kb_hi'), 4)}] | "
                      f"{fmt(f.get('p99_ms_per_kb'), 4)} [{fmt(f.get('p99_ms_per_kb_lo'), 4)}, {fmt(f.get('p99_ms_per_kb_hi'), 4)}] | "
                      f"{fmt(f.get('p50_kb_at_1ms'), 1)} | {fmt(f.get('first_measured_kb_with_added_p50_over_1ms'), 1)} |")
        md.append("")
    if scaling:
        md += ["## Horizontal scaling (P-2tasks): 1 x 0.5, 1 x 1 and 2 x 0.5 vCPU at the same absolute rates", "",
               "Saturated cells end a curve (never latency). With two tasks the client spreads its connections over both "
               "ports; task 1 / task 2 vCPU show whether the load split evenly.", "",
               "| Engine | Proxy | Rate/s | cells (saturated) | achieved/s | added p50 ms | added p99 ms | task 1 vCPU | task 2 vCPU | task 1 throttled ms |",
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in scaling:
            md.append(f"| {r['engine']} | {r['size']} | {fmt(r['offered_rate'], 0)} | {r['cells']} ({r['saturated']}) | {fmt(r['achieved_rate'], 0)} | "
                      f"{fmt(r['added_p50_ms'])} | {fmt(r['added_p99_ms'])} | {fmt(r['task1_vcpu'])} | {fmt(r['task2_vcpu'])} | {fmt(r['task1_throttled_ms'], 0)} |")
        md.append("")
    if btable:
        md += ["## Large results (W8): plain against one masked column, vericto-enforce at 0.5 vCPU", "",
               "| Engine | Result | Rate/s | Masked | n | added p50 ms [95%] | added p99 ms [95%] | proxy vCPU | result MB/s |",
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for t in btable:
            ci = lambda q: f" [{fmt(t[f'added_{q}_lo'])}, {fmt(t[f'added_{q}_hi'])}]" if t[f"added_{q}_lo"] is not None else ""  # noqa: E731
            md.append(f"| {t['engine']} | {t['result']} | {fmt(t['rate'], 0)} | {'yes' if t['masked'] else 'no'} | {t['n']} | "
                      f"{fmt(t['added_p50_ms'])}{ci('p50')} | {fmt(t['added_p99_ms'])}{ci('p99')} | {fmt(t['proxy_vcpu'])} | {fmt(t['result_mb_per_s'], 2)} |")
        md.append("")
        for f in bfits:
            if "slope" in f:
                md.append(f"- {f['engine']} {'masked' if f['masked'] else 'plain'}: {fmt(f['slope'], 4)} [{fmt(f['slope_lo'], 4)}, "
                          f"{fmt(f['slope_hi'], 4)}] vCPU-seconds per MB of result relayed (n = {f['n']}).")
        md.append("")
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
