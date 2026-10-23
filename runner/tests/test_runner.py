# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
import collections
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vbr import monitor as M  # noqa: E402
from vbr import suite as S  # noqa: E402
from vbr import tools as TL  # noqa: E402
from vbr.runner import fraction_above, steady_state, variant_ref  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Suites(unittest.TestCase):
    def test_every_committed_suite_loads(self):
        for f in sorted(os.listdir(os.path.join(REPO, "suites"))):
            if f == "day2.toml":
                # armed with day 1's S (suites/generate.py DAY1_S): every curve has it
                s = S.load(os.path.join(REPO, "suites", f))
                self.assertTrue(all(c.saturation_qps > 0 for c in s.curves), f)
            elif f.endswith(".toml"):
                s = S.load(os.path.join(REPO, "suites", f))
                self.assertTrue(s.curves, f)

    def test_williams_square_is_balanced(self):
        for n in range(2, 8):
            rows = S.williams(n)
            follows = collections.Counter()
            for r in rows:
                self.assertEqual(sorted(r), list(range(n)))
                for a, b in zip(r, r[1:]):
                    follows[(a, b)] += 1
            # every ordered pair follows equally often
            self.assertEqual(len(set(follows.values())), 1, n)
            self.assertEqual(len(follows), n * (n - 1))

    def test_rates_same_for_every_target_and_saturating_last(self):
        s = S.load(os.path.join(REPO, "suites", "smoke.toml"))
        c = S.Curve(id="x", engine="pg", tool="vbench", workload="orm", mode="extended", tls=True, size="0.5",
                    targets=["direct", "haproxy-tcp", "vericto-enforce"], rates_pct=[10, 50, 100, 30],
                    saturation_qps=1000)
        s.reps = 3
        cells = S.expand(s, c, {})
        by_rate = collections.defaultdict(set)
        for x in cells:
            by_rate[(x.rep, x.rate)].add(x.target)
        self.assertTrue(all(len(v) == 3 for v in by_rate.values()))
        for rep in (1, 2, 3):
            rates = [x.rate for x in cells if x.rep == rep]
            self.assertEqual(rates[-3:], [1000.0] * 3)  # the 100% rate runs last
        self.assertEqual(len({x.id for x in cells}), len(cells))

    def test_variants_resolve_to_their_base_and_are_pinned(self):
        s = S.load(os.path.join(REPO, "suites", "m2-quick.toml"))
        self.assertEqual(s.saturation_target, "vericto-enforce-4143")
        self.assertEqual(s.base("vericto-enforce-4150-off"), "vericto-enforce")
        self.assertEqual(s.base("direct"), "direct")
        self.assertEqual(s.variants["vericto-enforce-4150-off"].env, {"VERICTO_POLICY_RULES": "off"})
        with open(os.path.join(REPO, "versions.lock")) as f:
            lock = dict(l.strip().split("=", 1) for l in f if "=" in l and not l.lstrip().startswith("#"))
        for v in s.variants.values():
            self.assertRegex(lock[v.image_key], r"@sha256:[0-9a-f]{64}$")

    def test_override_variant_takes_the_runs_image(self):
        s = S.load(os.path.join(REPO, "suites", "m2-fix-ab.toml"))
        cand = s.variants["vericto-enforce-cand-off"]
        self.assertEqual(cand.image_key, S.OVERRIDE_IMAGE_KEY)
        self.assertEqual(cand.env, {"VERICTO_POLICY_RULES": "off"})
        ref = "registry.example/vericto-proxy@sha256:" + "a" * 64
        self.assertEqual(variant_ref(cand.image_key, {}, {"PROXY_IMAGE_OVERRIDE": ref}), ref)
        self.assertIsNone(variant_ref(cand.image_key, {"PROXY_IMAGE_OVERRIDE": ref}, {}))  # never from the lock
        self.assertEqual(variant_ref("VERICTO_PROXY_4_14_3_IMAGE", {"VERICTO_PROXY_4_14_3_IMAGE": ref}, {}), ref)
        self.assertIsNone(variant_ref("VERICTO_X_IMAGE", {}, {"PROXY_IMAGE_OVERRIDE": ref}))

    def test_variant_rules(self):
        for body, err in (('[variant.vericto-x]\nbase = "haproxy-tcp"\n', "base"),
                          ('[variant.other]\nbase = "vericto-enforce"\n', "name"),
                          ('[variant.vericto-x]\nbase = "vericto-enforce"\nenv = { lower = "1" }\n', "env"),
                          ('[variant.vericto-x]\nbase = "vericto-enforce"\nimage = "SOMETHING"\n', "image")):
            path = tempfile.mktemp(suffix=".toml")
            with open(path, "w") as f:
                f.write('[suite]\nname = "t"\nprofile = "quick"\norder_seed = 1\n' + body +
                        '[[curve]]\nid = "c"\nengine = "pg"\nworkload = "orm"\ntargets = ["direct"]\nrates = [10]\n')
            with self.assertRaisesRegex(S.SuiteError, err):
                S.load(path)
            os.remove(path)

    def test_listed_reversed_order_alternates_per_repetition(self):
        s = S.load(os.path.join(REPO, "suites", "m2-mysql-ab.toml"))
        sat = {"sat-my-w3-05": 360.0}
        ab = next(c for c in s.curves if c.id == "ab-my-w3-05")
        cells = S.expand(s, ab, sat)
        first = collections.Counter()
        for a, b in zip(cells[::2], cells[1::2]):
            self.assertEqual((a.rep, a.rate), (b.rep, b.rate))  # each rate: both releases next to each other
            self.assertNotEqual(a.target, b.target)
            first[(a.rate, a.target)] += 1
            self.assertEqual(a.target == "vericto-enforce-4143", a.rep % 2 == 1)
        self.assertEqual(set(first.values()), {4})  # each release first 4 times per rate
        swap = next(c for c in s.curves if c.id == "swap-my-w3-05")
        order = [c.target.removeprefix("vericto-enforce-") for c in S.expand(s, swap, sat)]
        self.assertEqual(order, ["4143", "4143-2nd", "4150-off", "4150-off-2nd",
                                 "4150-off-2nd", "4150-off", "4143-2nd", "4143"])
        self.assertTrue(all(c.profile_s == 0 for c in s.curves if c.id != "prof-my-w3-05"))

    def test_order_and_profile_rules(self):
        for body, err in (('order = "random"\n', "order"), ('profile_s = 10\nloop = "closed"\nconcurrency = [1]\n', "profile_s"),
                          ('targets = ["direct", "direct"]\n', "twice")):
            path = tempfile.mktemp(suffix=".toml")
            with open(path, "w") as f:
                t = "" if "targets" in body else 'targets = ["direct"]\n'
                f.write('[suite]\nname = "t"\nprofile = "quick"\norder_seed = 1\n[[curve]]\nid = "c"\nengine = "pg"\n'
                        'workload = "orm"\nrates = [10]\n' + t + body)
            with self.assertRaisesRegex(S.SuiteError, err):
                S.load(path)
            os.remove(path)

    def test_sysbench_open_loop_is_refused(self):
        path = tempfile.mktemp(suffix=".toml")
        with open(path, "w") as f:
            f.write('[suite]\nname="x"\nprofile="smoke"\norder_seed=1\n[[curve]]\nid="a"\nengine="mysql"\n'
                    'tool="sysbench"\nworkload="oltp_read_only"\ntargets=["direct"]\nrates=[10]\n')
        with self.assertRaises(S.SuiteError):
            S.load(path)
        os.remove(path)


class Pgbench(unittest.TestCase):
    def test_latency_is_time_plus_schedule_lag_and_window_is_by_schedule(self):
        d = tempfile.mkdtemp()
        prefix = os.path.join(d, "tx")
        t0 = 1_700_000_000
        with open(prefix + ".123", "w") as f:
            # client tx time script epoch us lag: 20 transactions due every 0.5 s
            for i in range(20):
                due = t0 + i * 0.5
                time_us, lag = 1000, (300_000 if i == 10 else 100)
                done = due + (time_us + lag) / 1e6
                f.write(f"0 {i} {time_us} 0 {int(done)} {int(round((done % 1) * 1e6))} {lag}\n")
        r, ints = TL.parse_pgbench(prefix, warmup=2, duration=6, interval=2, offered=2)
        self.assertEqual(r["completed"], 12)  # due in [2, 8)
        self.assertAlmostEqual(r["latency"]["max_ms"], 301.0, delta=0.01)
        self.assertAlmostEqual(r["service"]["max_ms"], 1.0, delta=0.01)
        self.assertEqual(len(ints), 3)
        self.assertEqual(sum(i["completed"] for i in ints), 12)

    def test_summarise_matches_nearest_rank(self):
        c = collections.Counter({1000: 98, 5000: 1, 9000: 1})
        s = TL.summarise(c)
        self.assertEqual((s["p50_ms"], s["p99_ms"], s["max_ms"]), (1.0, 5.0, 9.0))


class Steady(unittest.TestCase):
    def _write(self, rows):
        p = tempfile.mktemp()
        with open(p, "w") as f:
            for i, (n, v) in enumerate(rows):
                f.write(json.dumps({"i": i, "start": f"2026-10-19T00:{i:02d}:00+00:00",
                                    "end": f"2026-10-19T00:{i:02d}:10+00:00", "completed": n,
                                    "buckets_us": [[v, n]]}) + "\n")
        return p

    def test_constant_rate_and_drift_rules(self):
        self.assertNotIn("flag", steady_state(self._write([(1000, 900)] * 6), 100))
        self.assertIn("rate varies", steady_state(self._write([(1000, 900)] * 3 + [(900, 900)] * 3), 100)["flag"])
        self.assertIn("p50 drifts", steady_state(self._write([(1000, 900)] * 3 + [(1000, 1200)] * 3), 100)["flag"])

    def test_poisson_tolerance(self):
        rows = [(500, 900), (470, 900), (520, 900), (490, 900), (510, 900), (480, 900)]
        self.assertIn("flag", steady_state(self._write(rows), 50, poisson=False))
        self.assertNotIn("flag", steady_state(self._write(rows), 50, poisson=True))

    def test_fraction_above(self):
        p = self._write([(99, 1000), (1, 900_000)])
        self.assertAlmostEqual(fraction_above(p, 500_000), 0.01)


class Components(unittest.TestCase):
    class T:
        def __init__(self, kind):
            self.kind = kind

    def test_two_host_counts_every_interface(self):
        c = M.components(self.T("two-host"), "pg", "vericto-enforce", [6432])
        self.assertEqual(set(c), {"database", "intermediary", "loadgen-nic", "sut-nic"})
        # the upstream hop is counted at the proxy and at the database (project rule)
        self.assertIn("sut:nft:db5432_lo_in", c["intermediary"])
        self.assertIn("sut:nft:db5432_lo_in", c["database"])
        self.assertIn("sut:nft:cp9090_in", c["intermediary"])

    def test_direct_has_no_intermediary(self):
        self.assertNotIn("intermediary", M.components(self.T("two-host"), "mysql", "direct", []))


if __name__ == "__main__":
    unittest.main()
