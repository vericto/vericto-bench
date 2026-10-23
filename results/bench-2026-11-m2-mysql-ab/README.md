# BENCH-2026-11 M2 MySQL A/B: vericto-proxy 4.15.0 (VERICTO_POLICY_RULES=off) against 4.14.3

Status: run complete (2026-10-22), stack destroyed. Not published: profile `quick`. This is the
targeted diagnostic for the one cell that failed the M2 quick run
([`../bench-2026-11-m2-quick`](../bench-2026-11-m2-quick/README.md)): MySQL W3 at 50% of S.

**Result: the difference holds, but it is smaller than the quick run measured and it is not
specific to 50% of S.** By the pre-registered rule (the 95% interval of the paired difference
at 50% of S excludes 0 at p50 or p99) it holds: p99 is +0.076 ms [0.017, 0.135]. p50 is
+0.040 ms [−0.002, 0.082], about a third of the quick run's +0.112. The same shift shows at
40% of S, and at 60% the intervals contain 0. Pooled over all 24 pairs, 4.15.0(off) costs
**+0.047 ms [0.025, 0.068] at p50 (+1.1%)** and **+56 vCPU-µs [34, 79] per transaction
(+3.6%)**, about 3.5 µs per statement. The proxy was never CPU-throttled at these rates.
The CPU profiles do not resolve the difference, and they show no time in the code the flag
turns off (see below).

## What ran

- Suite [`suites/m2-mysql-ab.toml`](../../suites/m2-mysql-ab.toml), fixed before the run. It
  ran MySQL W3 only: the oltp_read_only replay, text protocol, TLS on both legs, 0.5 vCPU, and
  the `vericto-enforce` configuration (42 built-in rules, telemetry to the local stub,
  `RUST_LOG=info`). It used the same warm-up (15 s) and duration (60 s) per cell as the quick
  suite. The targets were 4.14.3 and 4.15.0 with `VERICTO_POLICY_RULES=off`; `direct` was not
  run, so this run measures differences between the two releases, not added latency.
  - `sat-my-w3-05`: closed loop, S = the maximum of 4.14.3 in this session: **356/s** (quick
    run: 363/s). The maximum of 4.15.0(off) was 346/s (−2.7%; one repetition).
  - `ab-my-w3-05`: 40, 50 and 60% of S (142.3, 177.9 and 213.5/s), 8 repetitions. In each
    repetition the rates are shuffled, and at each rate the two releases run next to each
    other: 4.14.3 first in odd repetitions, 4.15.0(off) first in even ones
    (`order = "listed-reversed"`). So each release runs first 4 times per rate.
  - `swap-my-w3-05`: 50% of S, each release twice back to back (4.14.3, 4.14.3, 4.15.0,
    4.15.0), then the mirror order. This controls for an order or warm-up effect.
  - `prof-my-w3-05`: 50% of S, each release first once and second once, with `perf record`
    of the proxy for 30 s after the warm-up (`host/profile.sh`).
- Images, by digest, as in the quick run (the same digests on Docker Hub and GHCR):
  - 4.14.3 `sha256:66fa5e986f2b63089c5bcf07324bc2a0501920e6d180997c04d0526cf75c7354`
  - 4.15.0 `sha256:f4fd543e764204162a04320feefa54e52ac3a1670ea3d8419d32987f70d75124`
- Hosts: SUT c7g.2xlarge and load generator c7g.xlarge in one cluster placement group in
  us-east-1, the BENCH-2026-11 setup.
  - The latest AL2023 AMI (2023.12.20261021, kernel 6.18.54) from its public SSM parameter,
    with OS updates applied at boot.
  - The base images are the current digests of their pinned tags (checked on 2026-10-22,
    unchanged from `versions.lock`).
  - The traffic caps of the harness applied. No steal time was recorded and no cell had a
    warning.
- Cells: 73 recorded; 62 used.
  - The 8 profiled cells and their 8 reruns are invalid by design: under perf, p50 drifts
    35–77% and p99 reaches 54–66 ms. They are used only for the profiles.
  - The network pre-flight probe of the profiled curve was also profiled. It is not used.
- Harness: base origin/main + patch 0004, plus the changes in this commit (below).
  `manifest.json` records `6533a02` (0004).
  - On the first attempt the SUT setup failed: the FlameGraph clone hit the first minutes
    after the NAT gateway was created, when egress did not work. The load generator then
    stopped, and nothing was measured.
  - The SUT setup was resumed by hand, and the load generator was replaced
    (`terraform apply -replace`).
  - The retry now in `host/setup.sh` was added after that. The SUT ran the setup script
    without the retry; everything else ran from this commit.
- Raw data: in Vericto's private archive under the prefix `bench-2026-11-m2-mysql-ab-1/`.
  [`run/SHA256SUMS`](run/SHA256SUMS) lists the tarballs. Instance ids, AMI ids, host names and
  private addresses are redacted in `run/manifest.json`.
- Cost: about USD 1.5 (2.3 h of the two instances, the NAT gateway and EBS).

## Paired difference 4.15.0(off) minus 4.14.3

Latency is per transaction (16 statements), in ms; CPU is the proxy container's vCPU-µs
per achieved transaction. Values are means with Student t 95% intervals, n = 8 pairs.

| Rate (% of S) | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- |
| 142.3/s (40%) | **+0.067 [0.037, 0.098]** | **+0.079 [0.011, 0.146]** | −0.046 [−0.760, 0.668] | **+71 [38, 105]** |
| 177.9/s (50%) | +0.040 [−0.002, 0.082] | **+0.076 [0.017, 0.135]** | +0.154 [−0.841, 1.149] | **+45 [8, 83]** |
| 213.5/s (60%) | +0.032 [−0.021, 0.086] | +0.025 [−0.104, 0.154] | +0.887 [−0.628, 2.402] | +53 [−10, 115] |
| pooled, 24 pairs | **+0.047 [0.025, 0.068]** | **+0.060 [0.015, 0.105]** | | **+56 [34, 79]** |

The levels at 50% of S:
- p50 is 4.220 ms for 4.14.3 and 4.260 ms for 4.15.0(off).
- p99 is 7.360 ms and 7.436 ms.
- CPU is 1,560 and 1,606 µs per transaction.
- The proxy was not CFS-throttled at 40% or 50%, and at 60% it was throttled for less than
  0.1 ms per second.

**Order.** Splitting each rate's pairs by which release ran first gives overlapping intervals
(e.g. 50% p50: +0.027 [−0.039, 0.093] with 4.14.3 first, +0.053 [−0.043, 0.149] with 4.15.0
first). The difference does not depend on the order.

**Back-to-back control** (50% of S, n = 2 blocks; low power, read as a check only):
- Release difference: +0.008 ms [−0.017, 0.033] at p99, −0.008 [−0.135, 0.119] at p50, and
  −1 µs/tx CPU.
- Position effect (the second back-to-back run of a release minus the first):
  −0.002 ms [−0.112, 0.108] at p50.

So there is no warm-up or carry-over effect at the scale of the difference. This control is
too small to confirm or refute a 0.04 ms shift on its own.

**Against the quick run.**
- The quick run's +0.112 ms at 50% (n = 3) is about 2.5 times this run's 50% estimate.
- The quick run's "absent at 30% and 70%" is not confirmed either: here the shift is largest
  at 40%.
- Read together, the data show a small cost that does not depend on the rate: about 3–4% more
  proxy CPU per transaction, and +0.03 to +0.07 ms at p50. The quick run's single failing cell
  was this cost plus noise; the cell itself was not special.

Every value is in [`run/report/ab.md`](run/report/ab.md) (per repetition too), and the
machine-readable values are in `run/report/ab.json`. `run/report/compare.md` is
`analysis/compare.py` on the same run; it has no added-latency columns, because `direct` was
not run.

## CPU profiles at 50% of S

There are 4 profiled cells per release, 30 s each. perf sampled at 499 Hz with DWARF unwinding
(`.eh_frame`). The release binaries keep their symbols but omit frame pointers, so
frame-pointer stacks would be truncated. There are about 47,000 samples per release.
- Flame graphs: [`profiles/flamegraph-4.14.3.svg`](profiles/flamegraph-4.14.3.svg) and
  [`profiles/flamegraph-4.15.0-off.svg`](profiles/flamegraph-4.15.0-off.svg).
- The differential:
  [`profiles/flamegraph-diff-4.15.0-off-vs-4.14.3.svg`](profiles/flamegraph-diff-4.15.0-off-vs-4.14.3.svg).
- The merged folded stacks: `profiles/*.folded.gz`.

- **Totals:** 93.31 G cycles for 4.14.3 and 93.02 G for 4.15.0(off), so −0.3%. In the
  profiled cells the CPU per transaction is 2,310 against 2,317 µs (+0.3%). perf adds about 48%
  CPU there, and the proxy is throttled. At this resolution the profiles cannot see the 3.6%
  measured without perf.
- **Statement evaluation** (parse + rules + sensitive columns + access, `evaluator::evaluate*`
  inclusive): 25.00% of samples against 25.04%.
- **The paths the flag turns off take no time with it off.** No samples are in
  `evaluate_with_context`, `policy_rules`, `tx_state`, the `SET vericto.*` interception, or
  the connect-attribute parsing. One sample in ~47,000 is in `drop_in_place<Vec<PolicyHit>>`:
  the new, always-empty `policy_hits` field of the engine's `EvaluationOutcome` being dropped.
- **rustls-webpki 0.103.16 / webpki-roots 1.0.10:** no samples. Certificate verification runs
  once per connection, and the connections are pooled. TLS record work (`rustls`, `ring`
  AES-GCM) changes by less than 0.1 point.
- **What does change: how the evaluation is split into functions, and its size.**
  - In 4.15.0, `evaluator::evaluate` calls a separate `decide()`, where 4.14.3 inlined it into
    `evaluate_message`.
  - The engine's `evaluate_rules` became `evaluate_rules_with(.., None, &[])`. It adds a
    `.filter()` on every rule (built-in rules pass the `RuleType::Custom` test), and folds the
    exemption caps over an empty slice for every violation. The new `FilterMap::next` frame is
    0.31% self in 4.15.0 and does not exist in 4.14.3.
  - `EvaluationOutcome` (+3 fields) and `TelemetryEvent` (+8 `Option<String>`) are larger and
    move by value.
  - The binary is 18% larger (17.5 MB to 20.7 MB; engine 4.4.0 brings the policy module and
    `regex`), which changes code layout.
  - Each of these shifts is a few tenths of a point. None of them alone explains 3.6%. Their
    sum, plus layout effects, is the likely source.

Likely code paths, in order (vericto-proxy origin/main 282f5b1, vericto-engine v4.4.0):

1. The engine's always-on wrapper: `RuleEngine::evaluate_rules` became
   `evaluate_rules_with` (the per-rule filter and the caps fold), and `EvaluationOutcome`
   grew. This runs on every statement, flag or not. The M1 micro-benchmark measured
   `evaluate()` against v4.3.0 with a ≤ 1.05 budget; the end-to-end +3.6% per transaction
   is inside that ratio, but this run's interval, about [1.02, 1.05], reaches its edge.
2. `evaluator::evaluate` / `decide()` in the proxy (4.15.0 split out the outcome mapping)
   and the larger `TelemetryEvent` (8 new `skip_serializing_if` fields per event).
3. Not supported by the data:
   - session context capture (`mysql_handshake_context`): only with the flag on, and per
     connection;
   - the `SET vericto.*` interception: `session_policy` is `None` with the flag off;
   - the transaction-status tracking of 0056-v2: `tx_state` and the relay tracker are `None`
     with the flag off, which leaves one `Option` check per read;
   - the `evaluate()` / `evaluate_with_context()` dispatch: with the flag off,
     `policy_ctx` is `None` and `evaluate_message` is called as before;
   - the rustls-webpki / webpki-roots bump.

To confirm the first two without the bench, run the engine micro-benchmark of v4.3.0 against
v4.4.0 on the MySQL oltp_read_only statements on Graviton, and count instructions with
`perf stat` on a fixed replay.

## Files

- `run/manifest.json`, `run/cells.jsonl`, `run/statements.jsonl`, `run/verdicts.jsonl`: the run.
- `run/report/`: `report.py`'s report, `ab.md` / `ab.json` (`analysis/ab.py`) and
  `compare.md` / `compare.json`. Regenerate them with:

      python3 analysis/ab.py results/bench-2026-11-m2-mysql-ab/run \
          --baseline vericto-enforce-4143 --candidate vericto-enforce-4150-off

- `profiles/`: the flame graphs (FlameGraph 41fee1f) and the merged folded stacks.

## Harness changes in this commit

- Suite option `order = "listed-reversed"` (`runner/vbr/suite.py`). Targets run in the listed
  order in odd repetitions and in the reverse order in even ones, for every rate of the
  repetition. A curve now refuses a target listed twice; list an alias variant instead.
- Suite option `profile_s` (`runner/vbr/runner.py` `_Profiler`, `host/profile.sh`). It runs
  perf record of the proxy under test on the SUT after the warm-up (two-host only), on the
  spare core. The folded stacks and `perf report` go into the cell directory.
  - `host/setup.sh` installs perf and FlameGraph (pinned commit, cloned with retries) on the
    SUT.
  - It lets the bench user run exactly `host/profile.sh` through sudo.
- `host/setup.sh` applies OS updates at boot (`dnf upgrade --releasever=latest`).
  `host/provenance.sh` records the installed kernels and the system-release package.
- `analysis/ab.py` (with tests): paired A/B per rate, split by run order, and the
  back-to-back control.
- `suites/m2-mysql-ab.toml`; `max_hours` for it is 5 h. The harness zip leaves out
  `terraform/archive` state and providers and the Terraform plan files.
