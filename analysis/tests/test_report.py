# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import report as R  # noqa: E402


def run_dir(profile, cells):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "manifest.json"), "w") as f:
        json.dump({"run_id": "r", "profile": profile, "suite": "s"}, f)
    with open(os.path.join(d, "cells.jsonl"), "w") as f:
        for c in cells:
            f.write(json.dumps(c) + "\n")
    return d


def cell(target, rep, p50, rate=100, status="ok", invalid=None):
    return {"cell": f"c.{target}.{rate}.{rep}", "curve": "c", "engine": "pg", "target": target, "loop": "open",
            "offered_rate": rate, "rep": rep, "day": 1, "status": status, "invalid_reasons": invalid or [],
            "latency": {"p50_ms": p50, "p99_ms": p50 * 3, "p999_ms": p50 * 5}}


class Report(unittest.TestCase):
    def test_smoke_cannot_be_publishable(self):
        d = run_dir("smoke", [cell("direct", 1, 1.0)])
        self.assertEqual(R.main([d, "--publishable"]), 2)
        self.assertEqual(R.main([d]), 0)
        with open(os.path.join(d, "report", "report.md")) as f:
            self.assertIn(R.SMOKE, f.read())
        with open(os.path.join(d, "report", "cells.csv")) as f:
            self.assertIn(R.SMOKE, f.readline())

    def test_paired_deltas_and_interval(self):
        cells = [cell("direct", r, 1.0) for r in (1, 2, 3)] + [cell("vericto-enforce", r, 1.0 + d) for r, d in ((1, 0.30), (2, 0.32), (3, 0.28))]
        rows = R.deltas(R.select([dict(c, _run="x") for c in cells])[0])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertAlmostEqual(r["added_p50_ms"], 0.30, places=6)
        self.assertLess(r["added_p50_lo"], 0.30)
        self.assertGreater(r["added_p50_lo"], 0)
        self.assertEqual(r["p50_note"], "")

    def test_interval_containing_zero_is_not_distinguishable(self):
        cells = [cell("direct", r, 1.0) for r in (1, 2, 3)] + [cell("haproxy-tcp", r, 1.0 + d) for r, d in ((1, 0.05), (2, -0.04), (3, 0.01))]
        r = R.deltas(R.select([dict(c, _run="x") for c in cells])[0])[0]
        self.assertEqual(r["p50_note"], "not distinguishable from the direct path")

    def test_saturated_and_invalid_cells_are_not_latency(self):
        cells = [cell("direct", 1, 1.0), cell("vericto-enforce", 1, 9.0, status="saturated"),
                 cell("direct", 2, 1.0), cell("vericto-enforce", 2, 1.2, invalid=["steal 2% on sut"])]
        used, invalid = R.select([dict(c, _run="x") for c in cells])
        self.assertEqual(len(invalid), 1)
        self.assertEqual(R.deltas(used), [])

    def test_ols(self):
        f = R.ols([1, 2, 3, 4], [0.12, 0.235, 0.35, 0.465])
        self.assertAlmostEqual(f["slope"], 0.115, places=3)


if __name__ == "__main__":
    unittest.main()
