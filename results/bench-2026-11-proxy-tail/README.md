# BENCH-2026-11: vericto-proxy tail latency near saturation

Status: runs complete (2026-10-23/24), stacks destroyed. Not published: profile `quick`.

BENCH-2026-11 measured an added p99 of about **43 ms** for PostgreSQL W1 at 80% of S at
0.5 vCPU (3.6 ms at 70%; p50 0.12 to 0.15 ms throughout), and 32.9 ms for MySQL W3 at
90%. This investigation asked why, and whether the proxy can do anything about it.

## Result

**Root cause: the proxy's CPU demand reaching its CFS quota.** A 0.5 vCPU budget gives
50 ms of CPU per 100 ms period. When the average demand nears that, more and more periods
run out of quota before they end, and every statement in flight waits for the next period:
tens of ms at once. The latency is flat up to the point where the average CPU reaches the
quota, then jumps within a few percent of load. The knee sits at `quota / CPU per statement`:

| | CPU per statement (PG W1) | Capacity at 0.5 vCPU | as % of S (6,032.6/s) | Added p99 at 80% / 90% of S |
| --- | --- | --- | --- | --- |
| 4.14.2, BENCH-2026-11 (2026-10-20) | 103-110 µs | about 4,750/s | 79% | 39-47 ms / saturated |
| 4.14.2, this session (control) | 91-95 µs | about 5,350/s | 89% | 4.6 ms / 29.8 ms |
| 4.15.3, this session | 85-87 µs | about 5,800/s | 96% | 1.05 ms / 1.33 ms (2.6 ms in the control) |

The evidence, per cell (`run/report/tail.md`, `control/report/tail.md`):

- At the knee, the proxy's average CPU equals its quota: 0.499 to 0.500 vCPU in all three
  BENCH-2026-11 cells at 80% of S, with 95% of the 100-ms periods throttled (134 to 182 ms
  throttled per second).
- Slow statements line up with throttled periods (host/schedmon.py, cgroup `cpu.stat`
  every 100 ms against pgbench's per-transaction log). For 4.15.3 at 90% of S, 2.4% of all
  transactions overlap a throttled period, but 91% of those slower than 10 ms do. In every
  cell with throttling, 69 to 100% of the slow transactions overlap one. At 1 vCPU (no
  quota) there is no throttling, and the p99.9 is about half that at 0.5.
- **It is not too many tokio workers in the bench.** At 0.5 the proxy has one dedicated
  core with a 50% quota (`--cpuset-cpus` plus `--cpus`). std's `available_parallelism`
  sees both, so tokio started 1 worker, plus the evaluation pool: 8 to 15 threads, 1
  worker. The candidate, which sizes the workers from the quota itself, matches
  4.15.3 there in every cell.
- **The knee moved because the CPU per statement fell.** About 11% came from the
  environment (4.14.2 on the same hardware: 103-110 µs on 2026-10-20, 91-95 µs now; newer
  AL2023 AMI and kernel 6.18.54, PostgreSQL 17.11 instead of 17.6). Another 8% came from
  4.15.3 (86.5 against 94.2 µs on the same hosts, same session). 4.14.2 shows the same jump
  in this session, one rate step later: 3.3 → 4.6 → 29.8 ms from 70 to 90%.

**But the worker count does matter on ECS Fargate, and there it reproduces the
problem.** In five Fargate probes (0.5 vCPU, ARM64, platform 1.4.0, cgroup v1), the
container's own cgroup carried no quota (`cpu.cfs_quota_us` = -1, no throttled periods in
its `cpu.stat`). The task's quota is set on the task cgroup, above the container, and it
held: two busy threads got 0.499 to 0.502 vCPU. The container saw 2 CPUs on most hosts and
1 on some (`nproc`, `available_parallelism` from Rust 1.88 and 1.98), so 4.15.3 starts 1
or 2 workers depending on the host. The ECS task metadata endpoint does report the limit
(`Limits.CPU` = 0.5).

The suite reproduces that with size `0.5x2c`: the 50% quota over two cores, and
`TOKIO_WORKER_THREADS=2` for 4.15.3, since Docker on EC2 shows the quota. Results:

- **4.15.3 with 2 workers** costs 20-25% more CPU per statement (103-106 against 81-83
  µs). It reaches the quota at about 80% of S: added p99 **39 ms** at 80%, the signature
  of the published figure. At 90% it collapses (p50 62 to 95 ms, p99 0.26 to 1.4 s; the
  third repetition and its rerun flagged unsteady).
- **The candidate on the same budget** picks 1 worker from the quota (on Fargate,
  from the task metadata; verified on a Fargate task: `"source": "ecs_task_cpu_limit",
  "worker_threads": 1`). Its added p99 is 0.40 ms at 80% and 0.49 ms at 90%. This is the
  best of all variants, 1 vCPU included: with 1 worker and the evaluation pool on a second
  core, the run-queue wait per statement falls from about 45 µs to 6-9 µs.

## Variants at the knee (3 paired repetitions, added latency against `direct`)

PostgreSQL W1 (pgbench select-only, extended, TLS on both hops). Added p99 / p99.9, ms:

| % of S | 4.15.3, 0.5 | candidate, 0.5 | candidate, 0.5, 4 blocking threads | 4.15.3, 0.5x2c, 2 workers | candidate, 0.5x2c (1 worker) | 4.15.3, 1 vCPU |
| --- | --- | --- | --- | --- | --- | --- |
| 60 | 0.68 / 6.1 | 0.68 / 4.7 | 0.62 / 4.9 | 0.26 / 0.75 | 0.29 / 0.54 | 0.64 / 3.8 |
| 70 | 0.84 / 6.5 | 0.86 / 7.9 | 0.78 / 6.5 | 0.35 / 16.6 | 0.35 / 0.64 | 0.83 / 6.7 |
| 80 | 1.05 / 13.6 | 1.02 / 12.2 | 0.97 / 12.3 | **39.1 / 82.9** | 0.40 / 2.0 | 1.00 / 9.8 |
| 90 | 1.33 / 21.1 | 2.82 / 31.0 | 1.45 / 24.8 | **759 / 958** (collapse) | 0.49 / 17.4 | 1.17 / 9.5 |

The p50 is 0.10 to 0.13 ms everywhere except the collapsing cells. The candidate at 0.5, 90%: one
of three repetitions reached the quota (p99 5.3 ms); its interval contains 4.15.3's.

MySQL W3 (oltp_read_only, text, TLS). Added p99 / p99.9, ms:

| % of S | 4.15.3, 0.5 | candidate, 0.5 | candidate, 0.5, 4 blocking threads | 4.15.3, 0.5x2c, 2 workers | candidate, 0.5x2c (1 worker) | 4.15.3, 1 vCPU |
| --- | --- | --- | --- | --- | --- | --- |
| 80 | 2.55 / 9.8 | 2.50 / 11.3 | 2.54 / 9.7 | **15.9 / 34.0** | 1.79 / 2.2 | 2.54 / 6.8 |
| 90 | 2.35 / 15.6 | 2.44 / 15.6 | 2.24 / 14.5 | **56.2 / 69.3** | 1.28 / 3.8 | 2.27 / 7.8 |

CPU per transaction: 1,400-1,465 µs at 0.5; 1,556-1,747 with 2 workers; 1,235-1,251 for the
candidate over two cores.

Throttling (hostmon, periods per second out of 10): 0.06-0.23 at 0.5 for 4.15.3 and the
candidate, against 8.7 to 10 for 2 workers at 80-90%.

- **Capping the evaluation pool** (`VERICTO_BLOCKING_THREADS=4`, a candidate-only switch
  for this run) made no difference beyond noise: same CPU, same p99 within the intervals.
  4.16.2 ships without that switch.
- **Smoothing periodic work**: nothing periodic showed up. Telemetry batches are about
  10 per second at these rates, and rule sync runs every 5 minutes. Serializing a 500-event
  batch takes about 0.15 ms. No throttled period lined up with a sync.

## Recommendation

1. Ship **vericto-proxy 4.16.2** (workers sized from the CPU limit, the ECS task limit
   included). On Fargate 0.5 vCPU tasks it removes the 2-worker penalty, which is the
   difference between 0.4 and 39 ms at 80% of S.
2. Size capacity from CPU per statement and **scale out at 50-60% CPU of the task
   reservation** (ECS `CPUUtilization`, target tracking). The knee is where the average
   reaches 100%. Inside a Fargate container, throttling is invisible, so use the ECS
   metric.
3. For tail budgets of a few ms at high utilization or bursty load, use **1 vCPU tasks**
   or more tasks: two 0.5 tasks sustained about 1.9 times one. The CFS period cannot be
   changed on Fargate.
4. Correct the published reading. The 43 ms at 80% of S is the 0.5 vCPU quota being
   reached by 4.14.2 in that environment. With 4.15.3 the same rate costs about 1 ms, and
   the knee is near 96% of S.

## What was measured

- Suites [`suites/proxy-tail.toml`](../../suites/proxy-tail.toml) (run) and
  [`suites/proxy-tail-control.toml`](../../suites/proxy-tail-control.toml) (control),
  both fixed before their runs:
  - S as pre-registered (BENCH-2026-11 day 1: 6,032.6/s PostgreSQL, 356.6/s MySQL), so the
    rates are the published absolute rates;
  - 3 repetitions, Williams order of the targets per repetition and rate;
  - 30 s warm-up, 120 s measured, 10 s cool-down;
  - every target against `direct` at the same rate in the same repetition.
- Images by digest:
  - 4.15.3: `docker.io/vericto/vericto-proxy@sha256:e543749208dbc485de08d139de6b4e7c82fd29f227c6b1b52a7ec7b0669667cf`;
  - 4.14.2: `sha256:0446e4357183cf676461c2eac42377d0e331ad19d044d12cde1045608785eb6b`;
  - the candidate ("4.16.1 candidate" in the run's labels), built for linux/arm64 with the
    proxy's Dockerfile from 4.16.0 (origin/main with patch 0060) plus the worker sizing,
    with a run-only `VERICTO_BLOCKING_THREADS` switch since removed, from a bench-only
    registry: `sha256:c6e1fa31019bf72b4c463a5b6a292d1214066188de216f301d5ecc00e3b5d320`.
    The sizing ships as vericto-proxy **4.16.2** (patch 0062, on top of the 4.16.1
    cancel-request fixes), whose default path is the same;
  - PostgreSQL 17.11 `sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe`;
  - MySQL 8.4.13 `sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69`;
  - HAProxy 3.0.30 `sha256:f7f26e983c1c1d0c99d2a82e5a7135d9c77917eb51d0bd3b624bd3d75b10ca30`
    (pulled, not run);
  - tools on Go 1.27 `sha256:b8c9b82affbbb82a020bbcf998dad2ba9516944ac7e883524642a481a9505e9c`
    and Alpine 3.24.3 `sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a`.

  These are the latest patch releases on 2026-10-23 (versions.lock).
- Hosts:
  - SUT c7g.2xlarge and load generator c7g.xlarge in one cluster placement group in
    us-east-1, in an existing VPC (`existing_vpc_id`);
  - the latest AL2023 arm64 AMI from its public SSM parameter (`ami-07890d146f8d6ee5b`,
    kernel 6.18.54), `dnf upgrade --releasever=latest` at boot.
- Size `0.5x2c` (new): cores `CPU_PROXY,CPU_PROXY2` with `--cpus=0.5`. A variant may now set
  `size` (runner/vbr/suite.py, runner.py).
- host/schedmon.py (new) records on the SUT's auxiliary core:
  - cgroup `cpu.stat` every 100 ms;
  - per-thread CPU and `schedstat` run-queue wait every 5 s.
- `analysis/tail.py` (new) writes `report/tail.md` and `tail.json`. Regenerate them with:

      python3 analysis/tail.py RUN_DIR --schedmon schedmon.jsonl.gz --out DIR

- Fargate probes: five short tasks (0.5 vCPU, 1 GB, ARM64, platform 1.4.0, Amazon Linux
  2023 image) printed:
  - `/proc/self/cgroup` and the cgroup mounts;
  - the quota files and `nproc`;
  - `available_parallelism` from Rust 1.88 and 1.98;
  - the task metadata `Limits`;
  - the CPU two busy threads got in 10 s.

  A sixth task ran the candidate and logged its sizing. They are not part of the
  harness.

## Validity

- 124 cells used in the run (126 planned, 2 netprobes, 2 reruns). Invalid (kept, not
  averaged): the `0.5x2c`/2-worker cell at 90% of S of repetition 3 and its rerun, for
  both PostgreSQL and MySQL (not steady). All collapsed under the quota, so they are the
  effect, not an artifact.
- All control cells were valid.
- The SUT's logs did not reach the run archive: `finish.sh` copied them with `scp -r dir/.`,
  which copied nothing. `schedmon.jsonl` was retrieved from the stopped SUT afterwards.
  `finish.sh` now copies them with tar over ssh. The control run has no schedmon log, so
  its throttling comes from hostmon only.
- Raw data:
  - in Vericto's private archive under `bench-2026-11-proxy-tail-1/` (results, logs, and
    `schedmon.jsonl.gz`) and `bench-2026-11-proxy-tail-control-1/`;
  - checksums in `run/SHA256SUMS` and `control/SHA256SUMS`.
- `harness_commit` in the manifests is the pre-commit state of this patch: the same files
  minus this README and the reports.

## Files

- `run/`, `control/`: `manifest.json` (instance ids and the bench registry redacted),
  `cells.jsonl`, `statements.jsonl`, `verdicts.jsonl`, `SHA256SUMS`, `report/tail.md`,
  `report/tail.json`.
