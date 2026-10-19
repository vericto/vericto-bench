# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Counters, the traffic-cap guard and the CPU/steal accounting of a cell.

One `hostmon sample` per host streams cumulative counters once a second; this
module pipes every stream into one `hostmon guard`, which applies the caps
(per component 400 Mbps hard / 300 target, aggregate 800 hard / 600 target)
and writes the stop file on a breach. The same bytes are counted at every
interface they cross (owner rule), so components share counters on purpose.
"""
from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime

from . import targets as TG
from . import topo as T


def components(topo: T.Topology, engine: str, target: str, ports: list[int]) -> dict[str, list[str]]:
    dbp = TG.PORTS[(engine, "direct")]
    if topo.kind == "compose":
        c = {"loadgen": ["local:netns:load:rx", "local:netns:load:tx"],
             "database": ["local:netns:db:rx", "local:netns:db:tx"],
             "telemetry": ["local:netns:cpstub:rx", "local:netns:cpstub:tx"]}
        if target != "direct":
            keys = []
            for i in range(len(ports)):
                n = "target" if i == 0 else f"target{i + 1}"
                keys += [f"local:netns:{n}:rx", f"local:netns:{n}:tx"]
            c["intermediary"] = keys
        return c
    h = "sut" if topo.kind == "two-host" else "local"
    db_lo = [f"{h}:nft:db{dbp}_lo_in", f"{h}:nft:db{dbp}_lo_out"]
    db_remote = [f"{h}:nft:db{dbp}_in", f"{h}:nft:db{dbp}_out"]
    listen = []
    for p in ports:
        if target != "direct":
            listen += [f"{h}:nft:p{p}_in", f"{h}:nft:p{p}_out"]
    c = {"database": db_remote + db_lo}
    if target != "direct":
        # Both hops of the intermediary and its telemetry to the stub.
        c["intermediary"] = listen + db_lo + [f"{h}:nft:cp9090_in", f"{h}:nft:cp9090_out"]
    if topo.kind == "two-host":
        c["loadgen-nic"] = ["loadgen:iface:default:rx", "loadgen:iface:default:tx"]
        c["sut-nic"] = ["sut:iface:default:rx", "sut:iface:default:tx"]
    else:
        c["client"] = listen if target != "direct" else db_lo
    return c


def sampler_cmd(topo: T.Topology, host: T.Host, images, label: str, cgroups: dict[str, str],
                netns: dict[str, int], nft: bool) -> list[str]:
    cmd = host.docker_cmd() + ["run", "--rm", "-i", "--name", f"vb-mon-{label}", "--label", f"{T.LABEL}={topo.run_label}",
                               "--network", "host", "--pid", "host", "--privileged",
                               "-v", "/sys/fs/cgroup:/host/cgroup:ro"]
    cpu = host.cpuset("CPU_AUX") or host.cpuset("CPU_OS")
    if cpu:
        cmd += ["--cpuset-cpus", cpu]
    cmd += [images.tools, "hostmon", "sample", "-host", label, "-cgroup-root", "/host/cgroup"]
    if topo.kind != "compose":
        cmd += ["-iface", "auto"]
    if nft:
        cmd += ["-nft"]
    for name, cid in cgroups.items():
        cmd += ["-cgroup-id", f"{name}={cid}"]
    for name, pid in netns.items():
        cmd += ["-netns", f"{name}={pid}"]
    return cmd


class Guard:
    """hostmon guard fed by the samplers' stdout."""

    def __init__(self, topo: T.Topology, images, cell_dir_local: str, cell_dir_data: str, stop_data: str,
                 comps: dict, caps: dict | None):
        self.topo = topo
        self.local = cell_dir_local
        with open(f"{cell_dir_local}/components.json", "w") as f:
            json.dump(comps, f, indent=2)
        args = ["run", "--rm", "-i", "--name", f"vb-guard-{abs(hash(cell_dir_local)) % 10**8}",
                "--label", f"{T.LABEL}={topo.run_label}"] + topo.data_mount()
        args += [images.tools, "hostmon", "guard", "-stdin", "-components", f"{cell_dir_data}/components.json",
                 "-stop-file", stop_data, "-out", f"{cell_dir_data}/net.jsonl", "-raw", f"{cell_dir_data}/samples.jsonl",
                 "-summary", f"{cell_dir_data}/net-summary.json"]
        if caps:
            with open(f"{cell_dir_local}/caps.json", "w") as f:
                json.dump(caps, f)
            args += ["-caps", f"{cell_dir_data}/caps.json"]
        self.proc = subprocess.Popen(topo.loadgen.docker_cmd() + args, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=open(f"{cell_dir_local}/guard.log", "wb"))
        self.samplers: list[subprocess.Popen] = []
        self.lock = threading.Lock()
        self.threads: list[threading.Thread] = []

    def add_sampler(self, cmd: list[str], log: str):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=open(log, "wb"))
        self.samplers.append(p)
        t = threading.Thread(target=self._pump, args=(p,), daemon=True)
        t.start()
        self.threads.append(t)

    def _pump(self, p: subprocess.Popen):
        for line in p.stdout:
            with self.lock:
                try:
                    self.proc.stdin.write(line)
                    self.proc.stdin.flush()
                except (BrokenPipeError, ValueError):
                    return

    def aborted(self) -> bool:
        return self.proc.poll() == 9

    def stop(self) -> dict:
        for p in self.samplers:
            p.terminate()
        for h in self.topo.hosts():
            ids = h.docker("ps", "-q", "--filter", f"label={T.LABEL}={self.topo.run_label}", "--filter", "name=vb-mon-",
                           check=False).stdout.decode().split()
            if ids:
                h.docker("kill", *ids, check=False)
        for t in self.threads:
            t.join(timeout=10)
        with self.lock:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
        out = b""
        timer = threading.Timer(30, self.proc.kill)
        timer.start()
        try:
            out = self.proc.stdout.read()
            self.proc.wait()
        finally:
            timer.cancel()
        for line in out.decode(errors="replace").splitlines():
            if line.startswith("HOSTMON_SUMMARY "):
                return json.loads(line.split(" ", 1)[1])
        return {"summary": None, "aborted": self.proc.returncode == 9, "reason": "no guard summary"}


def _t(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def cpu_and_steal(samples_path: str, t0: float, t1: float, budgets: dict[str, float]) -> dict:
    """vCPU used per container over [t0, t1] from cgroup usage_usec, CFS
    throttling, and steal time per host, from the guard's raw sample copy."""
    first: dict = {}
    last: dict = {}
    try:
        f = open(samples_path)
    except FileNotFoundError:
        return {}
    with f:
        for line in f:
            try:
                s = json.loads(line)
            except ValueError:
                continue
            t = _t(s["t"])
            if t < t0 or t > t1:
                continue
            host = s.get("host", "")
            for name, st in (s.get("cpu") or {}).items():
                key = (host, name)
                first.setdefault(key, (t, st))
                last[key] = (t, st)
            if s.get("stat"):
                key = (host, "__stat__")
                first.setdefault(key, (t, s["stat"]))
                last[key] = (t, s["stat"])
    out = {"containers": {}, "steal_pct": {}}
    for key, (ta, a) in first.items():
        tb, b = last[key]
        if tb <= ta:
            continue
        host, name = key
        if name == "__stat__":
            dt = b["total"] - a["total"]
            out["steal_pct"][host] = 100.0 * (b["steal"] - a["steal"]) / dt if dt > 0 else 0.0
            continue
        vcpu = (b["usage_usec"] - a["usage_usec"]) / 1e6 / (tb - ta)
        out["containers"][name] = {"host": host, "vcpu": vcpu, "seconds": tb - ta,
                                   "nr_throttled": b.get("nr_throttled", 0) - a.get("nr_throttled", 0),
                                   "throttled_ms": (b.get("throttled_usec", 0) - a.get("throttled_usec", 0)) / 1000.0,
                                   "budget_vcpu": budgets.get(name)}
    return out
