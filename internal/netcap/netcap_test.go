// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package netcap

import (
	"math"
	"strings"
	"testing"
	"time"
)

var t0 = time.Unix(1_700_000_000, 0)

// feed drives a guard with one sample per second where each component's single
// counter grows at the given Mbps, and returns the verdict of every tick.
func feed(t *testing.T, g *Guard, comps []string, mbps [][]float64) []Verdict {
	t.Helper()
	counters := map[string]uint64{}
	for _, c := range comps {
		counters[c] = 0
	}
	g.Observe(Sample{T: t0, Counters: copyMap(counters)})
	var out []Verdict
	for i, row := range mbps {
		for j, c := range comps {
			counters[c] += uint64(row[j] * 1e6 / 8)
		}
		at := t0.Add(time.Duration(i+1) * time.Second)
		g.Observe(Sample{T: at, Counters: copyMap(counters)})
		out = append(out, g.Evaluate(at))
	}
	return out
}

func copyMap(m map[string]uint64) map[string]uint64 {
	o := make(map[string]uint64, len(m))
	for k, v := range m {
		o[k] = v
	}
	return o
}

func oneEach(names ...string) Components {
	c := Components{}
	for _, n := range names {
		c[n] = []string{n}
	}
	return c
}

func TestDefaultCapsAreTheOwners(t *testing.T) {
	c := Default()
	if c.ComponentHard != 400 || c.ComponentTarget != 300 || c.AggregateHard != 800 || c.AggregateTarget != 600 || c.Consecutive != 3 {
		t.Fatalf("defaults %+v", c)
	}
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	c.AggregateHard = 1000
	if c.Validate() == nil {
		t.Fatal("an aggregate cap at 1 Gbps must be refused")
	}
}

func TestComponentAbortsAfterThreeConsecutiveSamples(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("proxy"))
	v := feed(t, g, []string{"proxy"}, [][]float64{{450}, {450}, {100}, {450}, {450}, {450}})
	for i := 0; i < 5; i++ {
		if v[i].Abort {
			t.Fatalf("tick %d aborted early: %s", i, v[i].Reason)
		}
	}
	if !v[5].Abort || !strings.Contains(v[5].Reason, "proxy above 400 Mbps") {
		t.Fatalf("tick 5: %+v", v[5])
	}
}

func TestDesignTargetIsAWarningOnly(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("proxy"))
	v := feed(t, g, []string{"proxy"}, [][]float64{{350}, {350}, {350}, {350}})
	for _, x := range v {
		if x.Abort {
			t.Fatalf("aborted at 350 Mbps: %s", x.Reason)
		}
	}
	if len(v[0].Warnings) == 0 || !g.Warned["proxy"] {
		t.Fatal("no warning above the design target")
	}
}

// Three components each under the per-component cap can still breach the
// aggregate: 3 x 300 = 900 > 800.
func TestAggregateCapAcrossComponents(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("loadgen", "proxy", "db"))
	v := feed(t, g, []string{"loadgen", "proxy", "db"}, [][]float64{{300, 300, 300}, {300, 300, 300}, {300, 300, 300}})
	if v[0].Abort || v[1].Abort {
		t.Fatal("aborted before three samples")
	}
	if !v[2].Abort || !strings.Contains(v[2].Reason, "aggregate") {
		t.Fatalf("tick 2: %+v", v[2])
	}
	if math.Abs(v[2].Aggregate-900) > 1 {
		t.Fatalf("aggregate %.1f, want 900", v[2].Aggregate)
	}
}

func TestAggregateBetweenTargetAndCapWarns(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("a", "b", "c"))
	v := feed(t, g, []string{"a", "b", "c"}, [][]float64{{230, 230, 230}, {230, 230, 230}, {230, 230, 230}, {230, 230, 230}})
	for _, x := range v {
		if x.Abort {
			t.Fatalf("aborted at 690 Mbps aggregate: %s", x.Reason)
		}
	}
	if !g.Warned[""] {
		t.Fatal("aggregate above 600 Mbps did not warn")
	}
}

func TestAverageRuleForFargate(t *testing.T) {
	caps := Default()
	caps.Consecutive, caps.AverageSamples = 0, 5
	g, _ := NewGuard(caps, oneEach("task"))
	// A one-sample spike to 900 averages to 420 over five samples with 300 around it.
	v := feed(t, g, []string{"task"}, [][]float64{{300}, {300}, {300}, {300}, {900}})
	if !v[4].Abort {
		t.Fatalf("mean 420 > 400 must abort: %+v", v[4])
	}
	g2, _ := NewGuard(caps, oneEach("task"))
	v = feed(t, g2, []string{"task"}, [][]float64{{200}, {200}, {200}, {200}, {900}})
	if v[4].Abort {
		t.Fatalf("mean 340 must not abort: %s", v[4].Reason)
	}
}

func TestCounterResetDoesNotFakeTraffic(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("proxy"))
	g.Observe(Sample{T: t0, Counters: map[string]uint64{"proxy": 1 << 40}})
	g.Observe(Sample{T: t0.Add(time.Second), Counters: map[string]uint64{"proxy": 10}})
	v := g.Evaluate(t0.Add(time.Second))
	if v.Mbps["proxy"] != 0 || v.Abort {
		t.Fatalf("after a reset: %+v", v)
	}
}

func TestRateUsesTheRealInterval(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("proxy"))
	g.Observe(Sample{T: t0, Counters: map[string]uint64{"proxy": 0}})
	// 100 Mbit in 2 s is 50 Mbps, not 100.
	g.Observe(Sample{T: t0.Add(2 * time.Second), Counters: map[string]uint64{"proxy": 100e6 / 8}})
	if m := g.Evaluate(t0.Add(2 * time.Second)).Mbps["proxy"]; math.Abs(m-50) > 0.01 {
		t.Fatalf("%.2f Mbps, want 50", m)
	}
}

func TestLostMonitorAborts(t *testing.T) {
	g, _ := NewGuard(Default(), oneEach("proxy", "db"))
	g.Observe(Sample{T: t0, Counters: map[string]uint64{"proxy": 0, "db": 0}})
	g.Observe(Sample{T: t0.Add(time.Second), Counters: map[string]uint64{"proxy": 1, "db": 1}})
	// The db stream stops; the proxy keeps reporting.
	for i := 2; i <= 8; i++ {
		g.Observe(Sample{T: t0.Add(time.Duration(i) * time.Second), Counters: map[string]uint64{"proxy": uint64(i)}})
	}
	v := g.Evaluate(t0.Add(8 * time.Second))
	if !v.Abort || !strings.Contains(v.Reason, "monitor lost") {
		t.Fatalf("%+v", v)
	}
}

func TestSharedCounterCountsInEveryComponent(t *testing.T) {
	g, err := NewGuard(Default(), Components{"proxy": {"up"}, "db": {"up"}})
	if err != nil {
		t.Fatal(err)
	}
	v := feed(t, g, []string{"up"}, [][]float64{{250}})
	if math.Abs(v[0].Aggregate-500) > 1 {
		t.Fatalf("aggregate %.1f, want 500 (250 at the proxy and 250 at the database)", v[0].Aggregate)
	}
	if _, err := NewGuard(Default(), Components{"a": {}}); err == nil {
		t.Fatal("an empty component must be refused")
	}
}

// The design's Tier S example: 2 proxy tasks x 3,500 QPS of the ORM mix at
// ~4 KB per crossing exceeds the 600-Mbps aggregate target, and the pre-flight
// gives the reduced rate instead.
func TestPreflightReducesRatesNotTheMargin(t *testing.T) {
	c := Default()
	per := 4096.0 // bytes per request per crossing
	cell := PlannedCell{ID: "tier-s-2tasks", Rate: 7000, BytesPerRequest: map[string]float64{
		"client": per, "proxy-1": per, "proxy-2": per, "aurora": per,
	}}
	// Each proxy task carries half the requests but two crossings: same bytes per
	// request of the total as one crossing.
	v := Preflight(c, []PlannedCell{cell})
	if len(v) == 0 {
		t.Fatal("7,000 QPS at 16 KB per request across the path must not pass")
	}
	var agg *Violation
	for i := range v {
		if v[i].What == "aggregate" {
			agg = &v[i]
		}
	}
	if agg == nil {
		t.Fatalf("no aggregate violation in %+v", v)
	}
	cell.Rate = agg.MaxRate
	if v := Preflight(c, []PlannedCell{cell}); len(v) != 0 {
		t.Fatalf("at the suggested max rate %.0f: %+v", agg.MaxRate, v)
	}
	if agg.MaxRate < 4000 || agg.MaxRate > 5000 {
		t.Fatalf("max rate %.0f, want about 4,360", agg.MaxRate)
	}
}

func TestPreflightPassesTheDesignW8Cells(t *testing.T) {
	c := Default()
	// 1 MB result at 10/s, two hosts: loadgen NIC 1 crossing, SUT NIC 1, proxy
	// ports 2 (client side and database side), database port 1.
	mb := 1.05e6
	cell := PlannedCell{ID: "w8-1mb-10", Rate: 10, BytesPerRequest: map[string]float64{
		"loadgen": mb, "sut-eni": mb, "proxy": 2 * mb, "db": mb,
	}}
	if v := Preflight(c, []PlannedCell{cell}); len(v) != 0 {
		t.Fatalf("%+v", v)
	}
	if _, agg := cell.Expected(); agg < 400 || agg > 500 {
		t.Fatalf("aggregate %.0f Mbps, want about 440", agg)
	}
}

func TestProbeComputesBytesPerRequest(t *testing.T) {
	comps := Components{"proxy": {"p_in", "p_out"}, "db": {"d"}}
	got, err := Probe(comps, map[string]uint64{"p_in": 1000, "p_out": 9000, "d": 5000}, 10)
	if err != nil || got["proxy"] != 1000 || got["db"] != 500 {
		t.Fatalf("%v %v", got, err)
	}
	if _, err := Probe(comps, map[string]uint64{"p_in": 1}, 10); err == nil {
		t.Fatal("missing counters must be an error")
	}
}
