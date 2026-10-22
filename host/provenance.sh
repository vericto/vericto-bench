#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Prints the host's provenance as JSON (manifest input, METHODOLOGY.md section 3).
# Hardware, kernel, clock, tuning and the CPU plan. No secrets, no environment dump.
set -euo pipefail
exec python3 -I - <<'PY'
import json, os, re, subprocess, urllib.request

def run(*cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception as e:  # tool missing on this host
        return f"unavailable: {e.__class__.__name__}"

def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None

def imds():
    out = {}
    try:
        req = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "120"})
        token = urllib.request.urlopen(req, timeout=2).read().decode()
        for key in ["ami-id", "instance-type", "instance-id", "placement/availability-zone",
                    "placement/availability-zone-id", "placement/group-name", "placement/region"]:
            try:
                r = urllib.request.Request("http://169.254.169.254/latest/meta-data/" + key,
                                           headers={"X-aws-ec2-metadata-token": token})
                out[key] = urllib.request.urlopen(r, timeout=2).read().decode()
            except Exception:
                out[key] = None
    except Exception:
        out["error"] = "IMDS not reachable (not on EC2?)"
    return out

def jsonish(s):
    try:
        return json.loads(s)
    except Exception:
        return s

host_env = {}
for line in (read("/etc/vericto-bench/host.env") or "").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        host_env[k] = v

iface = run("sh", "-c", "ip -o route show default | awk '{print $5; exit}'")
sysctls = ["net.core.somaxconn", "net.core.rmem_max", "net.core.wmem_max",
           "net.ipv4.tcp_rmem", "net.ipv4.tcp_wmem", "net.ipv4.tcp_congestion_control",
           "net.ipv4.ip_local_port_range", "net.ipv4.tcp_tw_reuse", "kernel.sched_autogroup_enabled"]
mp = jsonish(run("mpstat", "-o", "JSON", "1", "5", timeout=20))
steal = None
try:
    stats = mp["sysstat"]["hosts"][0]["statistics"]
    steal = max(s["cpu-load"][0]["steal"] for s in stats)
except Exception:
    pass

out = {
    "schema": "vericto-bench/provenance/1",
    "imds": imds(),
    "uname": run("uname", "-a"),
    "os_release": dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', read("/etc/os-release") or "", re.M)),
    "lscpu": jsonish(run("lscpu", "-J")),
    "nproc": os.cpu_count(),
    "kernel_cmdline": read("/proc/cmdline"),
    "clocksource": read("/sys/devices/system/clocksource/clocksource0/current_clocksource"),
    "chrony_tracking": run("chronyc", "tracking"),
    "thp_enabled": read("/sys/kernel/mm/transparent_hugepage/enabled"),
    "thp_defrag": read("/sys/kernel/mm/transparent_hugepage/defrag"),
    "cgroup_version": 2 if os.path.exists("/sys/fs/cgroup/cgroup.controllers") else 1,
    "docker_version": jsonish(run("docker", "version", "--format", "{{json .}}")),
    "irqbalance": run("systemctl", "is-active", "irqbalance"),
    "sysctl": {k: run("sysctl", "-n", k) for k in sysctls},
    "primary_interface": iface,
    "nic_driver": run("ethtool", "-i", iface) if iface and not iface.startswith("unavailable") else None,
    "mpstat_5s_max_steal_pct": steal,
    "host_env": host_env,
}
print(json.dumps(out, indent=2, sort_keys=True))
PY
