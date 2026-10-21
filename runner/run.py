#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
"""vericto-bench runner.

    python3 runner/run.py --suite suites/smoke.toml --topology compose --out /data/<run_id>
    python3 runner/run.py --suite suites/published.toml --topology two-host --sut-ssh bench@10.81.1.20 --out DIR

Exit codes: 0 the suite ran (invalid cells are recorded, not fatal), 2 usage
or suite error, 3 setup failure (nothing measured after it).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vbr import suite as S  # noqa: E402
from vbr import topo as T  # noqa: E402
from vbr.runner import Runner  # noqa: E402


def main() -> int:
    if sys.version_info < (3, 11):
        print("runner: Python 3.11 or later is required (tomllib)", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--topology", default="single", choices=["two-host", "single", "compose"])
    ap.add_argument("--sut-ssh", default="", help="bench@<SUT private IP> (two-host)")
    ap.add_argument("--out", default="results/plan", help="run directory (created)")
    ap.add_argument("--day", type=int, default=1, help="campaign day (1, or 2 for the fresh-instance repeat)")
    ap.add_argument("--image-tag", default="local", help="tag of the vericto-bench/* images built by `make images`")
    ap.add_argument("--report", action="store_true", help="run the report generator (vericto-bench/analysis image) at the end")
    ap.add_argument("--caps", default="", help="JSON caps file (default: the project's 400/300 and 800/600 Mbps)")
    ap.add_argument("--plan", action="store_true", help="print the cells and machine hours of the suite and exit")
    a = ap.parse_args()
    if a.plan:
        import json
        p = S.plan(S.load(a.suite))
        print(json.dumps(p, indent=2))
        return 0
    try:
        r = Runner(a)
    except (S.SuiteError, T.SetupError, KeyError) as e:
        print(f"runner: {e}", file=sys.stderr)
        return 2
    code = r.run()
    if a.report:
        code = max(code, r.report())
    return code


if __name__ == "__main__":
    sys.exit(main())
