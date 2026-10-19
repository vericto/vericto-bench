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

> **Status (2026-10-19): harness built and tested (phase P0). No campaign has run
> yet, so this repository contains no published figure.** The design is
> BENCH-2026-11; the methodology is in [METHODOLOGY.md](METHODOLOGY.md).

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

**Headline workloads** (decision 6): **pgbench select-only, extended protocol**
for PostgreSQL (W1; the unnamed statement is re-parsed and evaluated on every
execution, the conservative case for an ORM) and **sysbench oltp_read_only** for
MySQL (W3; replayed open loop by vbench over the text protocol, because
sysbench's own `--rate` latency excludes queue time). Both are the standard,
comparable workloads; both at **0.5 vCPU, TLS on both legs**, curves from 10% to
100% of the proxy's saturation rate. Everything else (TPC-B in three protocol
modes, the ORM mix, 1 vCPU, two tasks, TLS off, sizes, large results) is
published alongside, not instead.

**Publication scope** (decision 7): headline figures come **only from the EC2
campaign (Tier P)**. Staging measurements (Fargate and Aurora inside one VPC) are
context with that label, and telemetry-ingest results are internal (the staging
sessions use this repository's vbench through Vericto's internal scripts). Every figure
is published with its conditions (proxy and engine version, 42 built-in rules,
default policy, statement shape and size, rate, protocol mode, instance type,
vCPU budget, TLS, the direct baseline next to it, and the traffic of its cell).

## Topology: two hosts (decision 3)

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
  numbers. The design's own limitation ("co-location") disappears instead of
  being quantified.
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

## Network traffic caps (owner rule, design section 8a)

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
No iperf or bandwidth test of any kind is part of the harness.

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

The campaign (design section 10): `suite=published` (day 1, the full matrix:
1,455 cells, at most 118 machine-hours by the planner, less in practice because
closed-loop step-ups stop at the knee), `suite=day2` (headline curves on a fresh
SUT at day 1's rates), `suite=c7i` with `-var sut_instance_type=c7i.2xlarge`.
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

## Deviations from the design, and why

- **Two hosts** instead of one (decision 3; reasons above).
- **Private subnet with a NAT gateway** instead of a public subnet with egress
  only (owner instruction); access is SSM only in both.
- **HAProxy is a pure TCP hop in TLS cells**: a TCP proxy cannot terminate
  PostgreSQL's in-protocol TLS negotiation or MySQL's mid-handshake upgrade
  without changing the client, so it relays the end-to-end TLS session and pays
  no cryptography there. The TLS-off cells give its clean hop cost; the report
  labels it. PgBouncer, ProxySQL and the proxy pay both TLS legs.
- **The campaign measures vericto-proxy 4.14.3** (decision 8: the log-level and
  size-comment fixes ship before the run). `versions.lock` pins 4.14.1 until
  4.14.3 is published, and the runner refuses `profile=published` until the
  pinned tag is 4.14.3.
- **Poisson noise in the steady-state rule**: pgbench `-R` draws Poisson
  arrivals, so a 1% bound on the per-part rate is replaced by three standard
  deviations of a Poisson count when that is larger (it never is at the
  published cell sizes); constant-rate vbench cells keep the 1% rule.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
