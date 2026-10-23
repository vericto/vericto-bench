# BENCH-2026-11 M2 quick: vericto-proxy 4.15.0 (VERICTO_POLICY_RULES=off) against 4.14.3

Status: run complete (2026-10-22), stack destroyed. Not published: profile `quick`, n = 3.

**Gate result: FAIL in one cell.** 4.15.0 with `VERICTO_POLICY_RULES=off` cannot be told
apart from 4.14.3 in 7 of the 8 gated cells. In one cell, MySQL W3 at 182/s (50% of S), it is
slower at p50 and p99, and the 95% intervals say so.

## What ran

- Suite [`suites/m2-quick.toml`](../../suites/m2-quick.toml): the `quick` suite with four targets
  on the same two hosts, in one session. The targets are `direct`; 4.14.3 (the baseline);
  4.15.0 with `VERICTO_POLICY_RULES=off` (the gate); and 4.15.0 with
  `VERICTO_POLICY_RULES=observe` and an empty policy set (informational). All three proxies
  run the `vericto-enforce` configuration: 42 built-in rules, telemetry to the local stub,
  `RUST_LOG=info`, 0.5 vCPU, TLS on both legs. The suite runs 3 repetitions, and within
  each one every target runs at a rate before the next rate (Williams order), so every
  4.15.0 cell is paired with a 4.14.3 cell of the same repetition and rate. The headline
  curves run at 30, 50, 70 and 100% of S, where S is 4.14.3's closed-loop maximum.
- Images, by digest (same digests on GHCR):
  - 4.14.3 `sha256:66fa5e986f2b63089c5bcf07324bc2a0501920e6d180997c04d0526cf75c7354`
  - 4.15.0 `sha256:f4fd543e764204162a04320feefa54e52ac3a1670ea3d8419d32987f70d75124`
- Hosts: SUT c7g.2xlarge and load generator c7g.xlarge in one cluster placement group,
  us-east-1, the BENCH-2026-11 setup. Open loop, measured from the intended send time.
  The project's traffic caps applied.
- S (4.14.3, closed loop, 1 repetition): 5,766/s on PostgreSQL W1 and 363/s on MySQL W3.
- Harness: base `d4eef3b` plus the changes in this commit:
  - suite variants (`[variant.*]`): other proxy images and extra proxy environment;
  - `analysis/compare.py`;
  - the Go build image moved to 1.25, which `go.mod` has required since the pgx 5.9.2
    bump. The first attempt failed in the image build because of it, and measured nothing.

  `manifest.json` records `d4eef3b`. Its `proxy_image` field is the lock's default (4.14.2),
  which no cell used: the images actually run are under `proxy_variants`.
- Cells: 148 recorded, 132 used, 0 invalid.
  - The 9 proxy cells at 100% of S on PostgreSQL are saturated, as expected, for all three
    proxies.
  - MySQL at 100% of S (363/s) was not run: the network pre-flight fits 361/s at most.
  - One closed-loop `direct` MySQL step was aborted by the traffic cap.
  - The generator validation passed.
- Raw data: in Vericto's private archive, prefix `bench-2026-11-m2-quick-1/`;
  [`run/SHA256SUMS`](run/SHA256SUMS) lists the tarballs. Instance ids and host names are
  redacted in `run/manifest.json`.

## Gate: paired difference 4.15.0(off) minus 4.14.3

Gated cells are those below 70% of S, plus the cells at absolute rates. A gated cell
passes at a percentile if the two releases' 95% intervals of added latency overlap, or if
the paired difference's interval contains 0. Values are in ms, as means with Student t 95%
intervals, n = 3.

| Cell | p50 diff | p99 diff | p99.9 diff | Pass |
| --- | --- | --- | --- | --- |
| PG W1 1,730/s (30%) | 0.000 [-0.005, 0.005] | 0.022 [-0.057, 0.102] | -1.463 [-7.901, 4.975] | yes |
| PG W1 2,883/s (50%) | -0.001 [-0.013, 0.012] | 0.016 [-0.348, 0.380] | 1.158 [-3.406, 5.721] | yes |
| MySQL W3 109/s (30%) | 0.020 [-0.050, 0.090] | -0.035 [-0.273, 0.204] | -0.079 [-0.214, 0.057] | yes |
| **MySQL W3 182/s (50%)** | **0.112 [0.082, 0.142]** | **0.188 [0.022, 0.354]** | 0.245 [-4.254, 4.745] | **no** |
| PG payload 100 KB, 50/s | 0.019 [-0.018, 0.056] | 0.004 [-0.011, 0.019] | 0.221 [-0.531, 0.973] | yes |
| PG batch-1000 INSERT, 10/s, 1 vCPU | -0.061 [-0.490, 0.367] | -0.061 [-0.389, 0.267] | 2.821 [-8.599, 14.242] | yes |
| PG W1 4,036/s (70%, not gated) | 0.006 [0.002, 0.010] | 0.164 [-0.131, 0.459] | 2.464 [-7.474, 12.401] | (p50 no) |
| MySQL W3 254/s (70%, not gated) | -0.004 [-0.148, 0.140] | -0.004 [-0.448, 0.440] | -0.683 [-6.852, 5.486] | yes |

At MySQL 182/s, the added p50 is 1.546 ms [1.503, 1.589] for 4.14.3 and 1.658 ms
[1.603, 1.713] for 4.15.0(off), +7%. The added p99 is 4.098 [4.015, 4.181] against
4.286 [4.183, 4.389], +5%. The proxy's CPU in that cell is also higher: 0.0963 against
0.1026 vCPU per 1,000 statements/s, a paired difference of +0.0063 [0.0021, 0.0106].

The difference is consistent across the three repetitions: 4.15.0(off) is 0.09 to 0.11 ms
slower at p50 each time, whichever release ran first. It is not seen at 109/s or at 254/s,
and 4.15.0 with policy rules **on** (observe) was faster than 4.15.0(off) in that same
cell. So the effect does not grow with load and does not follow the code that the flag
turns on. Whether it is a regression of 4.15.0 or a cell effect cannot be told from n = 3.
It is reported as a failing cell, not explained away.

Proposed next diagnostic (not run):

1. A targeted A/B on a fresh stack: MySQL W3 at 40, 50 and 60% of S, 4.14.3 against
   4.15.0(off) only, at least 8 alternating repetitions of 300 s.
2. If the difference holds, compare the MySQL text path of the two releases: CPU profiles
   (`perf record` on the proxy core) and the engine's evaluation time per statement
   (`engine-eval bench` with engine v4.3.0 against v4.4.0).

## CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S, 9 points each)

| Curve | 4.14.3 | 4.15.0 off | 4.15.0 observe |
| --- | --- | --- | --- |
| PG W1 | 0.1009 [0.0982, 0.1035] | 0.1051 [0.1002, 0.1101] | 0.1073 [0.1024, 0.1122] |
| MySQL W3 | 0.0925 [0.0851, 0.1000] | 0.0893 [0.0808, 0.0978] | 0.0968 [0.0928, 0.1009] |

The intervals overlap on both engines.

## Informational: 4.15.0 with VERICTO_POLICY_RULES=observe (empty policy set) minus 4.14.3

- p50: +0.004 to +0.009 ms on PG W1 and not distinguishable from 0 on MySQL W3.
- p99: +0.66, +0.83 and +0.91 ms on PG W1 at 30, 50 and 70%, and +0.36, +0.49 and
  +0.57 ms on MySQL W3. Every one of these intervals excludes 0.
- CPU: about +0.004 to +0.007 vCPU per 1,000 statements/s.

So turning policy rules on costs little at the median, but it widens the p99 by roughly
0.4 to 0.9 ms at 0.5 vCPU.

## Closed-loop maximum (1 repetition, statements/s)

| | direct | 4.14.3 | 4.15.0 off | 4.15.0 observe |
| --- | --- | --- | --- | --- |
| PG W1 | 28,776 | 5,766 | 5,747 | 5,573 |
| MySQL W3 | 8,664 | 5,816 | 5,447 | 5,667 |

## Files

- `run/manifest.json`, `run/cells.jsonl`, `run/statements.jsonl`, `run/verdicts.jsonl`:
  the run.
- `run/report/`: `report.py`'s report and charts.
- `run/report/compare.md` and `run/report/compare.json`: every cell and percentile of the
  comparison. Regenerate them with:

      python3 analysis/compare.py <run dir> --baseline vericto-enforce-4143 \
          --candidate vericto-enforce-4150-off --extra vericto-enforce-4150-observe
