# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tail as TA  # noqa: E402

T0 = 1_800_000_000.0


def cell(target, rep, p99, rate=1000.0, tool="pgbench"):
    return {"cell": f"k.{target}.r{rate}.rep{rep}", "curve": "k", "engine": "pg", "tool": tool, "target": target,
            "loop": "open", "offered_rate": rate, "rate_pct": 80.0, "rep": rep, "seq": rep, "status": "ok",
            "achieved_rate": rate, "measure_from": "2027-01-15T08:00:00+00:00", "end": "2027-01-15T08:00:10+00:00",
            "latency": {"p50_ms": 0.2, "p99_ms": p99, "p999_ms": p99 * 2},
            "cpu": {"containers": {"target": {"vcpu": 0.4, "seconds": 10.0, "nr_throttled": 20, "throttled_ms": 300.0}}}}


class TailTest(unittest.TestCase):
    def test_added_latency_is_paired_per_repetition(self):
        cells = [cell("direct", r, 0.5) for r in (1, 2, 3)] + [cell("vericto-x", r, 0.5 + r) for r in (1, 2, 3)]
        rows = {r["target"]: r for r in TA.rows(cells, None, "")}
        self.assertAlmostEqual(rows["vericto-x"]["added_p99"]["mean"], 2.0)
        self.assertAlmostEqual(rows["vericto-x"]["cpu_us_per_tx"]["mean"], 400.0)
        self.assertAlmostEqual(rows["vericto-x"]["nr_throttled_per_s"]["mean"], 2.0)
        self.assertNotIn("added_p99", rows["direct"])

    def test_schedmon_throttle_overlap(self):
        start = TA.R._ts("2027-01-15T08:00:00+00:00")
        with tempfile.TemporaryDirectory() as d:
            c = cell("vericto-x", 1, 5.0)
            # 100-ms samples over 10 s; the period ending at +5.0 s is throttled
            path = os.path.join(d, "schedmon.jsonl")
            with open(path, "w") as f:
                for i in range(101):
                    t = start + i * 0.1
                    n = 1 if i >= 50 else 0
                    f.write(json.dumps({"k": "cg", "t": t, "c": "vb-pg-vericto-x", "u": i * 40000, "p": i, "n": n,
                                        "tu": n * 50000}) + "\n")
                for i, t in enumerate((start + 0.5, start + 9.5)):
                    f.write(json.dumps({"k": "th", "t": t, "c": "vb-pg-vericto-x", "pid": 1,
                                        "th": [[1, "vericto-proxy", 0, 0, 0], [2, "tokio-rt-worker", i * 360, i * 9_000_000, 0]]}) + "\n")
            os.makedirs(os.path.join(d, "cells", c["cell"], "pgbench"))
            # pgbench log: client tx time_us script epoch us lag; one slow tx across the throttle, one fast elsewhere
            with gzip.open(os.path.join(d, "cells", c["cell"], "pgbench", "tx.1.gz"), "wt") as f:
                done = start + 5.02
                f.write(f"0 1 40000 0 {int(done)} {int(round((done % 1) * 1e6))} 0\n")
                done = start + 2.0
                f.write(f"0 2 300 0 {int(done)} {int(round((done % 1) * 1e6))} 0\n")
            sm = TA.load_schedmon(path)
            r = TA.schedmon_cell(c, sm, d)
        self.assertEqual(r["throttled_periods"], 1)
        self.assertEqual(r["threads"], 2)
        self.assertAlmostEqual(r["top_threads"][0]["cpu"], 0.4, places=2)
        self.assertEqual((r["tx"], r["slow_tx"]), (2, 1))
        self.assertEqual(r["slow_overlap_throttle"], 1.0)
        self.assertEqual(r["all_overlap_throttle"], 0.5)


if __name__ == "__main__":
    unittest.main()
