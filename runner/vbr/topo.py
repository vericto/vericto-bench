# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Hosts and containers.

Every component runs in a container, so the same code drives three topologies:

- ``two-host`` (published numbers): the load generator host runs this runner
  and the load tools; the system-under-test host runs the databases, the
  intermediaries and cpstub, driven over ``docker -H ssh://bench@SUT``.
  Host networking, cpusets from /etc/vericto-bench/host.env.
- ``single``: one host, everything over loopback (a cheaper reproduction; not
  the published topology).
- ``compose``: the laptop smoke. The runner is itself a container with the
  Docker socket; components share the compose network and are addressed by
  name; no cpusets. NOT FOR PUBLISHED NUMBERS.
"""
from __future__ import annotations

import io
import os
import shlex
import subprocess
import tarfile
import time
from dataclasses import dataclass, field

LABEL = "vericto-bench.run"


class SetupError(RuntimeError):
    pass


def run(cmd: list[str], check: bool = True, input: bytes | None = None, timeout: float | None = None,
        env: dict | None = None) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, input=input, capture_output=True, timeout=timeout, env=env)
    if check and p.returncode != 0:
        raise SetupError(f"{shlex.join(cmd[:6])}... exit {p.returncode}: {p.stderr.decode(errors='replace')[-800:]}")
    return p


@dataclass
class Host:
    name: str  # "loadgen" | "sut" | "local"
    docker_host: str  # "" = local daemon, else ssh://bench@ip
    network: str  # "host" or a compose network name
    address: str  # how clients reach services on this host
    env: dict[str, str] = field(default_factory=dict)  # /etc/vericto-bench/host.env
    ssh: str = ""  # bench@ip for remote shell commands

    def docker_cmd(self) -> list[str]:
        return ["docker"] + (["-H", self.docker_host] if self.docker_host else [])

    def docker(self, *args: str, check: bool = True, input: bytes | None = None, timeout: float | None = None):
        return run(self.docker_cmd() + list(args), check=check, input=input, timeout=timeout)

    def shell(self, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        if self.ssh:
            return run(["ssh", "-o", "BatchMode=yes", self.ssh, cmd], check=check)
        return run(["sh", "-c", cmd], check=check)

    def cpuset(self, key: str) -> str:
        return self.env.get(key, "")


def read_env_file(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass
class Topology:
    kind: str
    loadgen: Host
    sut: Host
    data_source: str  # what `-v SRC:/data` mounts in every tool container
    data_local: str  # where this runner sees /data
    run_label: str

    def hosts(self) -> list[Host]:
        return [self.loadgen] if self.loadgen is self.sut else [self.loadgen, self.sut]

    def data_mount(self) -> list[str]:
        return ["-v", f"{self.data_source}:/data"]


def make(kind: str, out_dir: str, run_id: str, sut_ssh: str = "") -> Topology:
    out_dir = os.path.abspath(out_dir)
    if kind == "compose":
        net = os.environ.get("VBENCH_NETWORK")
        vol = os.environ.get("VBENCH_DATA_VOLUME")
        if not net or not vol:
            raise SetupError("compose topology needs VBENCH_NETWORK and VBENCH_DATA_VOLUME (set by compose/smoke.yml)")
        h = Host("local", "", net, "")
        return Topology(kind, h, h, vol, "/data", run_id)
    data_root = os.path.dirname(out_dir)
    if kind == "single":
        h = Host("local", "", "host", "127.0.0.1", env=_local_env())
        return Topology(kind, h, h, data_root, data_root, run_id)
    if kind == "two-host":
        if not sut_ssh or "@" not in sut_ssh:
            raise SetupError("two-host needs --sut-ssh bench@<sut private ip>")
        ip = sut_ssh.split("@", 1)[1]
        lg = Host("loadgen", "", "host", "127.0.0.1", env=_local_env())
        sut = Host("sut", f"ssh://{sut_ssh}", "host", ip, ssh=sut_ssh)
        sut.env = read_env_file(sut.shell("cat /etc/vericto-bench/host.env").stdout.decode())
        return Topology(kind, lg, sut, data_root, data_root, run_id)
    raise SetupError(f"unknown topology {kind}")


def _local_env() -> dict[str, str]:
    try:
        with open("/etc/vericto-bench/host.env") as f:
            return read_env_file(f.read())
    except FileNotFoundError:
        return {}


def addr(topo: Topology, host: Host, container: str) -> str:
    """Address a client uses for a service in `container` on `host`."""
    if host.network != "host":
        return container
    if topo.kind == "two-host" and host is topo.sut:
        return host.address
    return "127.0.0.1"


def peer_addr(topo: Topology, container: str) -> str:
    """Address an intermediary on the SUT uses to reach a database on the SUT."""
    return container if topo.sut.network != "host" else "127.0.0.1"


def tar_files(files: dict[str, tuple[bytes, int]], uid: int = 0, gid: int = 0) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, (data, mode) in files.items():
            ti = tarfile.TarInfo(name.rstrip("/"))
            ti.mode, ti.uid, ti.gid, ti.mtime = mode, uid, gid, int(time.time())
            if name.endswith("/"):
                ti.type = tarfile.DIRTYPE
                t.addfile(ti)
            else:
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


@dataclass
class Container:
    host: Host
    name: str
    id: str = ""

    def start(self):
        self.host.docker("start", self.name)

    def put(self, dest_dir: str, files: dict[str, tuple[bytes, int]], uid: int = 0, gid: int = 0):
        """Copy files into the (created, not necessarily started) container."""
        self.host.docker("cp", "-a", "-", f"{self.name}:{dest_dir}", input=tar_files(files, uid, gid))

    def pid(self) -> int:
        return int(self.host.docker("inspect", "-f", "{{.State.Pid}}", self.name).stdout.decode().strip())

    def running(self) -> bool:
        p = self.host.docker("inspect", "-f", "{{.State.Running}}", self.name, check=False)
        return p.returncode == 0 and p.stdout.decode().strip() == "true"

    def logs(self, path: str):
        p = self.host.docker("logs", "--timestamps", self.name, check=False)
        with open(path, "wb") as f:
            f.write(p.stdout + p.stderr)

    def remove(self):
        self.host.docker("rm", "-f", "-v", self.name, check=False)


def create(topo: Topology, host: Host, name: str, image: str, args: list[str] | None = None,
           env: dict[str, str] | None = None, pass_env: list[str] | None = None, cpuset: str = "",
           cpus: str = "", extra: list[str] | None = None, mount_data: bool = False) -> Container:
    """`docker create` with the run label, the host's network and the CPU budget."""
    host.docker("rm", "-f", "-v", name, check=False)
    cmd = ["create", "--name", name, "--label", f"{LABEL}={topo.run_label}", "--network", host.network,
           "--log-driver", "json-file", "--log-opt", "max-size=50m"]
    if host.network != "host":
        cmd += ["--network-alias", name]
    if cpuset:
        cmd += ["--cpuset-cpus", cpuset]
    if cpus:
        cmd += ["--cpus", cpus]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    for k in pass_env or []:  # value taken from this process's environment, never on a command line
        cmd += ["-e", k]
    if mount_data:
        cmd += topo.data_mount()
    cmd += extra or []
    cmd += [image] + (args or [])
    c = Container(host, name)
    c.id = run(host.docker_cmd() + cmd).stdout.decode().strip()
    return c


def cleanup(topo: Topology):
    for h in topo.hosts():
        ids = h.docker("ps", "-aq", "--filter", f"label={LABEL}={topo.run_label}", check=False).stdout.decode().split()
        if ids:
            h.docker("rm", "-f", "-v", *ids, check=False)
