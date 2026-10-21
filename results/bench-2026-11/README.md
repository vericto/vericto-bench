# BENCH-2026-11: results (EC2, Tier P, vericto-proxy 4.14.2)

**Internal until the owner's review. No figure here is published.** Status: day 1 + day 2 complete (2026-10-21); every run stack destroyed; only the archive bucket remains. Results page:
[Proxy benchmark BENCH-2026-11: day 1 results (EC2, proxy 4.14.2)](<internal-report>)
(Confluence, VTO). Design: [BENCH-2026-11](<internal-report>).

System under test: vericto-proxy 4.14.2
(`docker.io/vericto/vericto-proxy@sha256:0446e4357183cf676461c2eac42377d0e331ad19d044d12cde1045608785eb6b`,
same digest on GHCR; engine v4.3.0, 42 built-in rules, default policy), `RUST_LOG=info`,
enforce mode with telemetry to the local control-plane stand-in, TLS on both legs,
0.5 vCPU (one Graviton3 core, 50% CFS quota) and 2 x 0.5 vCPU. SUT c7g.2xlarge and load
generator c7g.xlarge in one cluster placement group, us-east-1a, account <aws-account-id>.

## Runs

| Directory | Run | Suite | What | Harness commit |
| --- | --- | --- | --- | --- |
| `p1-quick-2/` | bench-2026-11-p1-quick-2, 2026-10-20 | `quick` | P1 dry run, 39 cells: passed | c69f689 |
| `p2-day1/` | bench-2026-11-p2-day1, 2026-10-20/21 | `published` (cut) | Saturation (all 9 closed-loop curves), generator validation, the two headline curves (3 reps). Stopped by stopping the instances after head-my-w3-05 (owner's core cut); 2 cells of decomp-pg-w1 kept as extra data | 40d69b8 |
| `p2-core-h2-2/` | bench-2026-11-p2-core-h2-2, 2026-10-21 | `core-h2` | PG 2 x 0.5 vs direct at 30 to 220% of day 1's S_0.5, and 1 x 0.5 at 30/90/120%, 3 reps, 60 cells | a7acf9d |
| `p2-day2/` | bench-2026-11-p2-day2, 2026-10-21 | `day2` | The two headline curves at day 1's absolute rates on a fresh stack, 1 rep, 42 cells (+2 reruns at the knee) | 1adaff4 |
| `report/` | day 1 + day 2 combined | | `analysis/report.py --publishable --label "day 1 + day 2"` over the three published runs | |

Each run directory holds `manifest.json` (digests, hosts' provenance, suite, order seed),
`cells.jsonl`, `statements.jsonl` and `verdicts.jsonl` where the run has them, the runner
log, the run's own report, and `SHA256SUMS` of the raw archive.

## Raw data

Too big for git (pgbench per-transaction logs, HdrHistogram interval logs, 1-s counter
samples, proxy and database logs): kept in S3 in the archive bucket
`<private-archive-bucket>` (private, versioned, SSE, TLS only,
not force-destroyed, `ExpiresOn` 2027-01-31 as a review date; `terraform/archive`), one
prefix per run id with the tarballs and their `SHA256SUMS`:

| Prefix | Archive | Bytes |
| --- | --- | --- |
| `bench-2026-11-p1-quick-2/` | results + logs tarballs | 70,237,160 + 22,301 |
| `bench-2026-11-p2-day1/` | `results-bench-2026-11-p2-day1.tar.gz` (from the run's progress prefix; the run never reached finish.sh) | 2,308,336,654 |
| `bench-2026-11-p2-core-h2-2/` | results + logs tarballs | 1,581,960,714 + 23,044 |
| `bench-2026-11-p2-day2/` | results + logs tarballs | 303,522,960 + 22,721 |

    aws s3 cp s3://<private-archive-bucket>/<prefix>/ . --recursive
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
