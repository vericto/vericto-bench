# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Databases, the control-plane stub and every target of METHODOLOGY.md sections 1 and 2.

Port plan (identical in every topology; on the SUT with host networking):

    PostgreSQL 5432   MySQL 3306          direct
    vericto    6432 (second task 6433) / 6306 (6307)
    HAProxy    7432 / 7306                TCP hop
    PgBouncer  8432                       session pooling (PostgreSQL)
    ProxySQL   8306 (admin 127.0.0.1:6032)  SQL-aware (MySQL)
    cpstub     9090 (loopback on the SUT)

Every intermediary gets exactly the proxy's CPU budget (same cpuset and CFS
quota). TLS: the proxy, PgBouncer and ProxySQL terminate client TLS and open
their own TLS session to the database, so each pays two TLS legs. HAProxy is a
pure TCP hop: neither protocol can be TLS-terminated by a TCP proxy without
changing the client (PostgreSQL negotiates TLS in-protocol with SSLRequest,
MySQL upgrades mid-handshake), so in TLS cells HAProxy relays the end-to-end
TLS session and pays no cryptography. The TLS-off cells give its clean hop cost;
the report labels HAProxy accordingly (the original plan asked for termination
on both sides; see the README, "Design choices and changes").
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from . import topo as T

PORTS = {
    ("pg", "direct"): 5432, ("mysql", "direct"): 3306,
    ("pg", "vericto"): 6432, ("mysql", "vericto"): 6306,
    ("pg", "vericto2"): 6433, ("mysql", "vericto2"): 6307,
    ("pg", "haproxy-tcp"): 7432, ("mysql", "haproxy-tcp"): 7306,
    ("pg", "pgbouncer-session"): 8432, ("mysql", "proxysql"): 8306,
}
CPSTUB_PORT = 9090
DB_NAME = {"pg": "vb-postgres", "mysql": "vb-mysql"}
DB_UID = {"pg": 999, "mysql": 999}


def port(engine: str, target: str) -> int:
    key = "vericto" if target.startswith("vericto") else target
    return PORTS[(engine, key)]


@dataclass
class Images:
    proxy: str
    postgres: str
    mysql: str
    haproxy: str
    tools: str
    pgbouncer: str
    proxysql: str
    sysbench: str


def db_tuning(profile: str, cfg: dict) -> dict:
    big = profile != "smoke"
    return {
        "pg_shared_buffers": cfg.get("pg_shared_buffers", "4GB" if big else "256MB"),
        "pg_max_connections": str(cfg.get("pg_max_connections", 400)),
        "mysql_buffer_pool": cfg.get("mysql_buffer_pool", "4G" if big else "256M"),
        "mysql_max_connections": str(cfg.get("mysql_max_connections", 600)),
    }


def start_db(topo: T.Topology, images: Images, engine: str, tuning: dict, certs: dict[str, bytes]) -> T.Container:
    h = topo.sut
    cpuset = h.cpuset("CPU_DB")
    key_mode = 0o600
    if engine == "pg":
        args = ["postgres", "-c", "ssl=on", "-c", "ssl_cert_file=/certs/server.crt", "-c", "ssl_key_file=/certs/server.key",
                "-c", f"shared_buffers={tuning['pg_shared_buffers']}", "-c", f"max_connections={tuning['pg_max_connections']}",
                "-c", "fsync=on", "-c", "synchronous_commit=on", "-c", "max_wal_size=8GB", "-c", "checkpoint_timeout=15min",
                "-c", "huge_pages=off", "-c", "listen_addresses=*", "-c", "password_encryption=scram-sha-256"]
        c = T.create(topo, h, DB_NAME[engine], images.postgres, args=args,
                     env={"POSTGRES_USER": "bench", "POSTGRES_DB": "bench", "PGDATA": "/var/lib/postgresql/data/pgdata"},
                     pass_env=["POSTGRES_PASSWORD"], cpuset=cpuset)
    else:
        args = ["--mysql-native-password=ON", f"--innodb-buffer-pool-size={tuning['mysql_buffer_pool']}",
                f"--max-connections={tuning['mysql_max_connections']}", "--skip-name-resolve",
                "--ssl-ca=/certs/ca.crt", "--ssl-cert=/certs/server.crt", "--ssl-key=/certs/server.key",
                "--innodb-flush-log-at-trx-commit=1", "--sync-binlog=1", "--port=3306"]
        c = T.create(topo, h, DB_NAME[engine], images.mysql, args=args,
                     env={"MYSQL_DATABASE": "bench", "MYSQL_USER": "bench"},
                     pass_env=["MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD"], cpuset=cpuset)
    c.put("/", {"certs/": (b"", 0o755), "certs/ca.crt": (certs["ca.crt"], 0o644),
                "certs/server.crt": (certs["server.crt"], 0o644), "certs/server.key": (certs["server.key"], key_mode)},
          uid=DB_UID[engine], gid=DB_UID[engine])
    c.start()
    return c


def start_cpstub(topo: T.Topology, images: Images) -> T.Container:
    h = topo.sut
    listen = f"127.0.0.1:{CPSTUB_PORT}" if h.network == "host" else f"0.0.0.0:{CPSTUB_PORT}"
    c = T.create(topo, h, "vb-cpstub", images.tools,
                 args=["cpstub", "-listen", listen, "-rules", "/opt/vericto-bench/rules.json",
                       "-sensitive", "/opt/vericto-bench/sensitive.json"],
                 cpuset=h.cpuset("CPU_AUX"))
    c.start()
    return c


def cpstub_url(topo: T.Topology) -> str:
    return f"http://127.0.0.1:{CPSTUB_PORT}" if topo.sut.network == "host" else f"http://vb-cpstub:{CPSTUB_PORT}"


def cpstub_get(topo: T.Topology, path: str, post: bool = False) -> dict:
    url = f"http://127.0.0.1:{CPSTUB_PORT}{path}" if topo.sut.network == "host" else f"http://vb-cpstub:{CPSTUB_PORT}{path}"
    args = ["exec", "vb-cpstub", "wget", "-qO-"] + (["--post-data="] if post else []) + [url]
    p = topo.sut.docker(*args, check=not post)
    out = p.stdout.decode().strip()
    return json.loads(out) if out else {}


def budget(topo: T.Topology, size: str, second: bool = False) -> tuple[str, str]:
    """(cpuset, cpus) of an intermediary at a size: 0.5 = one core with a 50%
    CFS quota, 1 = one whole core, 2x0.5 = two cores at 50% each, 0.5x2c = a
    50% quota over two cores (as a 0.5 vCPU Fargate task on its 2-vCPU host)."""
    h = topo.sut
    cpuset = h.cpuset("CPU_PROXY2" if second else "CPU_PROXY")
    if size == "0.5x2c":
        cpuset = ",".join(x for x in (h.cpuset("CPU_PROXY"), h.cpuset("CPU_PROXY2")) if x)
    cpus = "" if size == "1" else "0.5"
    return cpuset, cpus


def start_target(topo: T.Topology, images: Images, engine: str, target: str, size: str, tls: bool,
                 certs: dict[str, bytes], second: bool = False, variant=None, variant_image: str = "") -> T.Container | None:
    """variant (suite.Variant): run `target` with the configuration of
    variant.base, from variant_image, with variant.env on top."""
    if target == "direct":
        return None
    h = topo.sut
    base = variant.base if variant else target
    cpuset, cpus = budget(topo, size, second)
    db = DB_NAME[engine]
    db_host = T.peer_addr(topo, db)
    db_port = PORTS[(engine, "direct")]
    name = f"vb-{engine}-{target}" + ("-2" if second else "")
    lport = PORTS[(engine, "vericto2")] if second else port(engine, target)
    if base.startswith("vericto"):
        env = {"VERICTO_WIRE_PROTOCOL": "postgres" if engine == "pg" else "mysql",
               "UPSTREAM_HOST": db_host, "UPSTREAM_PORT": str(db_port), "PROXY_LISTEN_PORT": str(lport),
               "UPSTREAM_SSLMODE": "require" if tls else "disable", "PROXY_TLS_MODE": "require" if tls else "disable",
               # The documented default; set explicitly so the run does not depend on the image's default.
               "RUST_LOG": "info"}
        if tls:
            env.update({"PROXY_TLS_CERT": "/certs/server.crt", "PROXY_TLS_KEY": "/certs/server.key"})
        if base in ("vericto-enforce", "vericto-observe"):
            mode = "observe" if base == "vericto-observe" else "enforce"
            env.update({"VERICTO_API_URL": cpstub_url(topo), "VERICTO_API_KEY": f"{mode}-{engine}",
                        "VERICTO_DATABASE_ID": f"bench-{engine}", "VERICTO_TELEMETRY_BUFFER": "memory"})
            if topo.sut.network != "host":
                # Compose only: the stub is another container, not loopback.
                env["VERICTO_ALLOW_INSECURE_API_URL"] = "true"
        if variant:
            env.update(variant.env)
        c = T.create(topo, h, name, variant_image or images.proxy, env=env, cpuset=cpuset, cpus=cpus)
        if tls:
            # Throwaway per-run key, readable by the image's non-root user.
            c.put("/", {"certs/": (b"", 0o755), "certs/server.crt": (certs["server.crt"], 0o644),
                        "certs/server.key": (certs["server.key"], 0o644)})
        c.start()
        return c
    if target == "haproxy-tcp":
        cfg = (f"global\n  nbthread 1\n  maxconn 4096\n  log stdout format raw local0 notice\n"
               f"defaults\n  mode tcp\n  timeout connect 5s\n  timeout client 1h\n  timeout server 1h\n  option tcp-smart-accept\n  option tcp-smart-connect\n"
               f"frontend fe\n  bind 0.0.0.0:{lport}\n  default_backend be\n"
               f"backend be\n  server db {db_host}:{db_port}\n")
        c = T.create(topo, h, name, images.haproxy, args=["haproxy", "-f", "/usr/local/etc/haproxy/haproxy.cfg"],
                     cpuset=cpuset, cpus=cpus)
        c.put("/usr/local/etc/haproxy", {"haproxy.cfg": (cfg.encode(), 0o644)})
        c.start()
        return c
    if target == "pgbouncer-session":
        tls_cfg = ("client_tls_sslmode = require\nclient_tls_key_file = /etc/pgbouncer/server.key\n"
                   "client_tls_cert_file = /etc/pgbouncer/server.crt\nserver_tls_sslmode = require\n") if tls else \
                  "client_tls_sslmode = disable\nserver_tls_sslmode = disable\n"
        ini = (f"[databases]\nbench = host={db_host} port={db_port} dbname=bench\n"
               f"[pgbouncer]\nlisten_addr = 0.0.0.0\nlisten_port = {lport}\nauth_type = scram-sha-256\n"
               f"auth_file = /etc/pgbouncer/userlist.txt\npool_mode = session\nmax_client_conn = 2000\n"
               f"default_pool_size = 1000\nmax_db_connections = 0\nmax_prepared_statements = 200\n"
               f"server_reset_query = DISCARD ALL\nignore_startup_parameters = extra_float_digits\n"
               f"so_reuseport = 0\nlog_connections = 0\nlog_disconnections = 0\nadmin_users = \n{tls_cfg}")
        c = T.create(topo, h, name, images.pgbouncer, cpuset=cpuset, cpus=cpus)
        users = f'"bench" "{os.environ["POSTGRES_PASSWORD"]}"\n'.encode()
        c.put("/etc/pgbouncer", {"pgbouncer.ini": (ini.encode(), 0o644), "userlist.txt": (users, 0o600),
                                 "server.crt": (certs["server.crt"], 0o644), "server.key": (certs["server.key"], 0o600)},
              uid=10002, gid=10002)
        c.start()
        return c
    if target == "proxysql":
        pw = os.environ["MYSQL_PASSWORD"]
        cnf = f"""datadir="/var/lib/proxysql"
admin_variables=
{{
  admin_credentials="admin:{pw}"
  mysql_ifaces="127.0.0.1:6032"
}}
mysql_variables=
{{
  threads=1
  max_connections=4096
  interfaces="0.0.0.0:{lport}"
  server_version="8.4.13"
  have_ssl={"true" if tls else "false"}
  monitor_enabled=false
  multiplexing=false
  query_digests=true
  default_query_timeout=3600000
  connect_timeout_server=5000
}}
mysql_servers=
(
  {{ address="{db_host}", port={db_port}, hostgroup=0, max_connections=4096, use_ssl={1 if tls else 0} }}
)
mysql_users=
(
  {{ username="bench", password="{pw}", default_hostgroup=0, transaction_persistent=1, fast_forward=0 }}
)
mysql_query_rules=
(
)
"""
        c = T.create(topo, h, name, images.proxysql, cpuset=cpuset, cpus=cpus)
        c.put("/etc", {"proxysql.cnf": (cnf.encode(), 0o600)})
        c.start()
        return c
    raise T.SetupError(f"unknown target {target}")
