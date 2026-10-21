# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Runs a suite: setup, pre-flights, every cell, teardown, manifest."""
from __future__ import annotations

import json
import math
import os
import secrets
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from . import monitor as M
from . import suite as S
from . import targets as TG
from . import tools as TL
from . import topo as T

VBENCH_WORKLOADS_NEED = {
    "orm": "orm", "orm-oltp": "orm", "masked": "orm", "connect": "orm", "blocked-delete": "orm", "blocked-update": "orm",
    "delete-where": "orm", "update-where": "orm", "select-only": "pgbench", "sysbench-ro": "sysbench",
}
ENFORCING = ("vericto-offline", "vericto-enforce")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def read_lock(path: str) -> dict[str, str]:
    with open(path) as f:
        return T.read_env_file(f.read())


def mirror(ref: str, lock: dict[str, str]) -> str:
    m = os.environ.get("LIBRARY_MIRROR", "")
    if m and ref.startswith("docker.io/library/"):
        return m.rstrip("/") + "/" + ref[len("docker.io/library/"):]
    if ref.startswith("docker.io/vericto/vericto-proxy") and os.environ.get("PROXY_FROM_MIRROR") == "1":
        return lock["VERICTO_PROXY_MIRROR"] + "@" + ref.split("@", 1)[1]
    return ref


def pull_ref(ref: str) -> str:
    """docker run accepts name:tag@digest; keep only name@digest so the digest is what counts."""
    name, _, digest = ref.partition("@")
    if digest:
        base = name.rsplit(":", 1)[0] if ":" in name.split("/")[-1] else name
        return f"{base}@{digest}"
    return ref


class Runner:
    def __init__(self, args):
        self.args = args
        self.repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.suite = S.load(args.suite)
        self.lock = read_lock(os.path.join(self.repo, "versions.lock"))
        self.out = os.path.abspath(args.out)
        os.makedirs(self.out, exist_ok=True)
        self.run_id = os.environ.get("RUN_ID") or os.path.basename(self.out)
        self.topo = T.make(args.topology, self.out, self.run_id, args.sut_ssh)
        self.data = "/data/" + os.path.relpath(self.out, self.topo.data_local)
        proxy_ref = os.environ.get("PROXY_IMAGE_OVERRIDE") or self.lock["VERICTO_PROXY_IMAGE"]
        tag = args.image_tag
        self.images = TG.Images(
            proxy=pull_ref(mirror(proxy_ref, self.lock)), postgres=pull_ref(mirror(self.lock["POSTGRES_IMAGE"], self.lock)),
            mysql=pull_ref(mirror(self.lock["MYSQL_IMAGE"], self.lock)), haproxy=pull_ref(mirror(self.lock["HAPROXY_IMAGE"], self.lock)),
            tools=f"vericto-bench/tools:{tag}", pgbouncer=f"vericto-bench/pgbouncer:{tag}",
            proxysql=f"vericto-bench/proxysql:{tag}", sysbench=f"vericto-bench/sysbench:{tag}")
        self.proxy_ref = proxy_ref
        self._resolve_images({"proxy": proxy_ref, "postgres": self.lock["POSTGRES_IMAGE"], "mysql": self.lock["MYSQL_IMAGE"],
                              "haproxy": self.lock["HAPROXY_IMAGE"]})
        self.datasets = {"pgbench_scale": 100, "sysbench_tables": 8, "sysbench_rows": 1_000_000, "payload_rows": 10_000}
        self.datasets.update(self.suite.datasets)
        self.cells_path = os.path.join(self.out, "cells.jsonl")
        self.saturation: dict[str, float] = {}
        self.manifest: dict = {}
        self.caps = None
        if args.caps:
            with open(args.caps) as f:
                self.caps = json.load(f)
        self._check_profile()

    def _resolve_images(self, origins: dict[str, str]):
        """host/pull-images.sh falls back to the original registry when a mirror
        fails; the digest is the same, the name is not. Use the mirror name where
        every host has it, else the original name where every host has that."""
        if self.topo.kind == "compose":
            return
        for field, raw in origins.items():
            mirrored = getattr(self.images, field)
            origin = pull_ref(raw)
            if mirrored == origin:
                continue

            def everywhere(ref: str) -> bool:
                return all(h.docker("image", "inspect", "-f", "{{.Id}}", ref, check=False).returncode == 0
                           for h in self.topo.hosts())
            if not everywhere(mirrored) and everywhere(origin):
                log(f"image {field}: {mirrored} not on every host; using the same digest as {origin}")
                setattr(self.images, field, origin)

    # ---- checks -------------------------------------------------------------------

    def _check_profile(self):
        p = self.suite.profile
        if p == "published":
            if self.topo.kind == "compose":
                raise T.SetupError("profile=published cannot run on the compose topology (laptop smoke)")
            tag = self.proxy_ref.split("@")[0].rsplit(":", 1)[-1]
            if tag != self.lock["PUBLISHED_PROXY_VERSION"]:
                raise T.SetupError(f"profile=published measures vericto-proxy {self.lock['PUBLISHED_PROXY_VERSION']}; "
                                   f"versions.lock pins {tag}. Pin the released digest first.")
        if self.topo.kind == "compose" and p != "smoke":
            raise T.SetupError("the compose topology only runs profile=smoke")

    # ---- tool containers ----------------------------------------------------------

    def tool(self, image: str, args: list[str], name: str, pass_env: list[str] | None = None, env: dict | None = None,
             check: bool = True, entrypoint: str | None = None, timeout: float | None = None,
             input: bytes | None = None, as_runner: bool = False) -> subprocess.CompletedProcess:
        h = self.topo.loadgen
        cmd = h.docker_cmd() + ["run", "--rm", "-i" if input else "--init", "--name", name, "--label",
                                f"{T.LABEL}={self.run_id}", "--network", h.network] + self.topo.data_mount()
        if as_runner and self.topo.kind != "compose":
            # Files this container writes must be readable (and removable) by the
            # runner, which runs as an unprivileged user on EC2 (bench), e.g. the
            # run's 0600 TLS key. Compose: the runner is root in its container.
            cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
        if h.cpuset("CPU_LOADGEN"):
            cmd += ["--cpuset-cpus", h.cpuset("CPU_LOADGEN")]
        for k in pass_env or []:
            cmd += ["-e", k]
        for k, v in (env or {}).items():
            cmd += ["-e", f"{k}={v}"]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        cmd += [image] + args
        return T.run(cmd, check=check, timeout=timeout, input=input)

    def addr(self, engine: str, target: str) -> tuple[str, list[int], int]:
        """(host, ports, db port) a client uses for a target."""
        if target == "direct":
            host = T.addr(self.topo, self.topo.sut, TG.DB_NAME[engine])
            p = TG.PORTS[(engine, "direct")]
            return host, [p], p
        name = f"vb-{engine}-{target}"
        host = T.addr(self.topo, self.topo.sut, name)
        return host, [TG.port(engine, target)], TG.PORTS[(engine, "direct")]

    # ---- setup --------------------------------------------------------------------

    def engines(self) -> list[str]:
        return sorted({c.engine for c in self.suite.curves})

    def setup(self):
        os.environ["DB_PASSWORD"] = os.environ.get("DB_PASSWORD") or secrets.token_urlsafe(18)
        for k in ("POSTGRES_PASSWORD", "MYSQL_PASSWORD", "PGPASSWORD"):
            os.environ[k] = os.environ["DB_PASSWORD"]
        os.environ["MYSQL_ROOT_PASSWORD"] = os.environ.get("MYSQL_ROOT_PASSWORD") or secrets.token_urlsafe(18)
        os.environ["MYSQL_PWD"] = os.environ["MYSQL_ROOT_PASSWORD"]
        T.cleanup(self.topo)
        self.write_manifest(stage="setup")
        log(f"run {self.run_id}: suite {self.suite.name} (profile {self.suite.profile}), topology {self.topo.kind}")
        names = "localhost,127.0.0.1," + ",".join(TG.DB_NAME.values()) + f",{self.topo.sut.address or 'vb'}"
        self.tool(self.images.tools, ["vbench", "certs", "-out", f"{self.data}/certs", "-names", names], "vb-certs",
                  as_runner=True)
        self.certs = {n: open(os.path.join(self.out, "certs", n), "rb").read() for n in ("ca.crt", "server.crt", "server.key")}
        tuning = TG.db_tuning(self.suite.profile, self.suite.database)
        self.db = {}
        for e in self.engines():
            log(f"starting {e} database")
            self.db[e] = TG.start_db(self.topo, self.images, e, tuning, self.certs)
        for e in self.engines():
            self.wait_ready(e, "direct", timeout=240)
        if "mysql" in self.db:
            pw = os.environ["DB_PASSWORD"].replace("'", "")
            sql = (f"ALTER USER 'bench'@'%' IDENTIFIED WITH mysql_native_password BY '{pw}';\n"
                   "GRANT ALL PRIVILEGES ON *.* TO 'bench'@'%';\nFLUSH PRIVILEGES;\n").encode()
            self.topo.sut.docker("exec", "-i", "-e", "MYSQL_PWD", TG.DB_NAME["mysql"], "mysql", "-uroot", input=sql)
        self.seed()
        self.cpstub = TG.start_cpstub(self.topo, self.images)
        self.verdict_preflight()
        self.write_manifest(stage="running")

    def wait_ready(self, engine: str, target: str, timeout: float = 90, expect_enforce: bool | None = None,
                   tls: bool = False):
        host, ports, _ = self.addr(engine, target)
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            args = ["vbench", "probe" if expect_enforce is not None else "scalar", "-engine", engine, "-host", host,
                    "-port", str(ports[0]), "-user", "bench", "-db", "bench", "-tls", "require" if tls else "disable"]
            if expect_enforce is None:
                args += ["-sql", "SELECT 1"]
            else:
                args += ["-workload", "blocked-delete", "-target", target] + (["-expect-enforce"] if expect_enforce else [])
            p = self.tool(self.images.tools, args, f"vb-wait-{engine}", pass_env=["DB_PASSWORD"], check=False, timeout=60)
            if p.returncode == 0:
                return p.stdout.decode()
            last = (p.stdout + p.stderr).decode(errors="replace")[-300:]
            if p.returncode == 5:
                raise T.SetupError(f"{engine}/{target}: probe verdict disagrees: {last}")
            time.sleep(2)
        raise T.SetupError(f"{engine}/{target} not ready after {timeout:.0f} s: {last}")

    def needed(self) -> dict[str, set]:
        need = {e: {"orm"} for e in self.engines()}
        for c in self.suite.curves:
            if c.tool == "pgbench":
                need[c.engine].add("pgbench")
            elif c.tool == "sysbench":
                need[c.engine].add("sysbench")
            elif c.workload.startswith("payload-"):
                need[c.engine].add("payload")
            elif c.workload in VBENCH_WORKLOADS_NEED:
                need[c.engine].add(VBENCH_WORKLOADS_NEED[c.workload])
        return need

    def vb(self, engine: str, *args: str, timeout: float = 3600) -> str:
        host, ports, _ = self.addr(engine, "direct")
        p = self.tool(self.images.tools, ["vbench", args[0], "-engine", engine, "-host", host, "-port", str(ports[0]),
                                          "-user", "bench", "-db", "bench", "-tls", "disable", *args[1:]],
                      f"vb-{args[0]}-{engine}", pass_env=["DB_PASSWORD"], timeout=timeout)
        return p.stdout.decode()

    def seed(self):
        d = self.datasets
        checks = {}
        for engine, sets in self.needed().items():
            host, ports, _ = self.addr(engine, "direct")
            for ds in ["orm", "payload", "pgbench", "sysbench"]:
                if ds not in sets:
                    continue
                t0 = time.time()
                log(f"seeding {engine}/{ds}")
                if ds == "pgbench":
                    self.tool(self.images.postgres, ["pgbench", "-i", "-q", "-s", str(d["pgbench_scale"]), "-h", host,
                                                     "-p", str(ports[0]), "-U", "bench", "bench"],
                              "vb-seed-pgbench", pass_env=["PGPASSWORD"], env={"PGSSLMODE": "disable"}, timeout=7200)
                elif ds == "sysbench" and engine == "mysql":
                    self.tool(self.images.sysbench, ["-c", 'exec sysbench "$@" --mysql-password="$DB_PASSWORD"', "sb",
                                                     "oltp_read_only", "--db-driver=mysql", f"--mysql-host={host}",
                                                     f"--mysql-port={ports[0]}", "--mysql-user=bench", "--mysql-db=bench",
                                                     "--mysql-ssl=off", f"--tables={d['sysbench_tables']}",
                                                     f"--table-size={d['sysbench_rows']}", "--rand-seed=1", "prepare"],
                              "vb-seed-sysbench", pass_env=["DB_PASSWORD"], entrypoint="sh", timeout=7200)
                else:
                    self.vb(engine, "seed", "-dataset", ds, "-pgbench-scale", str(d["pgbench_scale"]),
                            "-sysbench-tables", str(d["sysbench_tables"]), "-sysbench-rows", str(d["sysbench_rows"]),
                            "-payload-rows", str(d["payload_rows"]))
                out = self.vb(engine, "checksum", "-dataset", ds)
                val = json.loads(out.split("VBENCH_CHECKSUM ", 1)[1].splitlines()[0])["value"]
                checks[f"{engine}/{ds}"] = {"checksum": val, "seconds": round(time.time() - t0, 1)}
        self.manifest["datasets"] = {"sizes": d, "checksums": checks}

    def verdict_preflight(self):
        """Every vbench workload's declared verdicts against engine-eval (the
        same engine and 42 rules as the proxy). A disagreement stops the run."""
        lines = []
        for c in self.suite.curves:
            if c.tool != "vbench" or c.workload == "connect":
                continue
            lines.append(f"vbench dump -engine {c.engine} -mode {c.mode or ('extended' if c.engine == 'pg' else 'text')} "
                         f"-workload {c.workload} -pgbench-scale {self.datasets['pgbench_scale']} "
                         f"-sysbench-rows {self.datasets['sysbench_rows']} -payload-rows {self.datasets['payload_rows']}")
        if not lines:
            return
        script = "set -e; (" + "; ".join(lines) + f") > {self.data}/statements.jsonl; " \
                 f"engine-eval verdicts {self.data}/statements.jsonl --sensitive /opt/vericto-bench/sensitive.json > {self.data}/verdicts.jsonl"
        p = self.tool(self.images.tools, ["-c", script], "vb-verdicts", entrypoint="sh", check=False)
        if p.returncode != 0:
            raise T.SetupError(f"verdict pre-flight failed: see {self.out}/verdicts.jsonl")
        log("verdict pre-flight: every declared verdict matches engine-eval")

    # ---- cells ----------------------------------------------------------------------

    def start_targets(self, cell) -> list[T.Container]:
        c = cell.curve
        out = []
        n = 2 if (c.size == "2x0.5" and cell.target.startswith("vericto")) else 1
        for i in range(n):
            t = TG.start_target(self.topo, self.images, c.engine, cell.target, c.size, c.tls, self.certs, second=i == 1)
            if t:
                out.append(t)
        return out

    def ports_for(self, cell) -> tuple[list[str], list[int]]:
        """Hosts and ports of the target's tasks (two for 2x0.5). On host
        networking both tasks share the SUT's address; in compose the second
        task is its own container."""
        host, ports, _ = self.addr(cell.curve.engine, cell.target)
        hosts = [host]
        if cell.curve.size == "2x0.5" and cell.target.startswith("vericto"):
            ports = [ports[0], TG.PORTS[(cell.curve.engine, "vericto2")]]
            hosts.append(T.addr(self.topo, self.topo.sut, f"vb-{cell.curve.engine}-{cell.target}-2"))
        return hosts, ports

    def run_cell(self, cell, attempt: str = "") -> dict:
        c = cell.curve
        cid = cell.id + attempt
        local = os.path.join(self.out, "cells", cid)
        data = f"{self.data}/cells/{cid}"
        os.makedirs(local, exist_ok=True)
        stop_local = os.path.join(local, "STOP")
        stop_data = f"{data}/STOP"
        rec = {"cell": cid, "curve": c.id, "engine": c.engine, "tool": c.tool, "arrival": c.arrival, "workload": c.workload, "mode": c.mode,
               "tls": c.tls, "size": c.size, "target": cell.target, "loop": c.loop, "offered_rate": cell.rate,
               "rate_pct": cell.pct, "conc": cell.conc, "rep": cell.rep, "seq": cell.seq, "day": self.args.day,
               "started_at": now_iso(), "invalid_reasons": [], "warnings": []}
        log(f"cell {cid}")
        targets = []
        try:
            targets = self.start_targets(cell)
            hosts, ports = self.ports_for(cell)
            if cell.target != "direct":
                self.wait_ready(c.engine, cell.target, timeout=120, expect_enforce=cell.target in ENFORCING, tls=c.tls)
                if len(ports) > 1:
                    self._wait_port(c.engine, hosts[1], ports[1], c.tls)
            if cell.target in ("vericto-enforce", "vericto-observe"):
                st = TG.cpstub_get(self.topo, "/stats")
                key = ("observe" if cell.target == "vericto-observe" else "enforce") + f"-{c.engine}"
                rec["cpstub_syncs_before"] = st.get("syncs")
                if not st.get("syncs"):
                    raise T.SetupError(f"{cid}: the proxy never synced with cpstub")
                TG.cpstub_get(self.topo, "/reset", post=True)
            rec.update(self._load(cell, cid, local, data, stop_local, stop_data, hosts, ports, targets))
            if cell.target in ("vericto-enforce", "vericto-observe"):
                time.sleep(6)  # one telemetry flush interval (5 s) so the cell's events reach the stub
                rec["cpstub"] = TG.cpstub_get(self.topo, "/stats")
        except T.SetupError as e:
            rec["status"] = "aborted"
            rec["reason"] = f"setup: {e}"[:600]
            rec["invalid_reasons"].append("setup failure")
        finally:
            for t in targets:
                t.logs(os.path.join(local, f"{t.name}.log"))
                t.remove()
        rec["finished_at"] = now_iso()
        self._cooldown(c.engine, rec)
        self._validity(rec)
        with open(self.cells_path, "a") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        log(f"  -> {rec.get('status')} {rec.get('reason', '')} achieved {rec.get('achieved_rate', 0):.1f}/s "
            f"p50 {rec.get('latency', {}).get('p50_ms')} p99 {rec.get('latency', {}).get('p99_ms')} "
            f"{'INVALID ' + ','.join(rec['invalid_reasons']) if rec['invalid_reasons'] else ''}")
        return rec

    def _wait_port(self, engine, host, port, tls):
        deadline = time.time() + 60
        while time.time() < deadline:
            p = self.tool(self.images.tools, ["vbench", "scalar", "-engine", engine, "-host", host, "-port", str(port),
                                              "-user", "bench", "-db", "bench", "-tls", "require" if tls else "disable",
                                              "-sql", "SELECT 1"], "vb-wait2", pass_env=["DB_PASSWORD"], check=False)
            if p.returncode == 0:
                return
            time.sleep(2)
        raise T.SetupError(f"second task on {port} not ready")

    def _load(self, cell, cid, local, data, stop_local, stop_data, hosts, ports, targets) -> dict:
        c = cell.curve
        lg = self.topo.loadgen
        name = f"vb-load-{cell.seq}"
        lg.docker("rm", "-f", name, check=False)
        cmd = ["create", "--init", "--name", name, "--label", f"{T.LABEL}={self.run_id}", "--network", lg.network] + self.topo.data_mount()
        if lg.cpuset("CPU_LOADGEN"):
            cmd += ["--cpuset-cpus", lg.cpuset("CPU_LOADGEN")]
        threads = len(_cpus(lg.cpuset("CPU_LOADGEN"))) or 2
        warmup = c.warmup_s if c.warmup_s is not None else self.suite.warmup_s
        duration = c.duration_s if c.duration_s is not None else self.suite.duration_s
        if c.tool == "vbench":
            cmd += ["-e", "DB_PASSWORD", self.images.tools] + TL.vbench_args(cell, hosts, ports, f"{data}/load", stop_data,
                                                                             self.suite, self.datasets)
        elif c.tool == "pgbench":
            os.makedirs(os.path.join(local, "pgbench"), exist_ok=True)
            args, env = TL.pgbench_args(cell, hosts, ports, f"{data}/pgbench/tx", self.suite, threads)
            for k, v in env.items():
                cmd += ["-e", f"{k}={v}"]
            cmd += ["-e", "PGPASSWORD", self.images.postgres] + args
        else:
            cmd += ["-e", "DB_PASSWORD", "--entrypoint", "sh", self.images.sysbench, "-c",
                    'exec sysbench "$@" --mysql-password="$DB_PASSWORD"', "sb"] + TL.sysbench_args(cell, hosts, ports, self.suite, self.datasets)
        T.run(lg.docker_cmd() + cmd)
        load = T.Container(lg, name)
        comps = M.components(self.topo, c.engine, cell.target, ports if cell.target != "direct" else [])
        guard = M.Guard(self.topo, self.images, local, data, stop_data, comps, self.caps)
        t_start = time.time()
        proc = subprocess.Popen(lg.docker_cmd() + ["start", "-a", name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(0.3)
        self._samplers(guard, load, targets, c.engine)
        pauser = None
        if c.pause_every_s > 0:
            pauser = _Pauser(self.topo.sut, TG.DB_NAME[c.engine], c.pause_every_s, c.pause_s, warmup)
            pauser.start()
        killed = False
        while proc.poll() is None:
            if guard.aborted() and c.tool != "vbench" and not killed:
                lg.docker("kill", name, check=False)  # pgbench/sysbench cannot watch the stop file
                killed = True
            time.sleep(0.5)
        output = proc.stdout.read().decode(errors="replace")
        t_end = time.time()
        if pauser:
            pauser.stop()
        with open(os.path.join(local, "load.log"), "w") as f:
            f.write(output)
        net = guard.stop()
        load.remove()
        rec: dict = {"exit_code": proc.returncode, "net": net.get("summary"), "net_aborted": bool(net.get("aborted"))}
        if c.tool == "vbench":
            try:
                with open(os.path.join(local, "load", "result.json")) as f:
                    r = json.load(f)
            except FileNotFoundError:
                r = {"status": "aborted", "reason": f"vbench exit {proc.returncode}: {output[-300:]}"}
            rec.update({k: r.get(k) for k in ("status", "reason", "offered_rate", "achieved_rate", "statements_per_s",
                                               "scheduled", "completed", "incomplete", "unsent", "errors", "blocked",
                                               "latency", "latency_all", "service", "queue_wait", "gen_lag", "classes",
                                               "measure_from", "end", "client", "invalid", "error_samples", "conns", "latency_scope",
                                               "sent_total", "scheduled_total")})
            rec["intervals"] = f"cells/{cid}/load/intervals.jsonl"
            rec["hlog"] = f"cells/{cid}/load/latency.hlog"
        elif c.tool == "pgbench":
            r, ints = TL.parse_pgbench(os.path.join(local, "pgbench", "tx"), warmup, duration, self.suite.interval_s,
                                       cell.rate if c.loop == "open" else 0.0)
            with open(os.path.join(local, "intervals.jsonl"), "w") as f:
                for i in ints:
                    f.write(json.dumps(i) + "\n")
            r["summary"] = TL.parse_pgbench_summary(output)
            # The per-transaction logs stay in the raw data, compressed (one
            # line per transaction: tens of MB per cell, hundreds of cells a day).
            r["pgbench_logs"] = TL.gzip_logs(os.path.join(local, "pgbench", "tx"))
            if proc.returncode != 0 and r.get("status") == "ok":
                r["status"], r["reason"] = "aborted", f"pgbench exit {proc.returncode}"
            if r["summary"].get("clients_aborted"):
                r["errors"] = max(r.get("errors", 0), 1)
            rec.update(r)
            rec["intervals"] = f"cells/{cid}/intervals.jsonl"
        else:
            r = TL.parse_sysbench(output, duration, warmup)
            rec.update(r)
        if rec["net_aborted"]:
            rec["status"] = "aborted"
            rec["reason"] = "network cap: " + str(net.get("reason"))
        mfrom = _ts(rec.get("measure_from")) or (t_start + warmup)
        mend = _ts(rec.get("end")) or (t_start + warmup + duration)
        budgets = {"target": 1.0 if c.size == "1" else 0.5, "target2": 0.5}
        rec["cpu"] = M.cpu_and_steal(os.path.join(local, "samples.jsonl"), mfrom, mend, budgets)
        rec["wall_s"] = t_end - t_start
        if pauser:
            frac = fraction_above(os.path.join(self.out, rec["intervals"]), 500_000) if rec.get("intervals") else None
            rec["validation"] = pauser.verdict(rec, frac)
        return rec

    def _samplers(self, guard: M.Guard, load: T.Container, targets: list[T.Container], engine: str):
        topo = self.topo
        db = self.db[engine]
        if topo.kind == "compose":
            netns = {"load": load.pid(), "db": db.pid(), "cpstub": self.cpstub.pid()}
            cg = {"load": load.id or _cid(load), "db": db.id, "cpstub": self.cpstub.id}
            for i, t in enumerate(targets):
                netns["target" if i == 0 else f"target{i + 1}"] = t.pid()
                cg["target" if i == 0 else f"target{i + 1}"] = t.id
            guard.add_sampler(M.sampler_cmd(topo, topo.loadgen, self.images, "local", cg, netns, nft=False),
                              os.path.join(guard.local, "sampler-local.log"))
            return
        sut_cg = {"db": db.id, "cpstub": self.cpstub.id}
        for i, t in enumerate(targets):
            sut_cg["target" if i == 0 else f"target{i + 1}"] = t.id
        if topo.kind == "single":
            sut_cg["load"] = _cid(load)
            guard.add_sampler(M.sampler_cmd(topo, topo.sut, self.images, "local", sut_cg, {}, nft=True),
                              os.path.join(guard.local, "sampler-local.log"))
            return
        guard.add_sampler(M.sampler_cmd(topo, topo.sut, self.images, "sut", sut_cg, {}, nft=True),
                          os.path.join(guard.local, "sampler-sut.log"))
        guard.add_sampler(M.sampler_cmd(topo, topo.loadgen, self.images, "loadgen", {"load": _cid(load)}, {}, nft=False),
                          os.path.join(guard.local, "sampler-loadgen.log"))

    def _cooldown(self, engine: str, rec: dict):
        time.sleep(self.suite.cooldown_s)
        q = ("SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND state <> 'idle' "
             "AND pid <> pg_backend_pid()") if engine == "pg" else \
            ("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE COMMAND NOT IN ('Sleep', 'Daemon') "
             "AND ID <> CONNECTION_ID()")
        try:
            out = self.vb(engine, "scalar", "-sql", q, timeout=60)
            active = int(float(json.loads(out.split("VBENCH_SCALAR ", 1)[1].splitlines()[0])["value"]))
        except (T.SetupError, IndexError, ValueError):
            active = -1
        rec["idle_check"] = {"active_sessions": active}
        if active != 0:
            rec["warnings"].append(f"database not idle after cool-down ({active} active sessions)")

    def _validity(self, rec: dict):
        """Pre-registered validity rules (design section 8). Outliers are never
        removed; a repetition is invalid only for one of these reasons."""
        inv = rec["invalid_reasons"]
        done = rec.get("completed") or 0
        errs = rec.get("errors") or 0
        if done and errs / max(done, 1) > 0.001:
            inv.append(f"errors {errs} of {done} (> 0.1%)")
        if rec.get("invalid"):
            inv.append(str(rec["invalid"]))
        cpu = rec.get("cpu") or {}
        for host, st in (cpu.get("steal_pct") or {}).items():
            if st > 1.0:
                inv.append(f"steal {st:.2f}% on {host}")
        lg = self.topo.loadgen
        ncpu = len(_cpus(lg.cpuset("CPU_LOADGEN"))) or os.cpu_count() or 1
        load = (cpu.get("containers") or {}).get("load")
        if load and load["vcpu"] > 0.7 * ncpu:
            inv.append(f"client CPU {load['vcpu']:.2f} of {ncpu} cores (> 70%)")
        for name, st in (cpu.get("containers") or {}).items():
            has_quota = name.startswith("target") and rec.get("size") != "1"
            if not has_quota and st.get("nr_throttled", 0) > 0 and self.topo.kind != "compose":
                inv.append(f"{name} throttled {st['nr_throttled']} times without a quota")
        if rec.get("status") != "aborted" and rec.get("intervals"):
            poisson = rec.get("tool") == "pgbench" or rec.get("arrival") == "poisson"
            steady = steady_state(os.path.join(self.out, rec["intervals"]), rec.get("offered_rate") or 0, poisson)
            rec["steady"] = steady
            # A saturated cell is the end of its curve by construction (design
            # section 8: kept in the raw data, never a latency figure), so its
            # unsteady rate is expected, not a reason to invalidate and rerun it.
            if steady.get("flag") and rec.get("status") != "saturated":
                inv.append("not steady: " + steady["flag"])
        if self.suite.profile == "smoke":
            rec["smoke"] = True

    # ---- curves ---------------------------------------------------------------------

    def run_curve(self, curve: S.Curve):
        cells = S.expand(self.suite, curve, self.saturation)
        max_rate = math.inf
        if curve.loop == "open" and curve.pause_every_s == 0:
            max_rate = self.net_preflight(curve, cells)
        capped_at = math.inf
        stopped: set = set()
        prev: dict = {}
        best: dict = {}
        invalid = []
        for cell in cells:
            if curve.loop == "open" and cell.rate > max_rate:
                self._skip(cell, f"not run: above the traffic design targets (pre-flight: at most {max_rate:.0f}/s fits "
                                 f"300 Mbps per component and 600 Mbps aggregate); the curve stops at the cap")
                continue
            if curve.loop == "open" and cell.rate >= capped_at:
                self._skip(cell, f"not run: the curve stopped at the traffic cap at {capped_at:g}/s")
                continue
            key = (cell.rep, cell.target)
            if curve.loop == "closed" and key in stopped:
                continue
            rec = self.run_cell(cell)
            if rec.get("net_aborted"):
                capped_at = min(capped_at, cell.rate if curve.loop == "open" else math.inf)
                if curve.loop == "closed":
                    stopped.add(key)
            elif rec["invalid_reasons"] and not rec.get("reason", "").startswith("setup"):
                invalid.append(cell)
            if curve.loop == "closed":
                ach = rec.get("statements_per_s") or rec.get("achieved_rate") or 0
                if key in prev and prev[key] > 0 and ach < prev[key] * 1.03:
                    stopped.add(key)  # less than 3% more per doubling: past the knee
                prev[key] = ach
                if cell.target == "vericto-enforce":
                    r = rec.get("achieved_rate") or 0
                    best[cell.rep] = max(best.get(cell.rep, 0), r)
        # One rerun of an invalid repetition; the original stays in the raw data.
        # Not in smoke runs: their seconds-long cells on a shared laptop are
        # expected to fail the steady-state rule, and they prove the pipeline only.
        for cell in invalid if self.suite.profile != "smoke" else []:
            self.run_cell(cell, attempt=".rerun")
        if curve.loop == "closed" and best:
            self.saturation[curve.id] = statistics.mean(best.values())
            log(f"curve {curve.id}: S(vericto-enforce) = {self.saturation[curve.id]:.0f}/s")
            # Recorded in full: day 2 runs the same absolute rates (suites/day2.toml).
            self.manifest.setdefault("saturation", {})[curve.id] = self.saturation[curve.id]

    def engine_only(self):
        """Evaluation only (vantage point 1 of the blocked-statement cost, and
        the evaluation-cost figure): engine-eval over every statement of the
        suite's vbench workloads, on the proxy's core, at each size."""
        cfg = self.suite.engine_eval
        h = self.topo.sut
        for size in cfg.get("sizes", ["0.5", "1"]):
            name = f"vb-engine-eval-{size}"
            out = f"{self.data}/engine-eval-{size}.jsonl"
            args = ["run", "--rm", "--name", name, "--label", f"{T.LABEL}={self.run_id}", "--network", "none"]
            if h.cpuset("CPU_PROXY"):
                args += ["--cpuset-cpus", h.cpuset("CPU_PROXY")]
            if size == "0.5":
                args += ["--cpus", "0.5"]
            args += ["-e", f"ITERS={cfg.get('iters', 20000)}", "-e", f"BUDGET_SECS={cfg.get('budget_s', 20)}",
                     "-e", f"MIN_ITERS={cfg.get('min_iters', 1000)}", "-i", self.images.tools,
                     "sh", "-c", "cat > /tmp/s.jsonl && engine-eval bench /tmp/s.jsonl --sensitive /opt/vericto-bench/sensitive.json"]
            with open(os.path.join(self.out, "statements.jsonl"), "rb") as f:
                stmts = f.read()
            n = stmts.count(b"\n")
            log(f"engine-eval at {size} vCPU ({n} statements)")
            p = h.docker(*args, input=stmts, check=False, timeout=7200)
            with open(os.path.join(self.out, f"engine-eval-{size}.jsonl"), "wb") as f:
                f.write(p.stdout)
            del out

    def _skip(self, cell, why: str):
        rec = {"cell": cell.id, "curve": cell.curve.id, "target": cell.target, "offered_rate": cell.rate, "rep": cell.rep,
               "status": "not_run", "reason": why, "invalid_reasons": [], "engine": cell.curve.engine}
        with open(self.cells_path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def net_preflight(self, curve: S.Curve, cells: list):
        """10-s probe at a low rate through the curve's heaviest target, then the
        expected traffic of every rate: refuse the curve if a component would
        pass 300 Mbps or the aggregate 600 Mbps (owner rule: reduce the rates,
        never the margin)."""
        heavy = "vericto-enforce" if "vericto-enforce" in curve.targets else curve.targets[-1]
        rates = sorted({c.rate for c in cells})
        probe_rate = max(1.0, min(rates[0], 50.0))
        probe = S.Cell(curve, 0, heavy, probe_rate, 0, None, seq=10_000 + len(self.manifest.get("netprobes", {})))
        saved = (curve.warmup_s, curve.duration_s)
        curve.warmup_s, curve.duration_s = 2.0, 10.0
        try:
            rec = self.run_cell(probe, attempt=".netprobe")
        finally:
            curve.warmup_s, curve.duration_s = saved
        if rec.get("status") == "aborted" or not rec.get("net"):
            raise T.SetupError(f"network pre-flight probe of {curve.id} failed: {rec.get('reason')}")
        bytes_ = (rec.get("net") or {}).get("bytes") or {}
        # Bytes per REQUEST (the unit of the planned rates; a sysbench-ro request
        # is a 16-statement transaction). The counters cover the whole probe
        # (connection setup, warm-up, window), so divide by every request sent
        # over it (vbench sent_total); pgbench reports only the window, which
        # overstates bytes per request slightly (the safe side of the caps).
        reqs = rec.get("sent_total") or rec.get("completed") or 0
        comps = json.load(open(os.path.join(self.out, "cells", probe.id + ".netprobe", "components.json")))
        plan = {"components": comps, "cells": [{"id": f"{curve.id}@{r:g}", "rate": r,
                                                "probe": {"bytes": bytes_, "requests": reqs}} for r in rates]}
        if self.caps:
            plan["caps"] = self.caps
        pp = os.path.join(self.out, "cells", probe.id + ".netprobe", "preflight-plan.json")
        with open(pp, "w") as f:
            json.dump(plan, f, indent=2)
        p = self.tool(self.images.tools, ["hostmon", "preflight", "-plan",
                                          f"{self.data}/cells/{probe.id}.netprobe/preflight-plan.json"], "vb-preflight", check=False)
        res = p.stdout.decode()
        with open(os.path.join(self.out, "cells", probe.id + ".netprobe", "preflight.json"), "w") as f:
            f.write(res)
        self.manifest.setdefault("netprobes", {})[curve.id] = json.loads(res) if res.strip().startswith("{") else res
        if p.returncode not in (0, 1):
            raise T.SetupError(f"network pre-flight failed for {curve.id}: {(p.stdout + p.stderr).decode()[-600:]}")
        pf = json.loads(res)
        limit = min((c.get("max_rate", math.inf) for c in pf.get("cells", {}).values()), default=math.inf)
        if p.returncode == 0:
            log(f"network pre-flight {curve.id}: every rate under 300 Mbps per component and 600 Mbps aggregate")
            return math.inf
        # Owner rule: reduce the rates, never the margin. The rates that do not
        # fit are not run, and the curve is drawn as stopped at the cap.
        log(f"network pre-flight {curve.id}: rates above {limit:.0f}/s would pass a design target; they are not run")
        return limit

    # ---- run --------------------------------------------------------------------------

    def write_manifest(self, stage: str):
        m = self.manifest
        m.update({"run_id": self.run_id, "stage": stage, "profile": self.suite.profile, "suite": self.suite.name,
                  "suite_file": self.suite.raw, "order_seed": self.suite.order_seed, "topology": self.topo.kind,
                  "day": self.args.day, "versions_lock": self.lock, "proxy_image": self.proxy_ref,
                  "images": self.images.__dict__, "caps": self.caps or "default (400/300 per component, 800/600 aggregate)",
                  "harness_commit": os.environ.get("HARNESS_COMMIT") or _git(self.repo), "updated_at": now_iso()})
        m.setdefault("started_at", now_iso())
        m["hosts"] = {}
        for h in self.topo.hosts():
            info = {"env": h.env}
            ids = {}
            for img in set(self.images.__dict__.values()):
                p = h.docker("image", "inspect", "-f", "{{.Id}} {{json .RepoDigests}}", img, check=False)
                if p.returncode == 0:
                    ids[img] = p.stdout.decode().strip()
            info["images"] = ids
            prov = h.shell("cat /etc/vericto-bench/provenance.json 2>/dev/null || true", check=False).stdout.decode()
            if prov.strip().startswith("{"):
                info["provenance"] = json.loads(prov)
            m["hosts"][h.name] = info
        if self.suite.profile == "smoke":
            m["banner"] = "SMOKE RUN: NOT FOR PUBLISHED NUMBERS"
        TL.write_json(os.path.join(self.out, "manifest.json"), m)

    def run(self) -> int:
        code = 0
        try:
            self.setup()
            failed_in_a_row = 0
            for curve in self.suite.curves:
                log(f"curve {curve.id}: {curve.tool} {curve.workload} {curve.mode} tls={curve.tls} size={curve.size} "
                    f"targets={','.join(curve.targets)}")
                try:
                    self.run_curve(curve)
                    failed_in_a_row = 0
                except (S.SuiteError, T.SetupError) as e:
                    # One curve's failure (its pre-flight refused it, a target did
                    # not start) skips that curve; three in a row stop the run.
                    log(f"curve {curve.id} skipped: {e}")
                    self.manifest.setdefault("skipped_curves", {})[curve.id] = str(e)[:1500]
                    failed_in_a_row += 1
                    if failed_in_a_row >= 3:
                        raise T.SetupError(f"three curves in a row failed; last: {e}")
            if self.suite.engine_eval:
                self.engine_only()
        except T.SetupError as e:
            log(f"SETUP FAILURE: {e}")
            self.manifest["failure"] = str(e)[:2000]
            code = 3
        finally:
            for name, c in (getattr(self, "db", {}) or {}).items():
                c.logs(os.path.join(self.out, f"{c.name}.log"))
            if getattr(self, "cpstub", None):
                self.cpstub.logs(os.path.join(self.out, "vb-cpstub.log"))
            T.cleanup(self.topo)
            self.manifest["finished_at"] = now_iso()
            self.write_manifest(stage="done" if code == 0 else "failed")
            for k in (("certs", "server.key"),):
                try:
                    os.remove(os.path.join(self.out, *k))
                except OSError:
                    pass
        return code


def _report(self) -> int:
    p = self.topo.loadgen.docker("run", "--rm", "--name", "vb-report", "--label", f"{T.LABEL}={self.run_id}",
                                 *self.topo.data_mount(), f"vericto-bench/analysis:{self.args.image_tag}", self.data,
                                 check=False)
    log((p.stdout + p.stderr).decode(errors="replace").strip()[-800:])
    return 0 if p.returncode == 0 else 4


Runner.report = _report


def _git(repo: str) -> str:
    try:
        return subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, check=True).stdout.decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _cpus(spec: str) -> list[int]:
    out = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _cid(c: T.Container) -> str:
    if not c.id:
        c.id = c.host.docker("inspect", "-f", "{{.Id}}", c.name).stdout.decode().strip()
    return c.id


def _ts(s) -> float | None:
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def steady_state(intervals_path: str, offered: float, poisson: bool = False) -> dict:
    """Design section 8: the window split in parts; flagged if the achieved rate
    varies by more than 1% (coefficient of variation across parts) or the p50
    of the last third differs from the first third by more than 10%."""
    try:
        rows = [json.loads(l) for l in open(intervals_path)]
    except FileNotFoundError:
        return {}
    rows = [r for r in rows if r.get("completed")]
    if len(rows) < 3:
        return {"parts": len(rows)}
    secs = [(_ts(r["end"]) - _ts(r["start"])) or 1 for r in rows]
    rates = [r["completed"] / s for r, s in zip(rows, secs)]
    mean = statistics.mean(rates)
    cv = statistics.pstdev(rates) / mean if mean else 0
    third = max(1, len(rows) // 3)

    def p50(rs):
        counts = {}
        for r in rs:
            for v, k in r["buckets_us"] or []:
                counts[v] = counts.get(v, 0) + k
        n = sum(counts.values())
        acc = 0
        for v in sorted(counts):
            acc += counts[v]
            if acc >= n / 2:
                return v / 1000.0
        return 0.0

    a, b = p50(rows[:third]), p50(rows[-third:])
    drift = abs(b - a) / a if a else 0
    out = {"parts": len(rows), "rate_cv": cv, "p50_first_ms": a, "p50_last_ms": b, "p50_drift": drift}
    # A constant-rate schedule completes the same count per part, so 1% is the
    # rule. Poisson arrivals (pgbench -R) vary by 1/sqrt(count) per part by
    # construction: the tolerance is three of those when that is larger.
    nmin = min(r["completed"] for r in rows)
    tol = max(0.01, 3 / math.sqrt(nmin)) if poisson else 0.01
    out["rate_cv_tolerance"] = tol
    if offered and nmin >= 100 and cv > tol:
        out["flag"] = f"rate varies {cv * 100:.1f}% across parts"
    elif drift > 0.10 and a > 0.2:
        out["flag"] = f"p50 drifts {drift * 100:.0f}% from the first to the last third"
    return out


class _Pauser:
    """Generator validation: docker pause of the database for pause_s every
    every_s seconds, after the warm-up. An open-loop generator must show the
    stall in every request due during it."""

    def __init__(self, host: T.Host, container: str, every_s: float, pause_s: float, warmup: float):
        self.host, self.container, self.every, self.pause, self.warmup = host, container, every_s, pause_s, warmup
        self.ev = threading.Event()
        self.count = 0
        self.t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.t.start()

    def _loop(self):
        if self.ev.wait(self.warmup + self.every / 2):
            return
        while not self.ev.is_set():
            self.host.docker("pause", self.container, check=False)
            time.sleep(self.pause)
            self.host.docker("unpause", self.container, check=False)
            self.count += 1
            if self.ev.wait(self.every - self.pause):
                return

    def stop(self):
        self.ev.set()
        self.t.join(timeout=self.pause + 5)
        self.host.docker("unpause", self.container, check=False)

    def verdict(self, rec: dict, fraction_above_500ms: float | None) -> dict:
        lat = rec.get("latency") or {}
        expected = max(0.0, (self.pause - 0.5) / self.every)
        out = {"pauses": self.count, "pause_s": self.pause, "every_s": self.every,
               "expected_fraction_above_500ms": expected, "observed_fraction_above_500ms": fraction_above_500ms,
               "max_ms": lat.get("max_ms"), "p999_ms": lat.get("p999_ms")}
        ok = self.count > 0 and (lat.get("max_ms") or 0) >= 0.8 * self.pause * 1000
        if fraction_above_500ms is not None and expected > 0:
            ok = ok and 0.5 * expected <= fraction_above_500ms <= 2.0 * expected
        out["pass"] = bool(ok)
        return out


def fraction_above(intervals_path: str, us: int) -> float | None:
    try:
        rows = [json.loads(l) for l in open(intervals_path)]
    except FileNotFoundError:
        return None
    total = above = 0
    for r in rows:
        for v, k in r["buckets_us"] or []:
            total += k
            if v > us:
                above += k
    return above / total if total else None
