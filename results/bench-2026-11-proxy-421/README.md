# BENCH-2026-11, refresh for vericto-proxy 4.21.0 (EC2, Tier P, 2026-10-31)

Status: four runs complete on 2026-10-31, every stack destroyed. The public write-up is
[vericto.com/benchmarks/proxy-latency](https://vericto.com/benchmarks/proxy-latency), which this
directory now feeds; the earlier publication (vericto-proxy 4.14.2, 2026-10-20/21) stays in
[`../bench-2026-11`](../bench-2026-11).

System under test: vericto-proxy 4.21.0, the published image
`docker.io/vericto/vericto-proxy:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd`
(engine v4.6.0, 42 built-in rules, default policy, default configuration), copied by digest to a
bench-only Amazon ECR repository that was deleted after the runs (the manifests record that
reference; its account id is redacted here as `<bench-account>`, the digest is unchanged).
`RUST_LOG=info`, enforce mode with telemetry to the local control-plane stand-in, TLS on both
legs, 0.5 vCPU (one Graviton3 core, 50% CFS quota) and 2 x 0.5 vCPU. SUT c7g.2xlarge and load
generator c7g.xlarge in one cluster placement group per stack, each stack in its own VPC
(us-east-1c and us-east-1d), Amazon Linux 2023 upgraded at boot, PostgreSQL 17.11, MySQL 8.4.13,
HAProxy 3.0.30 (`versions.lock`).

## Runs

| Directory | Run | Suite | What |
| --- | --- | --- | --- |
| `day1-pg/` | bench-2026-11-proxy-421-p | `pub421-day1-pg` | PostgreSQL: closed-loop saturation of vericto-enforce (S = 9,667.7/s at 8 connections), the generator validation (2 x 1 s pauses per minute: 0.96% and 0.97% of requests above 500 ms, 0.83% expected), the headline curve at 10-100% of S against direct and HAProxy TCP, 3 repetitions of 300 s |
| `day1-my/` | bench-2026-11-proxy-421-m | `pub421-day1-my` | MySQL W3 oltp_read_only headline curve at 10-100% of a pre-registered S = 356.6 transactions/s (the 4.14.2 publication's S, so the rates are the published ones), 3 repetitions |
| `day2/` | bench-2026-11-proxy-421-d2 | `pub421-day2` | Both headline curves once more on a separately launched stack (fresh hosts, the same day), at day 1's absolute rates, 1 repetition (`day = 2`) |
| `scaling/` | bench-2026-11-proxy-421-h2 | `pub421-scaling` | PostgreSQL 2 x 0.5 vCPU against direct at 30-200% of day 1's S, and 1 x 0.5 at 30/90/120% on the same host, 2 repetitions |
| `report-day1/` | day 1 (PostgreSQL + MySQL) | | `analysis/report.py --publishable --label "day 1"` over `day1-pg` and `day1-my`: the headline tables |
| `report/` | all four | | `analysis/report.py --publishable --label "day 1 + day 2"` over the four runs: between-days and scaling tables |

Why MySQL's S is pre-registered: at about 40 KB per transaction, the closed-loop steps of a
4.20.0-class proxy pass the 400 Mbps hard cap (METHODOLOGY.md section 9) before the proxy
saturates (every closed-loop W3 step of the 4.20.0 release gate at 16 connections was aborted by
the cap). The open-loop curve at the published rates stayed under the caps; no cell of these four
runs was aborted.

Budget trims of this refresh (fixed in the suites before the runs): the saturation curve ran
vericto-enforce only; the scaling curve has 2 repetitions and stops at 200% of S; the day-2 stack
ran the same day on new hosts.

Validity: every open-loop cell valid except one not-steady repetition of the PostgreSQL 90% cell
and its rerun (the knee; saturated or not-steady cells are never latency). Steal 0% on every host.
Published latency stops at 70% of S: at 80% the PostgreSQL p99 was at the quota's knee on both
stacks.

Proxy memory (not part of the harness; the container's cgroup `memory.current` and
`memory.peak`, sampled every 30 s on the SUT during the day-1 runs): peak 25.2 MiB on PostgreSQL
(64 client connections, up to 100% of S) and 19.0 MiB on MySQL.

## Harness commits

The runs used this repository's `main` at 0165495 plus the release-gate suites of 4.17.1 to
4.20.0 and these suites (the commits of the patch that adds this directory). Recorded at run time
(`manifest.json`, `harness_commit`):

| Run | Recorded at run time | Commit |
| --- | --- | --- |
| bench-2026-11-proxy-421-p, -m | `f041a49d177ddd6ec1b4ba6a3a24988aefd9727c` | suites: refresh of the published figures for vericto-proxy 4.21.0 (day 1, PostgreSQL and MySQL) and a quick A/B gate against 4.20.0 |
| bench-2026-11-proxy-421-d2, -h2 | `30131ce` (the next commit) | suites: refresh for vericto-proxy 4.21.0, day 2 and one task or two, at day 1's S (9,667.7/s) |

Applied with `git am`, the commits get new ids; match them by message.

The per-run charts were not rendered (matplotlib was not available where the reports were built);
the site draws its own charts from these CSVs (vericto-fmw `landing/scripts/bench-extract.mjs`).

## Raw data

Kept by Vericto in the private, versioned S3 archive, one prefix per run id with the tarballs and
their `SHA256SUMS` (in each run directory here). Available on request:

| Prefix | Results + logs bytes |
| --- | --- |
| `bench-2026-11-proxy-421-p/` | 1,399,098,326 + 1,450,527 |
| `bench-2026-11-proxy-421-m/` | 8,131,640 + 996,970 |
| `bench-2026-11-proxy-421-d2/` | 449,315,334 + 776,313 |
| `bench-2026-11-proxy-421-h2/` | 1,541,520,459 + 1,926,222 |
| `bench-2026-11-proxy-421-025-q/` | 456,759,561 + 1,490,002 |
| `bench-2026-11-proxy-421-025-r/` | 2,201,576 + 446,572 |

## 0.25 vCPU (runs of 2026-10-31/11-01)

Owner request of 2026-10-31: the same published image and conditions (published profile, c7g,
TLS on both legs, enforce mode, 42 built-in rules, open loop, 3 interleaved repetitions of 300 s,
60 s warm-up), with the proxy's CPU quota at **0.25 vCPU** (one Graviton3 core, 25% CFS quota;
the runner's new size `0.25`). Two stacks, each in its own VPC (us-east-1c, us-east-1d).

| Directory | Run | Suite | What |
| --- | --- | --- | --- |
| `q025-pg/` | bench-2026-11-proxy-421-025-q | `pub421-025-pg` | PostgreSQL: closed-loop saturation of vericto-enforce at 0.25 vCPU (S = 4,237.1/s at 2 connections; the quota was already full at 1 connection: 4,137.2/s), then the headline curve at 10-100% of that S against direct, 3 repetitions |
| `q025-my/` | bench-2026-11-proxy-421-025-r | `pub421-025-my` | MySQL W3 oltp_read_only at the published rates that fit under the quota: 36, 107 and 178 transactions/s (10/30/50% of the pre-registered S = 356.6 tx/s), against direct, 3 repetitions |
| `report-q025/` | both | | `analysis/report.py --publishable --label "0.25 vCPU"` over `q025-pg` and `q025-my` |

Budget trims (fixed in the suites before the runs): no HAProxy baseline and no generator
validation (both independent of the proxy's quota, measured in `day1-pg/`); MySQL stops at 50%
of the published S, because 250 tx/s would need about 0.24 vCPU, the whole quota.

Validity: steal 0% on every host; no cell aborted. PostgreSQL 90%: one not-steady repetition,
replaced by its valid rerun. PostgreSQL 100%: one repetition saturated, the others and their
reruns not steady (the end of the curve). As for 0.5 vCPU, latency is quoted up to 70% of S:
at 80% the added p99 was 13.7 ms with an interval crossing zero (the quota's knee).

| Rate | Share of S | Proxy vCPU (share of quota) | Added p50 ms [95%] | Added p99 ms [95%] |
| --- | --- | --- | --- | --- |
| PostgreSQL 424/s | 10% | 0.038 (15%) | 0.096 [0.093, 0.099] | 0.14 [0.13, 0.16] |
| PostgreSQL 1,271/s | 30% | 0.099 (40%) | 0.086 [0.080, 0.091] | 0.14 [0.13, 0.16] |
| PostgreSQL 2,119/s | 50% | 0.155 (62%) | 0.083 [0.079, 0.086] | 0.27 [0.25, 0.30] |
| PostgreSQL 2,966/s | 70% | 0.215 (86%) | 0.083 [0.079, 0.087] | 0.94 [0.60, 1.29] |
| MySQL 36 tx/s | 10% of 356.6 | 0.040 (16%) | 1.18 [1.14, 1.21] per tx | 1.28 [1.26, 1.30] |
| MySQL 107 tx/s | 30% of 356.6 | 0.115 (46%) | 1.16 [1.02, 1.31] per tx | 1.71 [1.52, 1.90] |
| MySQL 178 tx/s | 50% of 356.6 | 0.187 (75%) | 1.15 [1.11, 1.19] per tx | 2.15 [2.03, 2.27] |

CPU fit (open-loop cells below 80% of S): PostgreSQL 0.0098 + 0.069 [0.067, 0.072] vCPU per
1,000 statements/s; MySQL 0.0044 + 0.064 [0.062, 0.067] per 1,000 statements/s.

Proxy memory (container cgroup, sampled every 30 s on the SUT as for day 1): peak 20.2 MiB on
PostgreSQL (64 client connections, up to 100% of S), 15.0 MiB on MySQL.

Harness commit recorded at run time: `0f90258` ("runner, suites: a 0.25 vCPU size ...", the
commit of the patch that adds this section; match it by message after `git am`). Proxy image:
the same digest as the other runs, copied to a separate bench-only ECR repository
(`vericto-bench/proxy-421-025`), deleted after the runs.
