# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""Suite files (TOML) and their expansion into an ordered list of cells.

A suite is pre-registered: the cells, rates, order seed and validity rules are
fixed in the file before the run, and copied into the run's manifest.

Order (design section 8): within each repetition, every target of a curve runs
at a given rate before the next rate; the target order comes from a balanced
Latin square (Williams design) whose rows are chosen per (repetition, rate), and
the rates are shuffled with the seed, except the saturating rates (>= 100% of
S), which run last.
"""
from __future__ import annotations

import dataclasses
import random
import tomllib
from typing import Any

PROFILES = ("smoke", "quick", "published")
TOOLS = ("vbench", "pgbench", "sysbench")
SIZES = ("0.5", "1", "2x0.5")
TARGETS = {
    "pg": ("direct", "haproxy-tcp", "pgbouncer-session", "vericto-offline", "vericto-enforce", "vericto-observe"),
    "mysql": ("direct", "haproxy-tcp", "proxysql", "vericto-offline", "vericto-enforce", "vericto-observe"),
}


class SuiteError(ValueError):
    pass


@dataclasses.dataclass
class Curve:
    id: str
    engine: str
    tool: str
    workload: str
    mode: str
    tls: bool
    size: str
    targets: list[str]
    loop: str = "open"
    rates: list[float] = dataclasses.field(default_factory=list)
    rates_pct: list[float] = dataclasses.field(default_factory=list)
    saturation_from: str = ""  # id of a closed-loop curve of this run (S = its max of vericto-enforce)
    saturation_qps: float = 0.0  # or a pre-registered S
    concurrency: list[int] = dataclasses.field(default_factory=list)  # closed loop
    conns: int = 0
    arrival: str = "constant"
    warmup_s: float | None = None
    duration_s: float | None = None
    conn_mode: str = "pooled"
    pause_every_s: float = 0.0  # generator validation: docker pause of the database
    pause_s: float = 1.0
    reps: int = 0  # 0 = the suite's


@dataclasses.dataclass
class Suite:
    name: str
    profile: str
    order_seed: int
    reps: int
    warmup_s: float
    duration_s: float
    cooldown_s: float
    interval_s: float
    datasets: dict[str, int]
    curves: list[Curve]
    raw: dict[str, Any]
    database: dict[str, Any]
    engine_eval: dict[str, Any]


def _get(d: dict, key: str, typ, default=None, required=False):
    if key not in d:
        if required:
            raise SuiteError(f"missing {key}")
        return default
    v = d[key]
    if typ is float and isinstance(v, int):
        v = float(v)
    if not isinstance(v, typ):
        raise SuiteError(f"{key} must be {typ.__name__}")
    return v


def load(path: str) -> Suite:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    s = raw.get("suite") or {}
    profile = _get(s, "profile", str, required=True)
    if profile not in PROFILES:
        raise SuiteError(f"profile must be one of {PROFILES}")
    curves = []
    seen = set()
    for c in raw.get("curve", []):
        cid = _get(c, "id", str, required=True)
        if cid in seen:
            raise SuiteError(f"duplicate curve id {cid}")
        seen.add(cid)
        engine = _get(c, "engine", str, required=True)
        if engine not in TARGETS:
            raise SuiteError(f"{cid}: engine must be pg or mysql")
        tool = _get(c, "tool", str, "vbench")
        if tool not in TOOLS:
            raise SuiteError(f"{cid}: tool must be one of {TOOLS}")
        targets = _get(c, "targets", list, required=True)
        for t in targets:
            if t not in TARGETS[engine]:
                raise SuiteError(f"{cid}: unknown {engine} target {t}")
        size = str(_get(c, "size", str, "0.5"))
        if size not in SIZES:
            raise SuiteError(f"{cid}: size must be one of {SIZES}")
        if size == "2x0.5" and any(not t.startswith("vericto") and t != "direct" for t in targets):
            raise SuiteError(f"{cid}: 2x0.5 is for vericto targets (and direct) only")
        loop = _get(c, "loop", str, "open")
        cur = Curve(
            id=cid, engine=engine, tool=tool, workload=_get(c, "workload", str, required=True),
            mode=_get(c, "mode", str, ""), tls=_get(c, "tls", bool, True), size=size, targets=list(targets),
            loop=loop, rates=[float(x) for x in _get(c, "rates", list, [])],
            rates_pct=[float(x) for x in _get(c, "rates_pct", list, [])],
            saturation_from=_get(c, "saturation_from", str, ""),
            saturation_qps=float(_get(c, "saturation_qps", float, 0.0)),
            concurrency=[int(x) for x in _get(c, "concurrency", list, [])],
            conns=_get(c, "conns", int, 0), arrival=_get(c, "arrival", str, "constant"),
            warmup_s=_get(c, "warmup_s", float, None), duration_s=_get(c, "duration_s", float, None),
            conn_mode=_get(c, "conn_mode", str, "pooled"),
            pause_every_s=float(_get(c, "pause_every_s", float, 0.0)), pause_s=float(_get(c, "pause_s", float, 1.0)),
            reps=_get(c, "reps", int, 0),
        )
        if loop == "open":
            if not cur.rates and not cur.rates_pct:
                raise SuiteError(f"{cid}: an open-loop curve needs rates or rates_pct")
            if cur.rates_pct and not (cur.saturation_from or cur.saturation_qps):
                raise SuiteError(f"{cid}: rates_pct needs saturation_from or saturation_qps")
        elif loop == "closed":
            if not cur.concurrency:
                raise SuiteError(f"{cid}: a closed-loop curve needs concurrency")
        else:
            raise SuiteError(f"{cid}: loop must be open or closed")
        if tool == "sysbench" and loop == "open":
            raise SuiteError(f"{cid}: sysbench --rate excludes queue time; use it closed loop only (design section 8)")
        if tool == "sysbench" and cur.tls:
            raise SuiteError(f"{cid}: sysbench 1.0.20 only does verified TLS with fixed file names (cacert.pem, "
                             "client-cert.pem, client-key.pem in its working directory), which the intermediaries' "
                             "certificates do not satisfy; run sysbench with tls = false (TLS-on MySQL throughput "
                             "comes from vbench's closed-loop sysbench-ro replay)")
        if tool == "pgbench" and engine != "pg":
            raise SuiteError(f"{cid}: pgbench is PostgreSQL only")
        curves.append(cur)
    for cur in curves:
        if cur.saturation_from and cur.saturation_from not in seen:
            raise SuiteError(f"{cur.id}: saturation_from {cur.saturation_from} is not a curve of this suite")
    if not curves:
        raise SuiteError("no curves")
    return Suite(
        name=_get(s, "name", str, required=True), profile=profile, order_seed=_get(s, "order_seed", int, required=True),
        reps=_get(s, "reps", int, 3), warmup_s=float(_get(s, "warmup_s", float, 60.0)),
        duration_s=float(_get(s, "duration_s", float, 300.0)), cooldown_s=float(_get(s, "cooldown_s", float, 30.0)),
        interval_s=float(_get(s, "interval_s", float, 10.0)), datasets=dict(raw.get("datasets", {})),
        curves=curves, raw=raw, database=dict(raw.get("database", {})), engine_eval=dict(raw.get("engine_eval", {})),
    )


def williams(n: int) -> list[list[int]]:
    """Balanced Latin square (Williams design): every element follows every
    other equally often. For odd n the square and its mirror are returned."""
    if n == 1:
        return [[0]]
    # Standard construction: 0, 1, n-1, 2, n-2, ...
    first = [0]
    for i in range(1, n):
        first.append((i + 1) // 2 if i % 2 else n - i // 2)
    rows = [[(x + r) % n for x in first] for r in range(n)]
    if n % 2:
        rows += [list(reversed(r)) for r in rows]
    return rows


@dataclasses.dataclass
class Cell:
    curve: Curve
    rep: int
    target: str
    rate: float  # open loop: requests/s; closed loop: 0
    conc: int  # closed loop concurrency; open loop: pool size (0 = default)
    pct: float | None  # rate as % of S, when given that way
    seq: int = 0

    @property
    def id(self) -> str:
        r = f"r{self.rate:g}" if self.curve.loop == "open" else f"c{self.conc}"
        return f"{self.curve.id}.{self.target}.{r}.rep{self.rep}"


def expand(suite: Suite, curve: Curve, saturation: dict[str, float]) -> list[Cell]:
    """The cells of one curve in run order, for every repetition."""
    rng = random.Random(f"{suite.order_seed}:{curve.id}")
    targets = list(curve.targets)
    rng.shuffle(targets)  # which target gets which Latin-square symbol
    square = williams(len(targets))
    cells: list[Cell] = []
    reps = curve.reps or suite.reps
    if curve.loop == "closed":
        for rep in range(1, reps + 1):
            row = square[(rep - 1) % len(square)]
            for conc in curve.concurrency:  # closed loop: step up in order (the knee search)
                for i in row:
                    cells.append(Cell(curve, rep, targets[i], 0.0, conc, None))
        return _number(cells)
    rates: list[tuple[float, float | None]] = [(r, None) for r in curve.rates]
    if curve.rates_pct:
        s = curve.saturation_qps or saturation.get(curve.saturation_from, 0.0)
        if s <= 0:
            raise SuiteError(f"{curve.id}: S unknown (closed-loop curve {curve.saturation_from} has no vericto-enforce maximum)")
        rates += [(round(s * p / 100.0, 1), p) for p in curve.rates_pct]
    k = 0
    for rep in range(1, reps + 1):
        normal = [x for x in rates if (x[1] or 0) < 100]
        saturating = [x for x in rates if (x[1] or 0) >= 100]
        rng.shuffle(normal)
        for rate, pct in normal + saturating:
            row = square[k % len(square)]
            k += 1
            for i in row:
                cells.append(Cell(curve, rep, targets[i], rate, curve.conns, pct))
    return _number(cells)


def _number(cells: list[Cell]) -> list[Cell]:
    for i, c in enumerate(cells):
        c.seq = i
    return cells


def plan(suite: Suite, placeholder_s: float = 1000.0) -> dict:
    """Cells and machine hours of a suite without running it (closed-loop curves
    counted at every step; S unknown until the run, so rates_pct curves use a
    placeholder that changes no count)."""
    out = {"curves": [], "cells": 0, "hours": 0.0}
    sat = {c.id: placeholder_s for c in suite.curves if c.loop == "closed"}
    for c in suite.curves:
        try:
            cells = expand(suite, c, sat)
        except SuiteError as e:
            out["curves"].append({"id": c.id, "error": str(e)})
            continue
        w = c.warmup_s if c.warmup_s is not None else suite.warmup_s
        d = c.duration_s if c.duration_s is not None else suite.duration_s
        per = w + d + suite.cooldown_s + 25  # + target start, probe and teardown
        h = len(cells) * per / 3600 + (35 / 3600 if c.loop == "open" else 0)  # + network pre-flight probe
        out["curves"].append({"id": c.id, "cells": len(cells), "hours": round(h, 2)})
        out["cells"] += len(cells)
        out["hours"] += h
    out["hours"] = round(out["hours"], 1)
    return out
