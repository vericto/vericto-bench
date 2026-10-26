# BENCH-2026-11 M2 fix A/B: vericto-proxy 4.15.3 candidate (VERICTO_POLICY_RULES=off) against 4.14.3

Status: run complete (2026-10-23), stack destroyed. Not published: profile `quick`. This is the
re-measurement after the fix for the regression found by
[`../bench-2026-11-m2-mysql-ab`](../bench-2026-11-m2-mysql-ab/README.md) (4.15.0 with the flag
off: +0.047 ms p50, +3.6% proxy CPU per transaction on MySQL W3).

**Result: no regression in any cell; the candidate is faster and cheaper than 4.14.3.** At every
rate of MySQL W3 and PostgreSQL W1 the upper end of the 95% interval of the paired difference
(candidate minus 4.14.3) is at or below 0 for p50, p99 and CPU per transaction, except MySQL p50
at 40% of S, whose interval contains 0. The pre-registered rule (the interval includes 0 or lies
below it) passes everywhere. Most intervals lie entirely below 0, so the two releases are not
"indistinguishable": the candidate is measurably better.

## What was measured

- The candidate is vericto-proxy 4.15.3 as delivered: origin/main 4.15.2 (Chainguard
  `glibc-dynamic` runtime) plus the 4.15.3 change. The change serializes telemetry batches
  straight from the events instead of building a `serde_json::Value` copy of every event first,
  and moves (instead of copying) a flagged statement's rule code and AST path. It was built for
  linux/arm64 with the repository's Dockerfile from the patched tree and run by digest from a
  bench-only registry:
  `sha256:ad4afa7abbcadb1564da1413b68f7d5a3c473417b373163c9d6ab3c8a446adaf`. It ran with
  `VERICTO_POLICY_RULES=off` (the default).
- The baseline is 4.14.3 by digest, as in m2-mysql-ab:
  `sha256:66fa5e986f2b63089c5bcf07324bc2a0501920e6d180997c04d0526cf75c7354`.
- Suite [`suites/m2-fix-ab.toml`](../../suites/m2-fix-ab.toml), fixed before the run:
  - MySQL W3 (oltp_read_only replay, text protocol, TLS on both legs, 0.5 vCPU): 40, 50 and 60%
    of S, 8 repetitions;
  - PostgreSQL W1 (pgbench select-only, extended protocol, TLS, 0.5 vCPU): 30 and 50% of S,
    8 repetitions;
  - S per engine is the closed-loop maximum of 4.14.3 in this session: **361/s** (MySQL) and
    **5,972/s** (PostgreSQL);
  - in each repetition the rates are shuffled and every rate runs both releases next to each
    other, 4.14.3 first in odd repetitions and the candidate first in even ones
    (`order = "listed-reversed"`);
  - `vericto-enforce` configuration (42 built-in rules, telemetry to the local stub,
    `RUST_LOG=info`), 15 s warm-up and 60 s per cell, as m2-mysql-ab.
- Hosts: SUT c7g.2xlarge and load generator c7g.xlarge in one cluster placement group in
  us-east-1. The latest AL2023 AMI (2023.12.20261021, kernel 6.18.54) from its public SSM
  parameter, with OS updates applied at boot. Base images at the digests of `versions.lock`.
- Cells: 94 recorded, 94 valid (no setup failure, no CFS throttling, no warning).
- Raw data: in Vericto's private archive under the prefix `bench-2026-11-m2-fix-ab-3/`;
  [`run/SHA256SUMS`](run/SHA256SUMS) lists the tarballs. Account, instance, AMI, host and
  registry identifiers are redacted in `run/`.
- Cost: about USD 2.3 for the whole investigation (this run, two aborted attempts, a
  profiling host and the bench-only registry).

## Paired difference, candidate minus 4.14.3

Latency per transaction in ms; CPU is the proxy container's vCPU-µs per achieved transaction.
Means with Student t 95% intervals, n = 8 pairs per rate.

| Cell | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- |
| MySQL W3, 144.4/s (40%) | −0.022 [−0.069, +0.026] | **−1.709 [−1.794, −1.624]** | **−1.055 [−1.706, −0.404]** | **−69 [−109, −30]** (−4.6%) |
| MySQL W3, 180.5/s (50%) | **−0.057 [−0.078, −0.037]** | **−1.787 [−1.837, −1.737]** | **−1.527 [−2.291, −0.763]** | **−122 [−141, −103]** (−8.1%) |
| MySQL W3, 216.6/s (60%) | **−0.096 [−0.119, −0.073]** | **−1.807 [−1.872, −1.742]** | −0.693 [−1.694, +0.307] | **−83 [−112, −53]** (−5.5%) |
| PostgreSQL W1, 1,791.7/s (30%) | −0.002 [−0.005, +0.000] | **−0.824 [−0.938, −0.709]** | **−1.875 [−3.388, −0.362]** | **−4.1 [−6.0, −2.3]** (−4.4%) |
| PostgreSQL W1, 2,986.2/s (50%) | **−0.002 [−0.004, −0.001]** | **−1.914 [−1.947, −1.880]** | **−1.948 [−3.308, −0.588]** | **−4.1 [−5.2, −3.1]** (−4.5%) |

Levels at 50% of S: MySQL p50 4.103 / 4.046 ms, p99 7.098 / 5.311 ms, CPU 1,511 / 1,389 µs per
transaction (4.14.3 / candidate); PostgreSQL p50 0.365 / 0.363 ms, p99 2.727 / 0.813 ms. The
split by which release ran first gives overlapping intervals (`run/report/ab-*.md`).

Closed-loop maximum (one repetition, for reference): MySQL 361/s for 4.14.3 and 401/s for the
candidate (+11%); PostgreSQL 5,972/s and 6,357/s (+6.4%).

## Why the regression was there, and why the tail moved

- With the flag off, 4.15.0 runs the same number of instructions per statement as 4.14.3:
  callgrind on a fixed MySQL oltp_read_only replay gives 3.73 M user-space instructions per
  transaction for both (within 0.2%), with the same system calls and page faults. The engine's
  `evaluate()` is within 0.2% of 4.3.0's. On Graviton (`perf stat`, the same replay) 4.15.0 needs
  about 2% more user cycles for the same instructions. The +3.6% of m2-mysql-ab is code layout and
  cache behaviour of a binary 18% larger, not extra work; there was nothing flag-gated to remove.
- The fix therefore removes work that 4.14.3 also did. Building a `serde_json::Value` for each
  telemetry batch copied every field of every event (one per statement) into a map entry and a
  string of its own. It cost more than 10% of the proxy's user-space instructions: 3.35 M against
  3.73 M per transaction on the same replay, −9.9% on Graviton.
- That serialization ran on an async worker for each batch of up to 500 events, so the statements
  scheduled on that worker waited for it. That is where most of the p99 and p99.9 gain comes
  from, on both engines.
- The candidate also changes the runtime base (4.15.2: Chainguard, glibc 2.44; 4.14.3:
  Debian 12, glibc 2.36). This run measures the release as delivered and does not separate the
  two. On the same Debian runtime as 4.14.3 the code change alone measured −9.9% user
  instructions and about −4% total cycles per transaction on Graviton (`perf stat`, fixed
  replay, 4 pairs).

## Files

- `run/manifest.json`, `run/cells.jsonl`, `run/statements.jsonl`, `run/verdicts.jsonl`: the run.
- `run/report/`: `report.py`'s report, and `ab-mysql.md` / `ab-pg.md` (with `.json`). Regenerate
  them with:

      python3 analysis/ab.py results/bench-2026-11-m2-fix-ab/run --baseline vericto-enforce-4143 \
          --candidate vericto-enforce-cand-off --ab-curve ab-my-w3-05 --swap-curve none --out DIR
      python3 analysis/ab.py results/bench-2026-11-m2-fix-ab/run --baseline vericto-enforce-4143 \
          --candidate vericto-enforce-cand-off --ab-curve ab-pg-w1-05 --swap-curve none --out DIR

## Harness changes in this commit

- A suite variant may take the run's own image: `image = "PROXY_IMAGE_OVERRIDE"`
  (`runner/vbr/suite.py`, `runner/vbr/runner.py` `variant_ref`, with tests). The image is
  `terraform -var proxy_image_override=<repo>@sha256:...`, pinned by digest, never read from
  `versions.lock`. The load generator's user-data now passes `PROXY_IMAGE_OVERRIDE` to the
  runner; before this, the override was pulled but never used.
- An override in a private Amazon ECR repository: Terraform grants both host roles pull on
  exactly that repository, and `host/pull-images.sh` logs in to that registry with the host role.
- `runner/vbr/topo.py`: files are copied into containers with `docker cp -a` only for a non-root
  owner. `-a` needs `getent` in the image, which the shell-less proxy images (4.15.2 and later)
  do not have; every current caller copies root-owned files, so nothing changes for them.
- `suites/m2-fix-ab.toml`; `max_hours` for it is 5 h.
- Run notes: the first attempt stopped at the variant check (the override not passed to the
  runner); the second failed every candidate cell at the certificate copy (`docker cp -a`).
  Both were destroyed. This run (`-3`) ran from this commit's harness. Its manifest records
  `218bcfb`, the local harness commit before the results were added.
