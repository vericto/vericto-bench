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
