# Contributing to vericto-bench

Thanks for helping make this benchmark better. Challenges to the methodology
are as welcome as code: if you think a baseline is configured unfairly, a rule
hides something or a figure is overstated, open an issue with the evidence.

vericto-bench is licensed under the [Apache License 2.0](LICENSE).
Contributions are accepted under the Vericto
[Contributor License Agreement](#contributor-license-agreement).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be
respectful, constructive, and technically precise.

## What belongs here

- **The load generator** (`cmd/vbench`, `internal/openloop`, `internal/workload`,
  `internal/db`): timing, workloads, drivers. Any change to the timing logic
  needs a unit test in `internal/openloop`.
- **The control-plane stub and the traffic caps** (`cmd/cpstub`, `cmd/hostmon`,
  `internal/netcap`). The caps (400/300 Mbps per component, 800/600 aggregate)
  are a project rule ([METHODOLOGY.md, section 9](METHODOLOGY.md#9-network-traffic-caps)):
  a change that loosens them will not be merged.
- **Baselines and targets** (`runner/vbr/targets.py`), **suites** (`suites/`),
  **analysis** (`analysis/report.py`), **provisioning** (`terraform/aws`, `host/`).

Changes to the methodology of a campaign that has started (its suites, validity
rules or analysis) are not merged until that campaign's report is out: the plan
is pre-registered.

## Getting started

```bash
git clone https://github.com/<you>/vericto-bench.git
cd vericto-bench
make test        # Go unit tests and the Python runner/report tests
make lint        # gofmt, go vet, bash -n, py_compile
compose/smoke.sh # the laptop smoke run (Docker): NOT FOR PUBLISHED NUMBERS
```

Requires Go 1.25+, Python 3.11+, Docker with Compose, and for `engine-eval`
Rust 1.88+ with `libclang` (or build it in its image: `make tools`).

New source files start with the two SPDX lines used everywhere in this
repository:

```
SPDX-FileCopyrightText: 2026 Vericto S.A.S.
SPDX-License-Identifier: Apache-2.0
```

Never commit results with credentials, account ids or hostnames you do not want
public. Raw data is not committed: a campaign commits only its manifests, cell
results, reports and archive checksums, after review (see `results/`).

## Contributor License Agreement

Before a pull request can be merged, every human commit author must sign the
Vericto Individual Contributor License Agreement, version 1.1
([CLA index](CLA.md), permanent text [legal/cla/1.1.md](legal/cla/1.1.md)). The
agreement lets Vericto distribute accepted contributions under the project's
public license and under separate commercial licenses while the contributor
keeps copyright.

Read the agreement and post this exact pull-request comment:

```
I have read the CLA Document and I hereby sign the CLA
```

The CLA workflow records your GitHub username and numeric account ID,
repository ID, pull-request number, comment ID, comment timestamp, CLA version
and SHA-256 document hash in `signatures/v1.1/cla.json` on the
`cla-signatures` branch. The data and retention are described in
[CLA_PRIVACY_NOTICE.md](CLA_PRIVACY_NOTICE.md). If the check does not rerun,
comment `recheck`. A commit whose email is not linked to a GitHub account
cannot be matched to a signer. Closed pull requests are locked to preserve the
signature comment.

If an employer, client or other person may own rights in your contribution,
obtain written authorization and send it to
[legal@vericto.com](mailto:legal@vericto.com) before submitting.
