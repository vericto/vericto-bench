# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Load tools (vbench, pgbench, sysbench): command lines and result parsing.

Every latency figure is measured from the intended send time:

- vbench open loop: by construction (internal/openloop).
- pgbench -R: its per-transaction log (-l) records the transaction time and the
  schedule lag; latency = time + lag, so it is also from the intended start.
- sysbench: closed loop only (its --rate latency excludes queue time).
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import re
import statistics
from datetime import datetime, timezone

PGBENCH_SCRIPTS = {"select-only": ["-S"], "tpcb-like": [], "simple-update": ["-N"]}
SYSBENCH_TESTS = ("oltp_read_only", "oltp_read_write", "oltp_point_select")


def vbench_args(cell, hosts: list[str], ports: list[int], out: str, stop: str, suite, datasets: dict) -> list[str]:
    c = cell.curve
    warmup = c.warmup_s if c.warmup_s is not None else suite.warmup_s
    duration = c.duration_s if c.duration_s is not None else suite.duration_s
    a = ["vbench", "run", "-engine", c.engine, "-host", hosts[0], "-port", str(ports[0]), "-user", "bench", "-db", "bench",
         "-tls", "require" if c.tls else "disable", "-mode", c.mode, "-workload", c.workload, "-target", cell.target,
         "-label", cell.id, "-conn", c.conn_mode, "-warmup", f"{warmup}s", "-duration", f"{duration}s",
         "-interval", f"{suite.interval_s}s", "-seed", str(suite.order_seed + cell.seq), "-out", out, "-stop-file", stop,
         "-pgbench-scale", str(datasets.get("pgbench_scale", 100)), "-sysbench-tables", str(datasets.get("sysbench_tables", 8)),
         "-sysbench-rows", str(datasets.get("sysbench_rows", 1_000_000)), "-payload-rows", str(datasets.get("payload_rows", 10_000))]
    if len(ports) > 1:
        a += ["-ports", ",".join(f"{h}:{p}" for h, p in zip(hosts, ports))]
    if c.loop == "open":
        a += ["-loop", "open", "-rate", f"{cell.rate:g}", "-arrival", c.arrival]
        if cell.conc:
            a += ["-conns", str(cell.conc)]
    else:
        a += ["-loop", "closed", "-conns", str(cell.conc)]
    return a


def pgbench_args(cell, hosts: list[str], ports: list[int], log_prefix: str, suite, threads: int) -> tuple[list[str], dict]:
    c = cell.curve
    warmup = c.warmup_s if c.warmup_s is not None else suite.warmup_s
    duration = c.duration_s if c.duration_s is not None else suite.duration_s
    if c.workload not in PGBENCH_SCRIPTS:
        raise ValueError(f"pgbench workload must be one of {list(PGBENCH_SCRIPTS)}")
    mode = c.mode or "extended"
    conns = cell.conc or c.conns or 8
    env = {"PGSSLMODE": "require" if c.tls else "disable", "PGAPPNAME": "pgbench"}
    hosts = ",".join(hosts)
    if len(ports) > 1:
        env["PGLOADBALANCEHOSTS"] = "random"  # libpq 16+: spread connections over the two proxy tasks
    a = ["pgbench", "-h", hosts, "-p", ",".join(str(p) for p in ports), "-U", "bench", "-n", "-M", mode,
         "-c", str(conns), "-j", str(max(1, min(threads, conns))), "-T", str(int(math.ceil(warmup + duration))),
         "-P", "10", "-l", f"--log-prefix={log_prefix}"] + PGBENCH_SCRIPTS[c.workload]
    if c.loop == "open":
        a += ["-R", f"{cell.rate:g}"]
    a.append("bench")
    return a, env


def sysbench_args(cell, hosts: list[str], ports: list[int], suite, datasets: dict) -> list[str]:
    c = cell.curve
    if c.workload not in SYSBENCH_TESTS:
        raise ValueError(f"sysbench workload must be one of {SYSBENCH_TESTS}")
    warmup = c.warmup_s if c.warmup_s is not None else suite.warmup_s
    duration = c.duration_s if c.duration_s is not None else suite.duration_s
    # Several ports: sysbench spreads its connections over the host list (two proxy tasks).
    return [c.workload, "--db-driver=mysql", "--mysql-host=" + ",".join(hosts),
            "--mysql-port=" + ",".join(str(p) for p in ports), "--mysql-user=bench",
            "--mysql-db=bench", f"--mysql-ssl={'on' if c.tls else 'off'}",
            f"--tables={datasets.get('sysbench_tables', 8)}", f"--table-size={datasets.get('sysbench_rows', 1_000_000)}",
            # sysbench 1.0.20 has no --warmup-time: the warm-up is dropped from
            # the per-interval reports instead (parse_sysbench).
            f"--threads={cell.conc}", f"--time={int(warmup + duration)}",
            f"--report-interval={max(1, int(suite.interval_s))}", "--percentile=99", "--histogram=off", "--rand-seed=1", "run"]


# ---- percentiles ---------------------------------------------------------------

def summarise(counts: collections.Counter) -> dict:
    """Percentiles in ms from exact microsecond counts (same keys as vbench)."""
    n = sum(counts.values())
    if n == 0:
        return {"count": 0}
    items = sorted(counts.items())
    def q(p):
        rank = max(1, math.ceil(p / 100.0 * n))
        acc = 0
        for v, k in items:
            acc += k
            if acc >= rank:
                return v / 1000.0
        return items[-1][0] / 1000.0
    mean = sum(v * k for v, k in items) / n / 1000.0
    return {"count": n, "mean_ms": mean, "p50_ms": q(50), "p90_ms": q(90), "p99_ms": q(99), "p999_ms": q(99.9),
            "max_ms": items[-1][0] / 1000.0}


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def parse_pgbench(log_prefix: str, warmup: float, duration: float, interval: float, offered: float) -> tuple[dict, list[dict]]:
    """Convert pgbench per-transaction logs into a vbench-shaped result and
    intervals. Log line: client_id transaction_no time script_no time_epoch
    time_us [schedule_lag] (time and lag in us; epoch/us = completion)."""
    rows = []
    for path in sorted(glob.glob(log_prefix + ".*")):
        with open(path) as f:
            for line in f:
                p = line.split()
                if len(p) < 6 or p[2] in ("skipped", "failed"):
                    if len(p) >= 3 and p[2] in ("skipped", "failed"):
                        rows.append((None, p[2]))
                    continue
                t_us = int(p[2])
                done = int(p[4]) + int(p[5]) / 1e6
                lag = int(p[6]) if len(p) >= 7 else 0
                rows.append(((done - (t_us + lag) / 1e6), done, t_us, lag))
    good = [r for r in rows if r[0] is not None]
    bad = collections.Counter(r[1] for r in rows if r[0] is None)
    if not good:
        return {"status": "aborted", "reason": "pgbench logged no transaction", "completed": 0}, []
    start = min(r[0] for r in good)
    mfrom, end = start + warmup, start + warmup + duration
    lat, svc, wait = collections.Counter(), collections.Counter(), collections.Counter()
    nint = max(1, int(math.ceil(duration / interval)))
    ints = [collections.Counter() for _ in range(nint)]
    done_in_window = 0
    completed = 0
    for sched, done, t_us, lag in good:
        if sched < mfrom or sched >= end:
            continue
        completed += 1
        if mfrom <= done < end:
            done_in_window += 1
        total = max(1, t_us + lag)
        lat[total] += 1
        svc[max(1, t_us)] += 1
        wait[lag] += 1
        i = int((sched - mfrom) // interval)
        if 0 <= i < nint:
            ints[i][total] += 1
    achieved = done_in_window / duration
    res = {"tool": "pgbench", "loop": "open" if offered > 0 else "closed", "offered_rate": offered,
           "achieved_rate": achieved, "statements_per_s": None, "completed": completed,
           "errors": sum(bad.values()), "skipped": bad.get("skipped", 0), "unsent": 0, "incomplete": 0,
           "start": _iso(start), "measure_from": _iso(mfrom), "end": _iso(end),
           "latency": summarise(lat), "service": summarise(svc), "queue_wait": summarise(wait), "classes": {}}
    res["status"], res["reason"] = "ok", ""
    if offered > 0:
        # pgbench -R draws Poisson arrivals: the count in the window has a
        # standard deviation of sqrt(expected), so "below 99% of offered" only
        # means saturation beyond three of those as well.
        expected = offered * duration
        if achieved < 0.99 * offered and expected - done_in_window > max(2.0, 3 * math.sqrt(expected)):
            res["status"], res["reason"] = "saturated", "achieved rate below 99% of offered"
        elif (res["queue_wait"].get("p50_ms", 0) > 1.0 and res["queue_wait"]["p50_ms"] > res["service"]["p50_ms"]):
            res["status"], res["reason"] = "saturated", "schedule lag dominates (pgbench client busy)"
    intervals = [{"i": i, "start": _iso(mfrom + i * interval), "end": _iso(min(end, mfrom + (i + 1) * interval)),
                  "completed": sum(c.values()), "buckets_us": sorted([v, k] for v, k in c.items())} for i, c in enumerate(ints)]
    return res, intervals


def parse_pgbench_summary(text: str) -> dict:
    out = {}
    for pat, key in [(r"number of failed transactions: (\d+)", "failed"), (r"tps = ([0-9.]+)", "tps"),
                     (r"number of transactions actually processed: (\d+)", "processed")]:
        m = re.search(pat, text)
        if m:
            out[key] = float(m.group(1))
    if "aborted" in text and "client" in text:
        m = re.search(r"(\d+) of (\d+) clients? .*aborted", text)
        if m:
            out["clients_aborted"] = int(m.group(1))
    return out


def parse_sysbench(text: str, duration: float, warmup: float = 0.0) -> dict:
    """Closed-loop throughput from `sysbench ... run` output: the mean of the
    per-interval reports after the warm-up (the summary includes the warm-up)."""
    def num(pat):
        m = re.search(pat, text)
        return float(m.group(1)) if m else None
    tps = num(r"transactions:\s+\d+\s+\(([0-9.]+) per sec")
    qps = num(r"queries:\s+\d+\s+\(([0-9.]+) per sec")
    errs = num(r"ignored errors:\s+(\d+)")
    iv = [(float(m.group(1)), float(m.group(2)), float(m.group(3)))
          for m in re.finditer(r"\[\s*(\d+)s \].*?tps: ([0-9.]+) qps: ([0-9.]+)", text)]
    after = [x for x in iv if x[0] > warmup]
    if after:
        tps = statistics.mean(x[1] for x in after)
        qps = statistics.mean(x[2] for x in after)
    res = {"tool": "sysbench", "loop": "closed", "achieved_rate": tps or 0.0, "statements_per_s": qps,
           "intervals_after_warmup": len(after),
           "errors": int(errs or 0), "status": "ok" if tps else "aborted", "reason": "" if tps else "no sysbench summary",
           "latency": {"mean_ms": num(r"avg:\s+([0-9.]+)"), "p99_ms": num(r"99th percentile:\s+([0-9.]+)"),
                       "max_ms": num(r"max:\s+([0-9.]+)"), "count": None}, "classes": {}}
    return res


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True, default=str)
        f.write("\n")
