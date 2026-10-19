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
  are an owner rule: a change that loosens them will not be merged.
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

Requires Go 1.23+, Python 3.11+, Docker with Compose, and for `engine-eval`
Rust 1.88+ with `libclang` (or build it in its image: `make tools`).

New source files start with the two SPDX lines used everywhere in this
repository:

```
SPDX-FileCopyrightText: 2026 Vericto S.A.S.
SPDX-License-Identifier: Apache-2.0
```

Never commit results with credentials, account ids or hostnames you do not want
public: results are published as release assets after review, not committed.

## Contributor License Agreement

Before your first pull request can be merged, you need to sign the Vericto
Contributor License Agreement (CLA), version 1.0, in [CLA.md](CLA.md). On your
first pull request, the `CLA` check comments with a link to the agreement and
fails until every author of a commit in the pull request has signed. To sign,
read the agreement, then post this comment on the pull request, exactly as
written:

```
I have read the CLA Document and I hereby sign the CLA
```

The check records your GitHub username and account id, the pull request, your
comment and its time on this repository's `cla-signatures` branch, and passes.
If the check does not rerun on its own, comment `recheck`.

If you contribute on behalf of an employer, write to
[legal@vericto.com](mailto:legal@vericto.com) before opening the pull request.
