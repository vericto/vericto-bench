#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
"""Scheduler monitor of the proxy containers on the SUT (started by the SUT's
user-data, pinned to CPU_AUX). Complements hostmon's 1 Hz samples with what a
CFS-quota stall needs to be seen:

- every 100 ms, the cgroup v2 cpu.stat of each running vericto container
  (usage_usec, nr_periods, nr_throttled, throttled_usec): one CFS period per
  sample at the default 100 ms period;
- every 5 s, every thread of the container's main process: name, CPU ticks
  (utime + stime), run-queue wait (schedstat run_delay, ns) and timeslices.

JSON lines on --out: {"k":"cg","t":epoch,"c":name,"u":..,"p":..,"n":..,"tu":..}
and {"k":"th","t":epoch,"c":name,"pid":..,"th":[[tid,comm,ticks,run_delay_ns,slices],...]}.
Analysis matches them to cells by container name and the cell's window.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time

NAME_PREFIXES = ("vb-pg-vericto", "vb-mysql-vericto")


def containers() -> dict[str, tuple[str, int]]:
    """name -> (cgroup dir, main pid) of the running vericto containers."""
    try:
        out = subprocess.run(["docker", "ps", "--no-trunc", "--format", "{{.ID}} {{.Names}}"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    found = {}
    for line in out.splitlines():
        cid, _, name = line.partition(" ")
        if not name.startswith(NAME_PREFIXES):
            continue
        cg = f"/sys/fs/cgroup/system.slice/docker-{cid}.scope"
        try:
            pid = int(subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", cid],
                                     capture_output=True, text=True, timeout=10).stdout.strip() or 0)
        except (OSError, subprocess.SubprocessError, ValueError):
            pid = 0
        if os.path.isdir(cg):
            found[name] = (cg, pid)
    return found


def cpu_stat(cg: str) -> dict | None:
    try:
        with open(os.path.join(cg, "cpu.stat")) as f:
            kv = dict(line.split() for line in f if line.strip())
    except (OSError, ValueError):
        return None
    return {"u": int(kv.get("usage_usec", 0)), "p": int(kv.get("nr_periods", 0)),
            "n": int(kv.get("nr_throttled", 0)), "tu": int(kv.get("throttled_usec", 0))}


def threads(pid: int) -> list:
    out = []
    base = f"/proc/{pid}/task"
    try:
        tids = os.listdir(base)
    except OSError:
        return out
    for tid in tids:
        try:
            with open(f"{base}/{tid}/stat") as f:
                st = f.read()
            with open(f"{base}/{tid}/schedstat") as f:
                ss = f.read().split()
        except OSError:
            continue
        comm = st[st.index("(") + 1:st.rindex(")")]
        rest = st[st.rindex(")") + 2:].split()
        ticks = int(rest[11]) + int(rest[12])  # utime + stime (fields 14, 15)
        out.append([int(tid), comm, ticks, int(ss[1]), int(ss[2])])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=0.1)
    ap.add_argument("--threads-every", type=float, default=5.0)
    a = ap.parse_args()
    found, next_scan, next_threads = {}, 0.0, 0.0
    with open(a.out, "a", buffering=1) as out:
        tick = time.monotonic()
        while True:
            now = time.time()
            mono = time.monotonic()
            if mono >= next_scan:
                found = containers()
                next_scan = mono + 2.0
            for name, (cg, pid) in found.items():
                s = cpu_stat(cg)
                if s:
                    out.write(json.dumps({"k": "cg", "t": round(now, 4), "c": name, **s}) + "\n")
            if mono >= next_threads:
                for name, (cg, pid) in found.items():
                    if pid:
                        out.write(json.dumps({"k": "th", "t": round(now, 3), "c": name, "pid": pid,
                                              "th": threads(pid)}) + "\n")
                next_threads = mono + a.threads_every
            tick += a.interval
            time.sleep(max(0.0, tick - time.monotonic()))


if __name__ == "__main__":
    main()
