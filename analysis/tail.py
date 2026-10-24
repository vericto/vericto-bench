# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Tail latency near saturation (suites/proxy-tail.toml).

    python3 analysis/tail.py RUN_DIR [--schedmon logs/sut/schedmon.jsonl] [--out DIR]

Uses the cells report.py uses (same validity selection). Per curve, rate and
target, over the repetitions:

- added p50 / p99 / p99.9: target minus direct at the same rate in the same
  repetition (paired), mean with a Student t 95% interval;
- the proxy's CPU (vCPU, vCPU-us per achieved transaction) and its CFS
  throttling from hostmon (throttled periods per second, throttled ms per
  second);
- from host/schedmon.py, when its log is given: the share of 100-ms CFS periods
  that were throttled, the proxy's threads and their CPU, its run-queue wait
  per transaction (schedstat run_delay), and for pgbench cells the share of
  transactions slower than 10 ms that overlap a throttled period (against the
  share of all transactions that do).

Writes tail.md and tail.json.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R  # noqa: E402

SLOW_US = 10_000
USER_HZ = 100


def target_cpu(c: dict) -> dict:
    return ((c.get("cpu") or {}).get("containers") or {}).get("target") or {}


def stat(xs: list[float]) -> dict:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    m, lo, hi = R.mean_ci(xs)
    return {"mean": m, "lo": lo, "hi": hi, "n": len(xs)}


def load_schedmon(path: str) -> dict[str, dict[str, list]]:
    """container -> {"cg": [(t, u, p, n, tu)], "th": [(t, threads)]}, sorted by t."""
    out: dict[str, dict[str, list]] = collections.defaultdict(lambda: {"cg": [], "th": []})
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("k") == "cg":
                out[d["c"]]["cg"].append((d["t"], d["u"], d["p"], d["n"], d["tu"]))
            elif d.get("k") == "th":
                out[d["c"]]["th"].append((d["t"], d["th"]))
    for v in out.values():
        v["cg"].sort()
        v["th"].sort(key=lambda x: x[0])
    return out


def container(c: dict) -> str:
    return f"vb-{c['engine']}-{c['target']}"


def schedmon_cell(c: dict, sm: dict, run: str) -> dict | None:
    rec = sm.get(container(c))
    t0, t1 = R._ts(c.get("measure_from")), R._ts(c.get("end"))
    if not rec or t0 is None or t1 is None:
        return None
    cg = [x for x in rec["cg"] if t0 <= x[0] <= t1]
    if len(cg) < 10:
        return None
    periods = cg[-1][2] - cg[0][2]
    throttled = cg[-1][3] - cg[0][3]
    # throttled 100-ms samples: the windows [t_prev, t] in which nr_throttled grew
    thr_windows = [(a[0], b[0]) for a, b in zip(cg, cg[1:]) if b[3] > a[3]]
    res = {"periods": periods, "throttled_periods": throttled,
           "throttled_share": throttled / periods if periods else None,
           "throttled_ms_per_s": (cg[-1][4] - cg[0][4]) / 1000.0 / (cg[-1][0] - cg[0][0])}
    th = [x for x in rec["th"] if t0 <= x[0] <= t1]
    if len(th) >= 2:
        first = {t[0]: t for t in th[0][1]}
        last = {t[0]: t for t in th[-1][1]}
        secs = th[-1][0] - th[0][0]
        per = []
        for tid, t in last.items():
            a = first.get(tid, [tid, t[1], 0, 0, 0])
            per.append({"comm": t[1], "cpu": (t[2] - a[2]) / USER_HZ / secs, "run_delay_ms_per_s": (t[3] - a[3]) / 1e6 / secs})
        per.sort(key=lambda x: -x["cpu"])
        done = (c.get("achieved_rate") or 0) * secs
        res.update({"threads": len(last), "threads_busy": sum(1 for p in per if p["cpu"] >= 0.01),
                    "top_threads": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in per[:4]],
                    "run_delay_us_per_tx": sum(p["run_delay_ms_per_s"] for p in per) * secs * 1000.0 / done if done else None})
    if c.get("tool") == "pgbench":
        res.update(slow_overlap(c, run, thr_windows, t0, t1))
    return res


def slow_overlap(c: dict, run: str, windows: list[tuple[float, float]], t0: float, t1: float) -> dict:
    """Share of transactions (scheduled in [t0, t1]) whose life [scheduled, done]
    overlaps a throttled 100-ms window, for the slow ones and for all."""
    starts = [w[0] for w in windows]

    def overlaps(a: float, b: float) -> bool:
        i = bisect.bisect_right(starts, b) - 1
        while i >= 0 and windows[i][1] >= a:
            if windows[i][0] <= b:
                return True
            i -= 1
        return False

    n = slow = n_ov = slow_ov = 0
    for path in glob.glob(os.path.join(run, "cells", c["cell"], "pgbench", "tx.*")):
        if not path.endswith(".gz") and os.path.exists(path + ".gz"):
            continue
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt") as f:
            for line in f:
                p = line.split()
                if len(p) < 7 or p[2] in ("skipped", "failed"):
                    continue
                lat = int(p[2]) + int(p[6])
                done = int(p[4]) + int(p[5]) / 1e6
                sched = done - lat / 1e6
                if not (t0 <= sched < t1):
                    continue
                ov = overlaps(sched, done)
                n += 1
                n_ov += ov
                if lat > SLOW_US:
                    slow += 1
                    slow_ov += ov
    return {"tx": n, "slow_tx": slow, "slow_share": slow / n if n else None,
            "all_overlap_throttle": n_ov / n if n else None,
            "slow_overlap_throttle": slow_ov / slow if slow else None}


def rows(used: list[dict], sm: dict | None, run: str) -> list[dict]:
    ok = [c for c in used if c.get("loop") == "open"]
    direct = {(c["curve"], c["offered_rate"], c["rep"]): c for c in ok if c["target"] == "direct"}
    groups = collections.defaultdict(list)
    for c in ok:
        groups[(c["curve"], c["offered_rate"], c["target"])].append(c)
    out = []
    for (curve, rate, target), cs in sorted(groups.items()):
        r = {"curve": curve, "offered_rate": rate, "rate_pct": cs[0].get("rate_pct"), "target": target,
             "size": cs[0].get("size"), "n": len(cs), "saturated": sum(1 for c in cs if c.get("status") == "saturated")}
        okc = [c for c in cs if c.get("status") == "ok"]
        for m in R.PCTS:
            r[m] = stat([R.pct(c, m) for c in okc])
            if target != "direct":
                r["added_" + m] = stat([R.pct(c, m) - R.pct(d, m) for c in okc
                                        if (d := direct.get((curve, rate, c["rep"]))) and d.get("status") == "ok"
                                        and R.pct(c, m) is not None and R.pct(d, m) is not None])
        if target != "direct":
            tc = [target_cpu(c) for c in cs]
            r["vcpu"] = stat([t.get("vcpu") for t in tc])
            r["cpu_us_per_tx"] = stat([t["vcpu"] / c["achieved_rate"] * 1e6 for c, t in zip(cs, tc)
                                       if t.get("vcpu") and c.get("achieved_rate")])
            r["nr_throttled_per_s"] = stat([t["nr_throttled"] / t["seconds"] for t in tc if t.get("seconds")])
            r["throttled_ms_per_s"] = stat([t["throttled_ms"] / t["seconds"] for t in tc if t.get("seconds")])
            if sm:
                per = [x for c in cs if (x := schedmon_cell(c, sm, run))]
                if per:
                    agg = {}
                    for k in ("throttled_share", "threads", "threads_busy", "run_delay_us_per_tx", "slow_share",
                              "all_overlap_throttle", "slow_overlap_throttle"):
                        agg[k] = stat([p.get(k) for p in per])
                    agg["top_threads_rep1"] = per[0].get("top_threads")
                    r["schedmon"] = agg
        out.append(r)
    return out


def s(x: dict | None, d: int = 2, ci: bool = True) -> str:
    if not x or x.get("mean") is None:
        return "-"
    if not ci or x.get("lo") is None:
        return f"{x['mean']:.{d}f}"
    return f"{x['mean']:.{d}f} [{x['lo']:.{d}f}, {x['hi']:.{d}f}]"


def markdown(res: dict, names: dict[str, str]) -> str:
    L = ["# Proxy tail latency near saturation", "",
         f"Cells used: {res['cells_used']}; invalid: {len(res['cells_invalid'])}.", "",
         "Added latency = target minus direct at the same rate in the same repetition, mean "
         "[95% interval] over the repetitions, in ms. CPU in vCPU-us per achieved transaction; "
         "throttled = CFS throttled periods per second (10 periods per second) and throttled ms per second "
         "(hostmon). Saturated cells (achieved below 99% of offered) are counted, not averaged.", ""]
    for curve in sorted({r["curve"] for r in res["rows"]}):
        L += [f"## {curve}", "",
              "| % of S | target | n (sat.) | added p50 | added p99 | added p99.9 | vCPU | CPU us/tx | throttled /s | throttled ms/s |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in [x for x in res["rows"] if x["curve"] == curve and x["target"] != "direct"]:
            L.append(f"| {r['rate_pct']:g} | {names.get(r['target'], r['target'])} | {r['n']} ({r['saturated']}) "
                     f"| {s(r['added_p50'], 3)} | {s(r['added_p99'])} | {s(r['added_p999'])} | {s(r['vcpu'], 3, False)} "
                     f"| {s(r['cpu_us_per_tx'], 1, False)} | {s(r['nr_throttled_per_s'], 2, False)} | {s(r['throttled_ms_per_s'], 1, False)} |")
        L.append("")
        if any("schedmon" in r for r in res["rows"] if r["curve"] == curve):
            L += ["Scheduler (host/schedmon.py, 100-ms cgroup samples, threads every 5 s): share of CFS periods "
                  "throttled; threads of the proxy (busy = at least 1% of a CPU); run-queue wait per transaction "
                  "(all threads, includes the time throttled); for pgbench, the share of transactions over 10 ms "
                  "and the share of those, and of all transactions, whose lifetime overlaps a throttled period.", "",
                  "| % of S | target | periods throttled | threads (busy) | run-queue us/tx | tx > 10 ms | of which overlap a throttle | all tx overlapping |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
            for r in [x for x in res["rows"] if x["curve"] == curve and "schedmon" in x]:
                m = r["schedmon"]
                L.append(f"| {r['rate_pct']:g} | {names.get(r['target'], r['target'])} | {s(m['throttled_share'], 3, False)} "
                         f"| {s(m['threads'], 0, False)} ({s(m['threads_busy'], 0, False)}) | {s(m['run_delay_us_per_tx'], 1, False)} "
                         f"| {s(m['slow_share'], 4, False)} | {s(m['slow_overlap_throttle'], 3, False)} | {s(m['all_overlap_throttle'], 3, False)} |")
            L.append("")
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--schedmon", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    man, cells = R.load_run(a.run)
    names = {n: v.get("label") or n for n, v in (man.get("proxy_variants") or {}).items()}
    used, invalid = R.select(cells)
    sm = load_schedmon(a.schedmon) if a.schedmon else None
    res = {"cells_used": len(used), "cells_invalid": [c.get("cell") for c in invalid],
           "rows": rows(used, sm, a.run)}
    out = a.out or os.path.join(a.run, "report")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "tail.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    with open(os.path.join(out, "tail.md"), "w") as fh:
        fh.write(markdown(res, names))
    print(f"tail: {os.path.join(out, 'tail.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
