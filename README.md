# vericto-bench

A reproducible benchmark of what [vericto-proxy](https://github.com/vericto/vericto-proxy)
adds to the path between an application and its PostgreSQL or MySQL database:
latency (as curves against offered load), CPU cost per 1,000 queries per second,
and per-byte cost of large results. It runs the same workloads against the direct
path and against a TCP hop (HAProxy), a protocol-aware pooler (PgBouncer) or SQL
proxy (ProxySQL), so the proxy's cost can be split into its parts. Anyone can run
it in their own AWS account, without Vericto's backend, and get the raw data
behind every figure.

License: Apache-2.0 (see [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md)).
The harness never vendors proxy source: it pulls the proxy image by digest.

> **Status (2026-10-21): the first campaign, BENCH-2026-11, is complete (day 1 and
> day 2 of the publishable core, on EC2) and its results are published.**
> Write-up: [vericto.com/benchmarks/proxy-latency](https://vericto.com/benchmarks/proxy-latency).
> Manifests, cell results, reports, charts, archive checksums and the harness commit
> of every run: [results/bench-2026-11/](results/bench-2026-11/README.md).
> The methodology is in [METHODOLOGY.md](METHODOLOGY.md); what this campaign ran of
> the full matrix is in its [section 11](METHODOLOGY.md#11-bench-2026-11-the-campaign-matrix-and-what-was-run).

## Results at a glance (BENCH-2026-11)

Conditions: vericto-proxy 4.14.2 (engine v4.3.0, 42 built-in rules, default
policy) as `vericto-enforce`, with telemetry to the local control-plane
stand-in; 0.5 vCPU (one Graviton3 core, 50% CFS quota); TLS on both legs; SUT
c7g.2xlarge and load generator c7g.xlarge in one cluster placement group,
us-east-1a. Added latency is the target minus `direct` at the same offered rate,
paired within each repetition, open loop and measured from the intended send
time: mean and Student t 95% interval over n = 4 repetitions (3 on day 1, 1 on
day 2). S, the closed-loop saturation rate of `vericto-enforce` at 0.5 vCPU, is
6,033/s for PostgreSQL and 357/s for MySQL. All figures are from
[results/bench-2026-11/report/](results/bench-2026-11/report/report.md).

| Headline workload | Offered rate (% of S) | Added p50 ms [95%] | Added p99 ms [95%] | Added p99.9 ms [95%] |
| --- | --- | --- | --- | --- |
| PostgreSQL W1: pgbench select-only, extended protocol | 603/s (10%) | 0.119 [0.117, 0.121] | 0.187 [0.182, 0.191] | 2.709 [2.665, 2.753] |
| | 1,810/s (30%) | 0.119 [0.116, 0.122] | 1.312 [1.209, 1.415] | 3.413 [3.219, 3.608] |
| | 4,223/s (70%) | 0.145 [0.135, 0.156] | 3.634 [2.941, 4.327] | 17.021 [11.847, 22.194] |
| MySQL W3: sysbench oltp_read_only (rates in transactions/s; 10 point selects and 4 ranges per transaction) | 36/s (10%) | 1.724 [1.660, 1.789] | 1.958 [1.865, 2.051] | 4.192 [4.043, 4.342] |
| | 178/s (50%) | 1.598 [1.557, 1.639] | 4.028 [3.896, 4.160] | 5.645 [4.707, 6.583] |
| | 250/s (70%) | 1.570 [1.554, 1.585] | 4.357 [4.197, 4.517] | 11.024 [9.418, 12.630] |

- **The TCP hop alone** (HAProxy with the same CPU budget, same rates) adds
  0.032 to 0.038 ms at p50 on PostgreSQL and 0.350 to 0.508 ms on MySQL.
- **Near saturation the tail grows**: added p99 is 43.097 ms on PostgreSQL at 80%
  of S and 32.875 ms on MySQL at 90% of S (n = 3 each).
- **CPU cost** (linear fit over open-loop cells below 80% of S): 0.1066 vCPU per
  1,000 QPS [0.1039, 0.1093] on PostgreSQL and 0.0975 [0.0959, 0.0992] on MySQL,
  that is USD 3.60 and 3.29 per month per 1,000 QPS at 70% utilisation at the
  Fargate ARM64 list price.
- **Two tasks of 0.5 vCPU** (PostgreSQL W1, same host, 3 repetitions): at
  5,429/s (90% of S), where one task saturates (4,732/s achieved), two tasks add
  0.124 ms at p50 and 2.524 ms at p99; they sustain 9,049/s (150%) and saturate at
  10,859/s (180%).
- The generator validation passed in both of its cells. 8 repetitions were
  invalid under the pre-registered rules and 19 cells were aborted by a traffic
  cap; both are listed in the report and kept in the raw data. Every rate, the
  between-days comparison, saturation curves and charts are in the full report.

## What is measured

| Question | How |
| --- | --- |
| Added latency at a given load | **Open loop at constant rate**: request *i* is due at `start + i/rate`; latency is completion minus the **intended** send time, so a stall shows in every request due during it (no coordinated omission). HdrHistogram p50 / p90 / p99 / p99.9 / max, per 10-s interval. Paired against the direct path at the same rate in the same repetition |
| Where the cost comes from | Same rate, six targets: `direct`, `haproxy-tcp` (the hop), `pgbouncer-session` / `proxysql` (protocol awareness), `vericto-offline` (rule evaluation, no control plane), `vericto-enforce` (plus telemetry, **the headline target**, how customers run it), `vericto-observe` (monitor mode) |
| Saturation throughput | Closed loop, concurrency 1 to 128, until throughput grows less than 3% per doubling. Latency at that point is labelled "at saturation" and never quoted as latency |
| CPU cost | The proxy container's cgroup `usage_usec` every second; linear fit of vCPU against achieved QPS below 80% of saturation, at 0.5 vCPU (CFS quota, as Fargate) and 1 vCPU, and with two tasks of 0.5 |
| Statement size | Multi-row INSERT of 1 to 2,000 rows (0.07 to 45 KB on PostgreSQL) and `IN` lists of 10 to 10,000 ids at 10 statements/s: the ms/KB slope and where added p50 passes 1 ms |
| Blocked statements | A block against the same statement forwarded, end to end, in the proxy (the stub's per-event latency) and in the engine alone |
| Large results | 10 KB, 100 KB and 1 MB results, plain and with a masked column, at reduced rates: CPU-seconds and added latency per MB |

**Headline workloads**: **pgbench select-only, extended protocol**
for PostgreSQL (W1; the unnamed statement is re-parsed and evaluated on every
execution, the conservative case for an ORM) and **sysbench oltp_read_only** for
MySQL (W3; replayed open loop by vbench over the text protocol, because
sysbench's own `--rate` latency excludes queue time). Both are the standard,
comparable workloads; both at **0.5 vCPU, TLS on both legs**, curves from 10% to
100% of the proxy's saturation rate. Everything else (TPC-B in three protocol
modes, the ORM mix, 1 vCPU, two tasks, TLS off, sizes, large results) is
published alongside, not instead.

**Publication scope**: headline figures come **only from the EC2
campaign (Tier P)**. Vericto's measurements in its own AWS environment (Fargate
and Aurora inside one VPC) are context with that label, and telemetry-ingest
results are not published from this repository. Every figure
is published with its conditions (proxy and engine version, 42 built-in rules,
default policy, statement shape and size, rate, protocol mode, instance type,
vCPU budget, TLS, the direct baseline next to it, and the traffic of its cell).

## Topology: two hosts

The published numbers come from **two instances in one cluster placement group**:

| Host | Type | Runs |
| --- | --- | --- |
| System under test (SUT) | c7g.2xlarge (8 Graviton3 cores, no SMT) | the proxy (its own core), the baseline intermediary (another core), PostgreSQL 17.6 and MySQL 8.4 (three cores), cpstub |
| Load generator | c7g.xlarge (4 cores) | vbench, pgbench, sysbench, the runner, the traffic-cap guard |

Why two hosts rather than one host over loopback, for a benchmark that will be
read critically:

- **The generator does not share the SUT's memory bandwidth, L3 cache or
  interrupt load.** On one host the generator's cost lands on the same chip as the
  proxy, and that is the first objection a reader raises against loopback
  numbers. The usual limitation of a single-host benchmark ("co-location")
  disappears instead of being quantified.
- **The comparison stays fair.** The client reaches the direct database and every
  intermediary over the same network hop; each intermediary reaches the database
  over loopback on the SUT. The paired delta is therefore the intermediary's own
  cost plus one loopback hop, as on one host, while the absolute latencies include
  a real in-AZ network round trip, as an application sees.
- **The traffic caps leave room.** With the second host every byte is counted at
  two more interfaces, and the heaviest planned open-loop cells still fit: the
  1-MB results at 10/s come to about 440 Mbps in aggregate, the ORM mix at 70% of
  saturation to about 470 Mbps, under the 600-Mbps design target; the guard
  enforces 400 per component and 800 in total (below), far from the ~1 Gbps at
  which AWS may throttle. Closed-loop steps that would pass a cap are aborted and
  end their curve.
- **It costs little more**: the load generator is about USD 0.145 per hour, about
  USD 15 over the campaign.

`-var topology=single` (one c7g.2xlarge over loopback) remains available for a
cheaper reproduction; its manifest says so and it is not the published topology.
The laptop smoke (below) is a third, unpublishable topology.

## Network traffic caps (a project rule)

The benchmark measures the proxy, never the network. Total traffic of the whole
benchmark must never reach 1 Gbps:

| Scope | Hard cap (abort) | Design target (warning; pre-flight refuses plans above it) |
| --- | --- | --- |
| Each component (a host's interface, an intermediary's both hops plus telemetry, the database's port) | 400 Mbps | 300 Mbps |
| **Aggregate of every component running at the same time** | **800 Mbps** | 600 Mbps |

The same bytes are counted at every interface they cross: a byte relayed by the
proxy counts at the load generator's NIC, at the SUT's NIC, twice at the proxy
(in and out) and at the database. `hostmon sample` reads interface counters,
nftables counters per port and direction, and cgroup CPU once a second on every
host; `hostmon guard` aborts the cell (vbench exits 9; pgbench and sysbench are
stopped) after three consecutive one-second samples above a hard cap, records
`aborted: network cap`, and the runner runs no higher rate of that curve. Before
every open-loop curve, a 10-s probe measures bytes per request at each component
and `hostmon preflight` refuses the curve if any planned rate would pass a design
target, printing the highest rate that fits: rates are reduced, never the margin.
No iperf or bandwidth test of any kind is part of the harness. Why the caps
exist and what is reported instead of high traffic: [METHODOLOGY.md, section 9](METHODOLOGY.md#9-network-traffic-caps).

## Quick start: laptop smoke (NOT FOR PUBLISHED NUMBERS)

Needs Docker (with Compose) and about 4 GB of memory for Docker.

```bash
compose/smoke.sh        # builds the images, runs suites/smoke.toml, writes results/<run_id>/report/
```

Every service of the published topology runs once, in seconds-long cells, on one
Docker host without CPU isolation. The report, every chart and every CSV carry
**"SMOKE RUN: NOT FOR PUBLISHED NUMBERS"**, and `analysis/report.py --publishable`
refuses smoke runs. If Docker Hub rate-limits you, use the same digests from a
mirror: `LIBRARY_MIRROR=public.ecr.aws/docker/library PROXY_FROM_MIRROR=1 compose/smoke.sh`.

## Reproduce on AWS (Tier P)

```bash
make images                                     # optional locally; the instances build them too
cd terraform/aws && terraform init
terraform apply -var run_id=my-run-1 -var expires_on=2026-12-01 -var suite=quick   # about 1 h, about USD 1
./teardown.sh -var run_id=my-run-1 -var expires_on=2026-12-01                      # sync results, verify, destroy
```

Everything is created in its own VPC in your account (private subnet, NAT for
image pulls, no inbound rule from outside, SSM only, `ExpiresOn` tag, a runtime
guard that shuts the hosts down). The suite runs unattended from user-data; the
results (raw data, report, manifest with every digest) land in an S3 bucket of
the same stack. Details and per-hour prices: [terraform/aws/README.md](terraform/aws/README.md).

The campaign ([METHODOLOGY.md, section 11](METHODOLOGY.md#11-bench-2026-11-the-campaign-matrix-and-what-was-run)):
`suite=published` (day 1; the full matrix is 1,455 cells and at most 118
machine-hours by the planner; BENCH-2026-11's day 1 ran it trimmed to the budget
for this campaign, about USD 45: the c7i cross-check is not run and every
non-headline open-loop curve has 2 repetitions instead of 3, the headline curves
keep 3, which gives 1,116 cells and at most 89.8 planner hours, about 70 in
practice because closed-loop step-ups stop at the knee and the network
pre-flight drops rates above the traffic targets; see `suites/generate.py`),
`suite=core-h2` (the PostgreSQL two-task curve on its own stack), `suite=day2`
(headline curves on a fresh SUT at day 1's rates), `suite=c7i` with `-var sut_instance_type=c7i.2xlarge`.
At list prices about USD 0.48 per hour for the two hosts and the NAT gateway:
about USD 55 to 65 for the whole Tier P campaign.
`python3 runner/run.py --suite suites/published.toml --plan` prints the cells and
hours of any suite without running it.

## Layout

```
cmd/vbench, internal/openloop   load generator (Go): open loop from intended send time, closed loop, HdrHistogram
internal/workload, internal/db  W1-W8 statement classes with declared verdicts, seeds, PostgreSQL/MySQL sessions
cmd/cpstub, internal/cpstub     control-plane stand-in: /api/v1/sync/rules (engine's 42 rules), /api/v1/ingest/events
cmd/hostmon, internal/netcap    counters, traffic-cap guard (400/800 Mbps), pre-flight
engine-eval/                    Rust, vericto-engine v4.3.0: rules export, verdict pre-flight, evaluation-only timing
runner/                         Python 3.11+: runs a suite on two-host / single / compose topologies
suites/                         pre-registered suites (TOML; generate.py writes the campaign ones)
analysis/report.py              tables, charts, deltas with intervals, CPU fit, traffic; refuses smoke for publication
docker/                         images: tools, PgBouncer (from tarball), ProxySQL (from release .deb), sysbench, analysis
terraform/aws/, host/           EC2 provisioning (written, applied only by whoever runs a campaign), host setup
compose/                        laptop smoke
versions.lock                   every component pinned by digest or checksum
```

## Design choices and changes, and why

- **Two hosts** instead of one (reasons above).
- **Private subnet with a NAT gateway** instead of a public subnet with egress
  only (we chose to give no instance a public IP); access is SSM only in both.
- **HAProxy is a pure TCP hop in TLS cells**: a TCP proxy cannot terminate
  PostgreSQL's in-protocol TLS negotiation or MySQL's mid-handshake upgrade
  without changing the client, so it relays the end-to-end TLS session and pays
  no cryptography there. The TLS-off cells give its clean hop cost; the report
  labels it. PgBouncer, ProxySQL and the proxy pay both TLS legs.
- **The campaign measures vericto-proxy 4.14.2** (we chose it on 2026-10-19 as
  the latest release, instead of waiting for a 4.14.3 with the log-level and
  size-comment fixes). 4.14.2 is documentation-only over
  4.14.1: same code, engine v4.3.0, 42 built-in rules. Its code default log
  filter is still `info,vericto_proxy=debug`, so the harness sets
  `RUST_LOG=info` explicitly. `versions.lock` pins it by digest, and the runner
  refuses `profile=published` for any other tag.
- **Poisson noise in the steady-state rule**: pgbench `-R` draws Poisson
  arrivals, so a 1% bound on the per-part rate is replaced by three standard
  deviations of a Poisson count when that is larger (it never is at the
  published cell sizes); constant-rate vbench cells keep the 1% rule.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
