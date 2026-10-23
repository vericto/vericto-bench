# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ab as AB  # noqa: E402

A, B = "vericto-enforce-4143", "vericto-enforce-4150-off"


def cell(curve, target, rep, seq, p50, vcpu=0.3, rate=180.0):
    return {"cell": f"{curve}.{target}.{rate}.rep{rep}", "curve": curve, "engine": "mysql", "target": target,
            "loop": "open", "offered_rate": rate, "rate_pct": 50.0, "rep": rep, "seq": seq, "day": 1,
            "status": "ok", "invalid_reasons": [], "achieved_rate": rate,
            "latency": {"p50_ms": p50, "p99_ms": p50 * 2, "p999_ms": p50 * 3},
            "cpu": {"containers": {"target": {"vcpu": vcpu, "seconds": 60.0, "throttled_ms": 0.0}}}}


class AbTest(unittest.TestCase):
    def test_paired_diff_order_split_and_swap_block(self):
        cells = []
        seq = 0
        for rep in range(1, 5):
            order = (A, B) if rep % 2 else (B, A)
            for t in order:
                cells.append(cell("ab", t, rep, seq, 2.0 + (0.1 if t == B else 0.0) + 0.01 * rep))
                seq += 1
        for rep, order in ((1, [A, A + "-2nd", B, B + "-2nd"]), (2, [B + "-2nd", B, A + "-2nd", A])):
            for i, t in enumerate(order):
                cells.append(cell("swap", t, rep, seq, 2.0 + (0.1 if t.startswith(B) else 0.0) + (0.05 if i % 2 else 0.0)))
                seq += 1
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "manifest.json"), "w") as f:
            json.dump({"run_id": "r", "profile": "quick", "suite": "s"}, f)
        with open(os.path.join(d, "cells.jsonl"), "w") as f:
            for c in cells:
                f.write(json.dumps(c) + "\n")
        self.assertEqual(AB.main([d, "--baseline", A, "--candidate", B, "--ab-curve", "ab", "--swap-curve", "swap"]), 0)
        with open(os.path.join(d, "report", "ab.json")) as f:
            res = json.load(f)
        row = res["ab"][0]
        self.assertEqual(row["n_pairs"], 4)
        self.assertAlmostEqual(row["diff"]["p50"]["mean"], 0.1)
        self.assertEqual(row["diff_by_first"][A]["p50"]["n"], 2)
        self.assertEqual(row["diff"]["cpu_us_per_tx"]["mean"], 0.0)
        sw = res["swap"]
        self.assertAlmostEqual(sw["release_diff"]["p50"]["mean"], 0.1)
        self.assertAlmostEqual(sw["position_diff"]["p50"]["mean"], 0.05)


if __name__ == "__main__":
    unittest.main()
