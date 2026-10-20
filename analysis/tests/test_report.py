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

    def test_timestamps_with_nanoseconds_keep_their_timezone(self):
        self.assertEqual(R._ts("2026-10-20T04:12:19.000083529Z"), R._ts("2026-10-20T04:12:19.000083+00:00"))
        self.assertAlmostEqual(R._ts("2026-10-20T04:12:19.5Z") - R._ts("2026-10-20T04:12:19+00:00"), 0.5)

    def test_size_curve_slope_and_1ms_crossing(self):
        drows = []
        for n, kb, d in ((1, 0.1, 0.12), (100, 2.0, 0.6), (1000, 20.0, 5.1)):
            drows.append({"curve": f"size-pg-batch{n}-1", "target": "vericto-enforce", "n": 3, "added_p50_ms": d,
                          "added_p50_lo": d - 0.01, "added_p50_hi": d + 0.01, "added_p99_ms": d * 2,
                          "added_p99_lo": None, "added_p99_hi": None, "added_p999_ms": d * 3})
        sizes = {("pg", "batch1"): 102, ("pg", "batch100"): 2048, ("pg", "batch1000"): 20480}
        pts, fits = R.size_rows(drows, sizes)
        self.assertEqual(len(pts), 3)
        f = fits[0]
        self.assertAlmostEqual(f["p50_ms_per_kb"], 0.25, delta=0.01)
        self.assertGreater(f["p50_kb_at_1ms"], 2.0)
        self.assertLess(f["p50_kb_at_1ms"], 20.0)
        self.assertEqual(f["first_measured_kb_with_added_p50_over_1ms"], 20.0)

    def test_directions_from_window_samples(self):
        d = tempfile.mkdtemp()
        cdir = os.path.join(d, "cells", "x.vericto-enforce.r10.rep1")
        os.makedirs(cdir)
        json.dump({"intermediary": ["sut:nft:p6432_in", "sut:nft:p6432_out"]}, open(os.path.join(cdir, "components.json"), "w"))
        with open(os.path.join(cdir, "samples.jsonl"), "w") as f:
            for i, t in enumerate(("2026-10-20T04:00:00Z", "2026-10-20T04:00:10Z", "2026-10-20T04:00:20Z")):
                f.write(json.dumps({"t": t, "host": "sut", "c": {"sut:nft:p6432_in": 1000 * i, "sut:nft:p6432_out": 125000 * i,
                                                                "sut:nft:db5432_lo_in": 1000 * i, "sut:nft:db5432_lo_out": 125000 * i,
                                                                "sut:nft:cp9090_in": 0}}) + "\n")
        c = {"_run": d, "cell": "x.vericto-enforce.r10.rep1", "engine": "pg", "target": "vericto-enforce", "status": "ok",
             "loop": "open", "achieved_rate": 10.0, "measure_from": "2026-10-20T04:00:00Z", "end": "2026-10-20T04:00:20Z"}
        r = R.direction_rows([c])[0]
        self.assertAlmostEqual(r["target_to_client_mbps"], 0.1)  # 12,500 B/s
        self.assertAlmostEqual(r["result_bytes_per_request"], 1250.0)
        self.assertAlmostEqual(r["target_total_mbps"], 0.2016)

    def test_day2_curves_pool_with_day1_and_report_between_days(self):
        d1 = run_dir("published", [cell("direct", r, 1.0) for r in (1, 2, 3)] +
                     [cell("vericto-enforce", r, 1.3) for r in (1, 2, 3)])
        day2 = [dict(cell(t, r, p), curve="c-day2", day=2) for t, p in (("direct", 1.0), ("vericto-enforce", 1.4)) for r in (1, 2, 3)]
        d2 = run_dir("published", day2)
        self.assertEqual(R.main([d1, d2, "--publishable", "--out", os.path.join(d1, "rep")]), 0)
        s = json.load(open(os.path.join(d1, "rep", "summary.json")))
        self.assertEqual([r["n"] for r in s["deltas"]], [6])
        with open(os.path.join(d1, "rep", "between_days.csv")) as f:
            rows = [l for l in f if not l.startswith("#")]
        self.assertIn("between_day_diff_p50_ms", rows[0])
        self.assertAlmostEqual(float(rows[1].split(",")[rows[0].split(",").index("between_day_diff_p50_ms")]), 0.1, places=6)


if __name__ == "__main__":
    unittest.main()
