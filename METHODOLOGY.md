# Methodology

This is the methodology of the vericto-proxy benchmark BENCH-2026-11, as
implemented in this repository. It is fixed before any run (pre-registered): the
suites in `suites/`, the validity rules in `runner/vbr/runner.py` and the
analysis in `analysis/report.py` are committed before a campaign starts, and the
run's manifest records the harness commit.

## 1. System under test

- **vericto-proxy 4.14.2** (documentation-only over 4.14.1; engine v4.3.0, **42 built-in rules**, default policy:
  critical and high block, medium flag, low and informational monitor, parse
  errors allowed and reported), pulled by digest. `RUST_LOG=info` is set
  explicitly. Memory telemetry buffer, gzip, batches of 500.
- Three configurations of the same image:
  - `vericto-offline`: no control-plane link; the built-in rules; no telemetry.
  - `vericto-enforce`: linked to `cpstub` over loopback (`http://127.0.0.1:9090`,
    accepted by the proxy for a loopback host); the same 42 rules, served from
    `engine-eval export-rules` so stub and proxy agree by construction;
    `monitor_mode=false`; the full telemetry path (serialise, sanitise,
    normalise, gzip, POST). **Headline target.**
  - `vericto-observe`: the same, `monitor_mode=true` (selected by the API key).
- Sizes: **0.5 vCPU** = one dedicated core with a 50% CFS quota (as a Fargate
  task of 0.5 vCPU); **1 vCPU** = one whole core, no quota; **2 x 0.5** = two
  tasks on two cores, the client spreading its connections over both.
- TLS cells: a throwaway CA and one server certificate (ECDSA P-256) are
  generated per run and never leave the run's hosts; every server presents it
  and clients encrypt without verifying it (`sslmode=require` / skip-verify), so
  the figures include the cost of encryption, not of certificate checks.

## 2. Baselines

Each baseline gets exactly the proxy's CPU budget (same cpuset and quota) and
runs one at a time, never alongside the target under test.

| Target | Configuration | Isolates |
| --- | --- | --- |
| `direct` | client to database | reference |
| `haproxy-tcp` | HAProxy 3.0.30, `mode tcp`, `nbthread 1` | the hop |
| `pgbouncer-session` | PgBouncer 1.24.1, `pool_mode=session`, pool = client connections, `max_prepared_statements=200`, TLS on both sides in TLS cells | protocol awareness without rules (PostgreSQL) |
| `proxysql` | ProxySQL 2.7.3, no query rules, multiplexing off, query digests on, one worker thread, TLS on both sides in TLS cells | a SQL-aware MySQL proxy (it parses for digests, it evaluates no rules) |

HAProxy relays TLS end to end in TLS cells (a TCP proxy cannot terminate
PostgreSQL's in-protocol TLS negotiation or MySQL's mid-handshake upgrade without
changing the client), so in those cells it pays no cryptography; its clean hop
cost comes from the TLS-off cells. The baselines locate costs; they are not a
ranking of products. Their configurations are in `runner/vbr/targets.py`.

## 3. Hosts

Published figures come from AWS us-east-1, two instances in a cluster placement
group in one AZ, in their own VPC (README, "Topology"):

- **SUT**, c7g.2xlarge (Graviton3, 8 physical cores, no SMT). cpusets: core 0 OS,
  interrupts and Docker; core 1 cpstub and the sampler; core 3 the proxy; core 4
  the second proxy task or the baseline; cores 5-7 the database.
- **Load generator**, c7g.xlarge: core 0 OS and interrupts, cores 1-3 the load tool.
- Cross-check: the SUT on c7i.2xlarge (Sapphire Rapids, SMT), the proxy on one
  hyperthread with its sibling idle.
- Databases: PostgreSQL 17.6 and MySQL 8.4.11 in containers, data on the
  instance's gp3 volume, `fsync`/`synchronous_commit`/`innodb_flush_log_at_trx_commit=1`
  on, buffers larger than the datasets (no Serverless scaling by construction).
- Recorded for every run (`manifest.json`, `host/provenance.sh`): lscpu, kernel,
  AMI, instance type, placement group, Docker version, clocksource, chrony, THP,
  cgroup version, steal time, every image digest, the cpuset plan.

## 4. Workloads

| ID | Workload | Tool | Notes |
| --- | --- | --- | --- |
| W1 | pgbench select-only (`-S`) | pgbench 17.6 `-R`, `-M simple|extended|prepared` | **headline PG: extended** |
| W2 | pgbench tpcb-like | pgbench, three modes | write-bound |
| W3 | sysbench oltp_read_only (10 point selects, 4 ranges, in a transaction) | vbench replay, text protocol, open loop; sysbench 1.0.20 closed loop for throughput | **headline MySQL** |
| W4 | ORM mix: 13 classes, about 80% allowed, 17% flagged, 3% blocked | vbench, PG extended, MySQL text | unchanged from Vericto's earlier (2026-10) Fargate measurements, for continuity |
| W5 | multi-row INSERT of 1-2,000 rows; `IN` list of 10-10,000 ids, 10/s on one connection | vbench | the ms/KB slope |
| W6 | DELETE/UPDATE without WHERE (blocked) vs with WHERE, on an always-empty table | vbench | cost of a block |
| W7 | new connection + TLS + authentication + one PK lookup | vbench `-conn newconn` | allowed on a local database only |
| W8 | PK-range SELECT returning 10 KB, 100 KB, 1 MB; plain, and with a masked 24-byte column | vbench | per-byte cost at reduced rates |

Protocol note for every PostgreSQL figure: the proxy evaluates a statement at
`Parse` and passes `Bind`/`Execute` through. In `prepared` mode a statement is
evaluated once per connection, so W1/W2 `prepared` measure almost only
forwarding; `extended` and `simple` evaluate every execution.

Every declared verdict is checked before the run by `engine-eval verdicts`
(the proxy's engine and rules) and against the running proxy by `vbench probe`;
a disagreement stops the run. Datasets are seeded deterministically and their
checksums recorded (pgbench `-i -s 100`; sysbench 8 x 1,000,000 rows,
`--rand-seed=1`; the vbench ORM schema; 10,000 payload rows).

## 5. Load generation

- **Open loop for every latency figure.** vbench: request *i* is due at
  `start + i/rate` (or Poisson gaps with a seed); a dispatcher hands it to an
  idle connection of a fixed pool (by default `max(8, rate x 10 ms x 4)`), or
  queues it. **Latency = completion minus intended send time**; service time and
  queue wait are recorded apart, plus the dispatcher's own lateness. No request
  is skipped silently: every request of the schedule is completed, or counted as
  unsent (cell stopped, queue overflow) or incomplete (still in flight after the
  drain). A cell whose achieved rate falls below 99% of offered, or whose queue
  passes 10 x rate, is **saturated**: kept, drawn as the end of the curve, never
  quoted as latency.
- pgbench `-R` is open loop with a Poisson schedule per client; its
  per-transaction log gives the schedule lag, which is added to the transaction
  time, so pgbench latency is also from the intended time.
- sysbench's `--rate` latency excludes queue time: sysbench is used closed loop
  only.
- Histograms: HdrHistogram, 1 us to 120 s, 3 significant digits; one interval
  per 10 s (`latency.hlog`, standard HdrHistogram log, and `intervals.jsonl`).
- **Generator validation, in every campaign:** the database is paused for 1 s
  once a minute during an open-loop cell; the cell must show a max of about 1 s
  and about 1% of requests above 500 ms (a closed-loop generator would show one
  slow request per pause). The result is in the report.
- Closed loop (saturation): concurrency 1, 2, 4 ... 128, 2 minutes per step,
  until throughput grows less than 3% per doubling. S, the maximum of
  `vericto-enforce` at a size, sets the open-loop rates.

## 6. Cells, order and repetitions

- 60 s warm-up discarded, **300 s measured**, 30 s cool-down, then a check that
  the database has no active session.
- Rates: the same absolute values for every target of a curve, 10, 30, 50, 70,
  80, 90 and 100% of S.
- Order: within a repetition, every target runs at a rate before the next rate,
  in an order from a seeded balanced Latin square (Williams design); rates are
  shuffled with the seed, the saturating ones last. The seed is in the manifest.
- 3 repetitions per day; the headline curves again on a second day on a freshly
  launched SUT at day 1's rates (`suites/day2.toml`). What BENCH-2026-11 actually
  ran (fewer repetitions for some curves, one on day 2) is in section 11.

## 7. Validity rules (no outlier removal)

A repetition is invalid only for one of these reasons, recorded with it, rerun
once, and kept in the raw data:

- unexpected errors above 0.1% of statements;
- load-generator CPU above 70% of its cores;
- steal time above 1% on any host;
- CFS throttling of a container without a quota;
- a failed probe or setup;
- not steady: the window split in 10-s parts, the achieved rate varies by more
  than 1% (three Poisson standard deviations when larger, for pgbench), or the
  p50 of the last third differs from the first third by more than 10%.

## 8. Analysis

- Per cell: percentiles of the cell's merged histogram; a block bootstrap over
  its intervals gives a 95% interval per percentile.
- **Added latency** per repetition: target minus `direct` at the same rate in the
  same repetition (paired), per percentile; across repetitions the mean with a
  Student t 95% interval (n = 3 per day; n = 6 for the headline across days).
  An interval containing zero is written "not distinguishable from the direct
  path", never as zero or negative.
- Decomposition at the same rate: hop (haproxy minus direct), protocol
  awareness (pgbouncer/proxysql minus haproxy), evaluation (offline minus
  haproxy), telemetry (enforce minus offline), observe minus enforce.
- **Cost per 1,000 QPS**: the proxy container's cgroup CPU sampled every second,
  linear fit against achieved statements/s over open-loop cells below 80% of S
  (slope and intercept with intervals); in money at the Fargate ARM64 list price
  (USD 0.03238 per vCPU-hour), at 50% and 70% target utilisation.
- Bytes per second per direction and the total against the caps, in every cell.

## 9. Network traffic caps

The benchmark measures the proxy, never the network. Total traffic must stay
far below the ~1 Gbps at which AWS may throttle or block an instance, so that no
figure is shaped by a network limit. This is a project rule, enforced by
`internal/netcap` and `hostmon`, and contributions that loosen it are not merged:

| Scope | Hard cap (abort) | Design target (warning; the pre-flight refuses plans above it) |
| --- | --- | --- |
| Each component (a host's interface, an intermediary's both hops plus telemetry, the database's port) | 400 Mbps | 300 Mbps |
| Aggregate of every component running at the same time | 800 Mbps | 600 Mbps |

- **Counting.** The same bytes are counted at every interface they cross: a
  byte relayed by the proxy counts at the load generator's NIC, at the SUT's
  NIC, twice at the proxy (in and out) and at the database. Components share
  counters on purpose.
- **Guard.** Interface counters, nftables counters per port and direction, and
  cgroup CPU are sampled once a second on every host. Three consecutive
  one-second samples above a hard cap abort the cell (recorded as
  `aborted: network cap`), and no higher rate of that curve is run.
- **Pre-flight.** Before every open-loop curve, a 10-s probe measures bytes per
  request at each component; with a 5% allowance for protocol framing, the
  expected traffic of every planned rate is checked against the design targets.
  Rates that would pass one are not run, and the curve is drawn as stopped at
  the cap: **the rates are reduced, never the margin.**
- **Harness traffic counts too.** The progress and final uploads of the results
  to S3 are capped at 8 MB/s and kept on the OS core (BENCH-2026-11's day 1
  showed one-second bursts of about 850 Mbps on the load generator's NIC while
  an uncapped upload ran).
- **What is reported instead of high traffic.** Curves that would need more
  traffic to saturate stop at the cap and say so; throughput at large result
  sizes is therefore not measured. Every cell reports bytes per second per
  direction (client to target, target to client, target to database, database
  to target, telemetry egress, the NICs) and bytes per request, and the per-MB
  cost is published so a reader can extrapolate. Network limits of AWS or of the
  proxy are deliberately not measured, and no iperf or bandwidth test of any
  kind is part of the harness.

## 10. Limitations

- Loopback between an intermediary and its database is not a network;
  Vericto's earlier Fargate measurements (behind an NLB, with Aurora) cover the
  in-VPC case, and they are not part of this repository.
- The stub is not the API: the proxy's telemetry work is measured in full, the
  backend's is not.
- Built-in ruleset only; custom rules and agent-access allowlists add cost that
  is not measured; masking only in the W8 cells. In 4.14.x masking rewrites the
  forwarded SQL (the database computes the masked value) and results are relayed
  untouched.
- At 0.5 vCPU the CFS quota creates tail waits that are not the proxy's code;
  the 1-vCPU curve is the reference for tails.
- Graviton3 and Sapphire Rapids only.
- Cells are 5 minutes; memory growth over hours is not covered.
- Statements are legitimate SQL; adversarial input belongs to fuzzing.

## 11. BENCH-2026-11: the campaign matrix and what was run

The full pre-registered matrix is `suites/published.toml` (day 1), written by
`suites/generate.py`: 1,455 cells and at most 118 machine-hours by the planner
(`python3 runner/run.py --suite suites/published.toml --plan`), plus
`suites/day2.toml` and the `suites/c7i.toml` cross-check. BENCH-2026-11 ran a
subset of it:

- **Proxy version.** We chose vericto-proxy 4.14.2 on 2026-10-19, the latest
  release, instead of waiting for a 4.14.3 with the log-level and size-comment
  fixes. 4.14.2 is documentation-only over 4.14.1; its default log filter is
  still `info,vericto_proxy=debug`, so the harness sets `RUST_LOG=info`.
- **Budget trim of day 1** (2026-10-19). The budget for this campaign was about
  USD 45 of AWS spend for the dry run and the campaign (about USD 0.51 per hour for both
  hosts and the NAT gateway). In order: (1) the c7i cross-check is not run;
  (2) every non-headline open-loop curve runs 2 interleaved repetitions instead
  of 3; (3) the two headline curves keep 3. That gives 1,116 cells and at most
  89.8 planner hours, about 70 in practice, because closed-loop step-ups stop at
  the knee and the network pre-flight drops rates above the traffic targets.
  Saturated cells are not rerun.
- **Run order.** Saturation first (it sets S), the generator validation next,
  then the two headline curves, then the rest of the matrix, so that a stop by
  the runtime guard loses the least.
- **Day-1 core cut** (2026-10-20). Day 1 was stopped after the MySQL headline
  curve (`head-my-w3-05`). It holds every closed-loop saturation curve, the
  generator validation and both headline curves with 3 repetitions; 2 cells of
  `decomp-pg-w1` that had completed are kept as extra data. The PostgreSQL
  two-task curve (`suites/core-h2.toml`) ran on its own stack instead: 2 x 0.5
  vCPU against `direct` at 30 to 220% of day 1's S at 0.5 vCPU, and 1 x 0.5 at
  30, 90 and 120% on the same host for a like-for-like comparison, 3
  repetitions. It started after `head-my-w3-05`, so that both stacks stayed
  under one aggregate traffic cap.
- **Day 2 at one repetition** (2026-10-20). Day 2 runs the two headline curves
  once on a freshly launched stack at day 1's absolute rates (about 4.6 hours).
  The headline rows pool day 1 and day 2 (n = 4, not the 6 of section 8), and
  the report's between-days table flags every day-2 value outside day 1's 95%
  interval.
- **Not run in this campaign:** the size sweep, large results and masking, the
  full decomposition, 1 vCPU, PgBouncer and ProxySQL, TLS off, the protocol
  modes, the ORM mix, blocked statements, connection setup and the c7i
  cross-check. They are `suites/published.toml` minus what ran, for a follow-up
  campaign.

The runs, their harness commits and the combined report are in
[results/bench-2026-11/](results/bench-2026-11/README.md).
