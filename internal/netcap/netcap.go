// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package netcap enforces the benchmark's network traffic caps.
//
// The benchmark measures the proxy, never the network: total traffic must stay
// far below the ~1 Gbps at which AWS may throttle or block. The rules (a project
// rule, METHODOLOGY.md section 9):
//
//   - per component (a host, a task, or one process's ports), both directions,
//     every hop: hard cap 400 Mbps, design target 300 Mbps;
//   - aggregate over every component running at the same time (load generator,
//     proxy tasks, intermediaries, database, telemetry): hard cap 800 Mbps,
//     design target 600 Mbps. The same bytes are counted at every interface they
//     cross, so a byte relayed by the proxy counts at the client, twice at the
//     proxy and once at the database.
//
// A breach of a hard cap aborts the cell; crossing a design target is a warning.
// The pre-flight refuses a plan whose expected traffic crosses a design target,
// and says the highest rate that fits, so rates are reduced rather than the
// margin.
package netcap

import (
	"fmt"
	"math"
	"sort"
	"strings"
	"time"
)

// Caps are the limits, in Mbps (10^6 bits per second).
type Caps struct {
	ComponentHard   float64 `json:"component_hard_mbps"`
	ComponentTarget float64 `json:"component_target_mbps"`
	AggregateHard   float64 `json:"aggregate_hard_mbps"`
	AggregateTarget float64 `json:"aggregate_target_mbps"`
	// Breach rule. Consecutive > 0: abort after that many consecutive samples
	// above a hard cap (Tier P: 3 one-second samples). Otherwise Average: abort
	// when the mean of the last AverageSamples samples is above it (Fargate: 5 s).
	Consecutive    int `json:"consecutive"`
	AverageSamples int `json:"average_samples"`
	// Stale: a component whose counters have not moved forward for this long
	// cannot be watched any more, and the cell is aborted.
	Stale time.Duration `json:"stale_ns"`
}

// Default returns the project's caps with the Tier P breach rule.
func Default() Caps {
	return Caps{ComponentHard: 400, ComponentTarget: 300, AggregateHard: 800, AggregateTarget: 600,
		Consecutive: 3, Stale: 5 * time.Second}
}

// Validate refuses caps that would not protect anything.
func (c Caps) Validate() error {
	switch {
	case c.ComponentHard <= 0 || c.AggregateHard <= 0:
		return fmt.Errorf("hard caps must be positive")
	case c.ComponentTarget <= 0 || c.ComponentTarget > c.ComponentHard:
		return fmt.Errorf("component target %.0f must be in (0, %.0f]", c.ComponentTarget, c.ComponentHard)
	case c.AggregateTarget <= 0 || c.AggregateTarget > c.AggregateHard:
		return fmt.Errorf("aggregate target %.0f must be in (0, %.0f]", c.AggregateTarget, c.AggregateHard)
	case c.AggregateHard >= 1000:
		return fmt.Errorf("aggregate hard cap %.0f Mbps must stay below 1 Gbps", c.AggregateHard)
	case c.Consecutive <= 0 && c.AverageSamples <= 0:
		return fmt.Errorf("set consecutive or average_samples")
	}
	return nil
}

// Sample is one reading of cumulative byte counters, keyed by a stable name
// such as "sut:nft:6432_in" or "loadgen:iface:ens5:tx".
type Sample struct {
	T        time.Time // the sampler's clock: rates are computed on it
	Received time.Time // the guard's clock when the sample arrived (zero: T)
	Counters map[string]uint64
}

// Components maps a component name to the counter keys whose bytes it carries.
type Components map[string][]string

// Check refuses a component with no counters. A counter may belong to several
// components on purpose: the same bytes are counted at every interface they
// cross (a project rule), e.g. the proxy's upstream hop is counted at the proxy
// and at the database.
func (c Components) Check() error {
	if len(c) == 0 {
		return fmt.Errorf("no components")
	}
	for name, keys := range c {
		if len(keys) == 0 {
			return fmt.Errorf("component %s has no counters", name)
		}
	}
	return nil
}

// Verdict is the guard's evaluation at one tick.
type Verdict struct {
	T          time.Time          `json:"t"`
	Mbps       map[string]float64 `json:"mbps"`
	Aggregate  float64            `json:"aggregate_mbps"`
	Warnings   []string           `json:"warnings,omitempty"`
	Abort      bool               `json:"abort,omitempty"`
	Reason     string             `json:"reason,omitempty"`
	Incomplete bool               `json:"incomplete,omitempty"` // not every component has a rate yet
}

type rate struct {
	bps  float64
	at   time.Time // sampler clock of the last sample
	recv time.Time // guard clock of the last sample, for staleness
	last uint64
	seen bool
}

// Guard turns counter samples into rates and applies the caps.
type Guard struct {
	caps    Caps
	comps   Components
	names   []string
	rates   map[string]*rate
	history map[string][]float64 // per component, and "" for the aggregate
	started time.Time
	Totals  map[string]uint64 // bytes per counter since the first sample
	first   map[string]uint64
	Max     map[string]float64
	sum     map[string]float64
	ticks   int
	Warned  map[string]bool
}

// NewGuard returns a guard for the given components.
func NewGuard(caps Caps, comps Components) (*Guard, error) {
	if err := caps.Validate(); err != nil {
		return nil, err
	}
	if err := comps.Check(); err != nil {
		return nil, err
	}
	g := &Guard{caps: caps, comps: comps, rates: map[string]*rate{}, history: map[string][]float64{},
		Totals: map[string]uint64{}, first: map[string]uint64{}, Max: map[string]float64{}, sum: map[string]float64{},
		Warned: map[string]bool{}}
	for n := range comps {
		g.names = append(g.names, n)
	}
	sort.Strings(g.names)
	return g, nil
}

// Observe records one sample. Counters that went backwards (a restarted
// container, a re-created nftables counter) restart from the new value.
func (g *Guard) Observe(s Sample) {
	recv := s.Received
	if recv.IsZero() {
		recv = s.T
	}
	if g.started.IsZero() {
		g.started = recv
	}
	for k, v := range s.Counters {
		r, ok := g.rates[k]
		if !ok {
			r = &rate{}
			g.rates[k] = r
		}
		if _, ok := g.first[k]; !ok {
			g.first[k] = v
		}
		if r.seen && v >= r.last {
			if dt := s.T.Sub(r.at).Seconds(); dt > 0 {
				r.bps = float64(v-r.last) * 8 / dt
			}
			g.Totals[k] += v - r.last
		} else if r.seen {
			r.bps = 0 // reset: no rate for this interval
		}
		r.last, r.at, r.recv, r.seen = v, s.T, recv, true
	}
}

// Evaluate applies the caps at time now with the latest rates.
func (g *Guard) Evaluate(now time.Time) Verdict {
	v := Verdict{T: now, Mbps: map[string]float64{}}
	for _, name := range g.names {
		var bps float64
		for _, k := range g.comps[name] {
			r, ok := g.rates[k]
			if !ok || !r.seen {
				v.Incomplete = true
				if now.Sub(g.started) > g.caps.Stale && !g.started.IsZero() {
					v.Abort, v.Reason = true, fmt.Sprintf("monitor lost: no sample of %s for component %s", k, name)
				}
				continue
			}
			if g.caps.Stale > 0 && now.Sub(r.recv) > g.caps.Stale {
				v.Abort, v.Reason = true, fmt.Sprintf("monitor lost: %s not sampled for %s", k, now.Sub(r.recv).Round(time.Second))
			}
			bps += r.bps
		}
		mbps := bps / 1e6
		v.Mbps[name] = mbps
		v.Aggregate += mbps
	}
	if v.Abort {
		return v
	}
	g.ticks++
	for _, name := range g.names {
		m := v.Mbps[name]
		g.track(name, m)
		if m > g.caps.ComponentTarget {
			v.Warnings = append(v.Warnings, fmt.Sprintf("%s at %.1f Mbps, above the %.0f-Mbps design target", name, m, g.caps.ComponentTarget))
			g.Warned[name] = true
		}
		if g.breached(name, g.caps.ComponentHard) {
			v.Abort, v.Reason = true, fmt.Sprintf("network cap: %s above %.0f Mbps (%s)", name, g.caps.ComponentHard, g.rule())
		}
	}
	g.track("", v.Aggregate)
	if v.Aggregate > g.caps.AggregateTarget {
		v.Warnings = append(v.Warnings, fmt.Sprintf("aggregate at %.1f Mbps, above the %.0f-Mbps design target", v.Aggregate, g.caps.AggregateTarget))
		g.Warned[""] = true
	}
	if !v.Abort && g.breached("", g.caps.AggregateHard) {
		v.Abort, v.Reason = true, fmt.Sprintf("network cap: aggregate of %d components above %.0f Mbps (%s)", len(g.names), g.caps.AggregateHard, g.rule())
	}
	return v
}

func (g *Guard) rule() string {
	if g.caps.Consecutive > 0 {
		return fmt.Sprintf("%d consecutive samples", g.caps.Consecutive)
	}
	return fmt.Sprintf("mean of %d samples", g.caps.AverageSamples)
}

func (g *Guard) track(name string, m float64) {
	n := g.caps.Consecutive
	if n <= 0 {
		n = g.caps.AverageSamples
	}
	h := append(g.history[name], m)
	if len(h) > n {
		h = h[len(h)-n:]
	}
	g.history[name] = h
	if m > g.Max[name] {
		g.Max[name] = m
	}
	g.sum[name] += m
}

func (g *Guard) breached(name string, hard float64) bool {
	h := g.history[name]
	if g.caps.Consecutive > 0 {
		if len(h) < g.caps.Consecutive {
			return false
		}
		for _, m := range h {
			if m <= hard {
				return false
			}
		}
		return true
	}
	if len(h) < g.caps.AverageSamples {
		return false
	}
	var s float64
	for _, m := range h {
		s += m
	}
	return s/float64(len(h)) > hard
}

// Summary of a guarded cell, for the result files.
type Summary struct {
	MaxMbps      map[string]float64 `json:"max_mbps"`
	MeanMbps     map[string]float64 `json:"mean_mbps"`
	MaxAggregate float64            `json:"max_aggregate_mbps"`
	Bytes        map[string]uint64  `json:"bytes"`
	Warned       []string           `json:"warned,omitempty"`
	Caps         Caps               `json:"caps"`
}

// Summarise returns per-component maxima and means and the bytes per counter.
func (g *Guard) Summarise() Summary {
	s := Summary{MaxMbps: map[string]float64{}, MeanMbps: map[string]float64{}, Bytes: g.Totals, Caps: g.caps}
	for _, n := range g.names {
		s.MaxMbps[n] = g.Max[n]
		if g.ticks > 0 {
			s.MeanMbps[n] = g.sum[n] / float64(g.ticks)
		}
	}
	s.MaxAggregate = g.Max[""]
	for n := range g.Warned {
		if n == "" {
			n = "aggregate"
		}
		s.Warned = append(s.Warned, n)
	}
	sort.Strings(s.Warned)
	return s
}

// PlannedCell is one cell of a plan as the pre-flight sees it.
type PlannedCell struct {
	ID   string  `json:"id"`
	Rate float64 `json:"rate"` // requests per second
	// BytesPerRequest at each component: every crossing of its interfaces, both
	// directions (from a probe; see Probe).
	BytesPerRequest map[string]float64 `json:"bytes_per_request"`
	// FixedMbps: traffic independent of the rate (telemetry heartbeat, a second
	// task's idle sync), per component.
	FixedMbps map[string]float64 `json:"fixed_mbps,omitempty"`
}

// Framing is the safety factor on probe-measured bytes (~5%, METHODOLOGY.md section 9).
const Framing = 1.05

// Expected returns the expected Mbps per component and in aggregate.
func (p PlannedCell) Expected() (map[string]float64, float64) {
	out := map[string]float64{}
	var agg float64
	keys := map[string]bool{}
	for k := range p.BytesPerRequest {
		keys[k] = true
	}
	for k := range p.FixedMbps {
		keys[k] = true
	}
	for k := range keys {
		m := p.BytesPerRequest[k]*Framing*8*p.Rate/1e6 + p.FixedMbps[k]
		out[k] = m
		agg += m
	}
	return out, agg
}

// MaxRate is the highest rate at which every component stays at or below its
// design target and the aggregate at or below its own.
func (p PlannedCell) MaxRate(c Caps) float64 {
	best := math.Inf(1)
	var perReqAgg, fixedAgg float64
	for k, b := range p.BytesPerRequest {
		perReq := b * Framing * 8 / 1e6
		perReqAgg += perReq
		fixedAgg += p.FixedMbps[k]
		if perReq > 0 {
			best = math.Min(best, (c.ComponentTarget-p.FixedMbps[k])/perReq)
		}
	}
	for k, f := range p.FixedMbps {
		if _, ok := p.BytesPerRequest[k]; !ok {
			fixedAgg += f
		}
	}
	if perReqAgg > 0 {
		best = math.Min(best, (c.AggregateTarget-fixedAgg)/perReqAgg)
	}
	if best < 0 {
		return 0
	}
	return best
}

// Violation is a planned cell that would cross a design target.
type Violation struct {
	Cell      string  `json:"cell"`
	What      string  `json:"what"`
	Mbps      float64 `json:"mbps"`
	TargetMbp float64 `json:"target_mbps"`
	MaxRate   float64 `json:"max_rate"`
}

// Preflight returns every violation of the design targets in a plan. An empty
// result means the plan may start.
func Preflight(c Caps, plan []PlannedCell) []Violation {
	var out []Violation
	for _, p := range plan {
		per, agg := p.Expected()
		names := make([]string, 0, len(per))
		for n := range per {
			names = append(names, n)
		}
		sort.Strings(names)
		for _, n := range names {
			if per[n] > c.ComponentTarget {
				out = append(out, Violation{Cell: p.ID, What: n, Mbps: per[n], TargetMbp: c.ComponentTarget, MaxRate: p.MaxRate(c)})
			}
		}
		if agg > c.AggregateTarget {
			out = append(out, Violation{Cell: p.ID, What: "aggregate", Mbps: agg, TargetMbp: c.AggregateTarget, MaxRate: p.MaxRate(c)})
		}
	}
	return out
}

// Probe converts a probe's byte totals into bytes per request per component.
func Probe(comps Components, totals map[string]uint64, requests int64) (map[string]float64, error) {
	if requests <= 0 {
		return nil, fmt.Errorf("probe completed no requests")
	}
	out := map[string]float64{}
	var missing []string
	for name, keys := range comps {
		var b uint64
		for _, k := range keys {
			v, ok := totals[k]
			if !ok {
				missing = append(missing, k)
			}
			b += v
		}
		out[name] = float64(b) / float64(requests)
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return out, fmt.Errorf("probe has no bytes for %s", strings.Join(missing, ", "))
	}
	return out, nil
}
