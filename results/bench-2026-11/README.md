# BENCH-2026-11: results (EC2, Tier P, vericto-proxy 4.14.2)

Status: day 1 + day 2 complete (2026-10-21); every run stack destroyed. The public write-up is
[vericto.com/benchmarks/proxy-latency](https://vericto.com/benchmarks/proxy-latency); this directory
holds the per-run manifests, cell results and reports it is built from. What the campaign ran of the
full matrix, and why, is in [METHODOLOGY.md, section 11](../../METHODOLOGY.md#11-bench-2026-11-the-campaign-matrix-and-what-was-run).
Run ids: `p1` is the dry run, `p2` the published campaign.

System under test: vericto-proxy 4.14.2
(`docker.io/vericto/vericto-proxy@sha256:0446e4357183cf676461c2eac42377d0e331ad19d044d12cde1045608785eb6b`,
same digest on GHCR; engine v4.3.0, 42 built-in rules, default policy), `RUST_LOG=info`,
enforce mode with telemetry to the local control-plane stand-in, TLS on both legs,
0.5 vCPU (one Graviton3 core, 50% CFS quota) and 2 x 0.5 vCPU. SUT c7g.2xlarge and load
generator c7g.xlarge in one cluster placement group, us-east-1a.

## Runs

| Directory | Run | Suite | What | Harness commit (see below) |
| --- | --- | --- | --- | --- |
| `p1-quick-2/` | bench-2026-11-p1-quick-2, 2026-10-20 | `quick` | P1 dry run, 39 cells: passed | d24f0ae |
| `p2-day1/` | bench-2026-11-p2-day1, 2026-10-20/21 | `published` (cut) | Saturation (all 9 closed-loop curves), generator validation, the two headline curves (3 reps). Stopped by stopping the instances after head-my-w3-05 (the day-1 core cut); 2 cells of decomp-pg-w1 kept as extra data | c256dc3 |
| `p2-core-h2-2/` | bench-2026-11-p2-core-h2-2, 2026-10-21 | `core-h2` | PG 2 x 0.5 vs direct at 30 to 220% of day 1's S_0.5, and 1 x 0.5 at 30/90/120%, 3 reps, 60 cells | 38f0fb8 |
| `p2-day2/` | bench-2026-11-p2-day2, 2026-10-21 | `day2` | The two headline curves at day 1's absolute rates on a fresh stack, 1 rep, 42 cells (+2 reruns at the knee) | 36a8980 |
| `report/` | day 1 + day 2 combined | | `analysis/report.py --publishable --label "day 1 + day 2"` over the three published runs | |

### Harness commits

The repository's history was rewritten before it went public, which changed the id of every
commit from `91ccdb4` on. The table above gives the commits in the published history; each run's
`manifest.json` (`harness_commit`) and report keep the id recorded at run time. The commits were
matched by message and date in the rewritten history (each predates its run's start):

| Run | Recorded at run time | Published history | Commit |
| --- | --- | --- | --- |
| bench-2026-11-p1-quick-2 | `c69f68950b760171d19d477a9ce126b372806d4b` | `d24f0ae1da1b44096677971fd95f2ec9d6fd792f` | fix(runner): the certs container runs as the runner's user |
| bench-2026-11-p2-day1 | `40d69b8bbb013d038b6d3965d3788210393de5f5` | `c256dc358f9834e9f018f4a0f3919688e65f9ff7` | feat: day-1 budget trim, no rerun of saturated cells, ... |
| bench-2026-11-p2-core-h2-2 | `a7acf9df46235e9fd124687229317ccdb3794e74` | `38f0fb818198b8b6f76c3e09a9baa35f5a95465f` | fix: same-digest fallback when an image mirror fails |
| bench-2026-11-p2-day2 | `1adaff4be7f4f5702adc1f27fb7f9843437b230d` | `36a89802ad769ade57e1f8c7baf9ae211a1ef9e1` | report: the bytes-per-direction table is at the highest offered rate |

To reproduce a run with the same harness, check out the commit in the "Published history" column.

Each run directory holds `manifest.json` (digests, hosts' provenance, suite, order seed),
`cells.jsonl`, `statements.jsonl` and `verdicts.jsonl` where the run has them, the runner
log, the run's own report, and `SHA256SUMS` of the raw archive.

## Raw data

Too big for git (pgbench per-transaction logs, HdrHistogram interval logs, 1-s counter
samples, proxy and database logs): kept by Vericto in a private, versioned S3 archive
(`terraform/archive` creates one like it), one prefix per run id with the tarballs and
their `SHA256SUMS`. Available on request:

| Prefix | Archive | Bytes |
| --- | --- | --- |
| `bench-2026-11-p1-quick-2/` | results + logs tarballs | 70,237,160 + 22,301 |
| `bench-2026-11-p2-day1/` | `results-bench-2026-11-p2-day1.tar.gz` (from the run's progress prefix; the run never reached finish.sh) | 2,308,336,654 |
| `bench-2026-11-p2-core-h2-2/` | results + logs tarballs | 1,581,960,714 + 23,044 |
| `bench-2026-11-p2-day2/` | results + logs tarballs | 303,522,960 + 22,721 |

    # after receiving a prefix's files:
    shasum -a 256 -c SHA256SUMS

## Re-create a run

    cd terraform/aws
    terraform workspace new <name>
    terraform apply -var run_id=<id> -var expires_on=<YYYY-MM-DD> -var suite=<quick|published|core-h2|day2> \
      -var harness_commit=$(git rev-parse HEAD)
    ./teardown.sh -var run_id=<id> -var expires_on=<YYYY-MM-DD> -var suite=<suite> -var harness_commit=<same>

Day 2 records `day = 2` automatically (`-var suite=day2`). The follow-up batch (size sweep,
large results and masking, decomposition, 1 vCPU, PgBouncer / ProxySQL, TLS off, modes,
ORM, blocked, connection setup, c7i) is `suites/published.toml` minus what ran here.
