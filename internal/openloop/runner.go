// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package openloop is the timing core of vbench.
//
// Open loop: request i is due at a time fixed in advance (Schedule). A
// dispatcher hands each due request to an idle connection of a fixed pool; if
// none is idle, the request waits in a queue and the wait is part of its
// latency. Latency is completion time minus intended send time, so a stall of
// the target shows up in every request that was due during it (no coordinated
// omission). Service time (completion minus actual send) and queue wait are
// recorded separately. No request is ever skipped silently: every request of the
// schedule is either completed, or counted as unsent or incomplete with the
// reason, and the identity scheduled = sent + unsent always holds.
//
// Closed loop (saturation throughput only): each connection sends its next
// request as soon as the previous one completes; latency is service time and is
// labelled "at saturation" by the analysis.
package openloop

import (
	"context"
	"math/rand"
	"sort"
	"sync"
	"time"

	hdr "github.com/HdrHistogram/hdrhistogram-go"

	"github.com/vericto/vericto-bench/internal/hist"
)

// Outcome is what one request did.
type Outcome struct {
	Class      string // statement class, for per-class histograms
	Statements int    // statements in the request (a transaction counts each)
	Blocked    bool   // refused by the proxy's rules, as the workload expects
	Err        error  // any other error: counted, excluded from latency
}

// Exec runs one request on connection conn. It must honour ctx.
type Exec func(ctx context.Context, conn int, rng *rand.Rand) Outcome

// Config of one cell.
type Config struct {
	Closed   bool          // closed loop (saturation throughput)
	Rate     float64       // open loop: requests per second
	Poisson  bool          // open loop: exponential gaps instead of constant
	Seed     int64         // schedule and per-connection PRNG seed
	Conns    int           // connection pool size
	Warmup   time.Duration // discarded
	Duration time.Duration // measured window
	// MaxQueue: open loop, requests waiting for a connection beyond which the
	// cell is saturated and stops sending (default 10 x rate, at least 100).
	MaxQueue int
	// Drain: after the window, how long in-flight and queued requests may take
	// to complete before they are counted as incomplete (default 30 s).
	Drain time.Duration
	// Interval: length of the histogram intervals (default 10 s).
	Interval time.Duration
	// Lead: delay between Run and the first intended send (default 100 ms), so
	// the first request is not late by the time it takes to start goroutines.
	Lead time.Duration
	// Stop aborts the cell when closed (the network-cap guard's stop file).
	Stop       <-chan struct{}
	StopReason string
	// BlockedInHeadline: the workload is blocked statements only (W6), so the
	// headline aggregate and its intervals are the blocked requests.
	BlockedInHeadline bool
}

// Status of a cell.
const (
	StatusOK        = "ok"
	StatusSaturated = "saturated"
	StatusAborted   = "aborted"
)

// ClassResult is the per-class part of a result.
type ClassResult struct {
	Latency hist.Summary `json:"latency"`
	Blocked int64        `json:"blocked"`
	Errors  int64        `json:"errors"`
}

// Interval is one histogram interval, keyed by intended send time (open loop)
// or actual send time (closed loop).
type Interval struct {
	Start     time.Time
	End       time.Time
	Latency   *hdr.Histogram
	Completed int64
}

// Result of a cell. Counts refer to the measured window unless named Total.
type Result struct {
	Loop        string    `json:"loop"`
	Status      string    `json:"status"`
	Reason      string    `json:"reason,omitempty"`
	Offered     float64   `json:"offered_rate"`  // requests/s scheduled (open loop)
	Achieved    float64   `json:"achieved_rate"` // requests/s completed in the window
	Statements  float64   `json:"statements_per_s"`
	Start       time.Time `json:"start"`
	MeasureFrom time.Time `json:"measure_from"`
	End         time.Time `json:"end"`

	ScheduledTotal int64 `json:"scheduled_total"` // whole schedule, warm-up included
	SentTotal      int64 `json:"sent_total"`
	UnsentTotal    int64 `json:"unsent_total"` // never sent: cell stopped or queue overflow
	Scheduled      int64 `json:"scheduled"`    // due in the window
	Completed      int64 `json:"completed"`    // due in the window and completed
	Incomplete     int64 `json:"incomplete"`   // due in the window, sent, not completed after the drain
	Unsent         int64 `json:"unsent"`       // due in the window, never sent
	Errors         int64 `json:"errors"`
	Blocked        int64 `json:"blocked"`
	MaxQueueDepth  int   `json:"max_queue_depth"`

	Latency    *hdr.Histogram `json:"-"` // from intended send time (open) / service (closed)
	Allowed    *hdr.Histogram `json:"-"` // Latency without blocked requests: the headline aggregate
	Service    *hdr.Histogram `json:"-"` // completion minus actual send
	QueueWait  *hdr.Histogram `json:"-"` // actual send minus intended send
	GenLag     *hdr.Histogram `json:"-"` // dispatcher lateness handing a due request to the queue
	Classes    map[string]*ClassResult
	classHists map[string]*hdr.Histogram
	Intervals  []Interval `json:"-"`
	ErrSamples []string   `json:"error_samples,omitempty"`
	Stmts      int64      `json:"statements"`
}

type job struct {
	seq   int64
	due   time.Time
	inWin bool
}

type worker struct {
	latency, allowed      *hdr.Histogram
	service, wait         *hdr.Histogram
	classes               map[string]*hdr.Histogram
	classBlocked          map[string]int64
	classErrs             map[string]int64
	intervals             []*hdr.Histogram
	intervalDone          []int64
	completed, incomplete int64
	doneInWindow          int64
	errs, blocked, stmts  int64
	errSample             string
}

func newWorker(nIntervals int) *worker {
	w := &worker{latency: hist.New(), allowed: hist.New(), service: hist.New(), wait: hist.New(),
		classes: map[string]*hdr.Histogram{}, classBlocked: map[string]int64{}, classErrs: map[string]int64{},
		intervals: make([]*hdr.Histogram, nIntervals), intervalDone: make([]int64, nIntervals)}
	for i := range w.intervals {
		w.intervals[i] = hist.New()
	}
	return w
}

func (c *Config) defaults() {
	if c.Conns < 1 {
		c.Conns = 1
	}
	if c.MaxQueue <= 0 {
		c.MaxQueue = int(10 * c.Rate)
		if c.MaxQueue < 100 {
			c.MaxQueue = 100
		}
	}
	if c.Drain <= 0 {
		c.Drain = 30 * time.Second
	}
	if c.Interval <= 0 {
		c.Interval = 10 * time.Second
	}
	if c.Lead <= 0 {
		c.Lead = 100 * time.Millisecond
	}
}

func nIntervals(c Config) int {
	n := int((c.Duration + c.Interval - 1) / c.Interval)
	if n < 1 {
		n = 1
	}
	return n
}

// record files one completed request into w. t is the time the window is keyed
// on (intended send in open loop, actual send in closed loop).
func (w *worker) record(c Config, measureFrom, end time.Time, key, sent, done time.Time, o Outcome) {
	if key.Before(measureFrom) || !key.Before(end) {
		return
	}
	w.completed++
	if !done.Before(measureFrom) && done.Before(end) {
		w.doneInWindow++
	}
	if o.Err != nil {
		w.errs++
		w.classErrs[o.Class]++
		if w.errSample == "" {
			w.errSample = truncate(o.Err.Error(), 300)
		}
		return
	}
	lat := done.Sub(key)
	if o.Blocked {
		w.blocked++
		w.classBlocked[o.Class]++
	}
	w.stmts += int64(o.Statements)
	hist.Record(w.latency, lat)
	hist.Record(w.service, done.Sub(sent))
	hist.Record(w.wait, sent.Sub(key))
	h, ok := w.classes[o.Class]
	if !ok {
		h = hist.New()
		w.classes[o.Class] = h
	}
	hist.Record(h, lat)
	if o.Blocked && !c.BlockedInHeadline {
		return // blocked requests stay out of the headline aggregate and its intervals
	}
	hist.Record(w.allowed, lat)
	i := int(key.Sub(measureFrom) / c.Interval)
	if i >= 0 && i < len(w.intervals) {
		hist.Record(w.intervals[i], lat)
		w.intervalDone[i]++
	}
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

// Run executes one cell and returns its result. It never returns early on a
// slow target: the window is fixed by the clock, and what could not be done in
// it is counted.
func Run(ctx context.Context, c Config, exec Exec) *Result {
	c.defaults()
	ni := nIntervals(c)
	start := time.Now().Add(c.Lead)
	measureFrom := start.Add(c.Warmup)
	end := measureFrom.Add(c.Duration)
	workers := make([]*worker, c.Conns)
	for i := range workers {
		workers[i] = newWorker(ni)
	}
	res := &Result{Loop: "open", Offered: c.Rate, Start: start, MeasureFrom: measureFrom, End: end}
	if c.Closed {
		res.Loop = "closed"
		res.Offered = 0
		runClosed(ctx, c, exec, workers, start, measureFrom, end, res)
	} else {
		runOpen(ctx, c, exec, workers, start, measureFrom, end, res)
	}
	merge(c, res, workers, measureFrom, ni)
	return res
}

func runOpen(ctx context.Context, c Config, exec Exec, workers []*worker, start, measureFrom, end time.Time, res *Result) {
	q := make(chan job, c.MaxQueue)
	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	var wg sync.WaitGroup
	for i := range workers {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			w := workers[i]
			rng := rand.New(rand.NewSource(c.Seed + int64(i+1)*7919))
			for j := range q {
				if runCtx.Err() != nil {
					if j.inWin {
						w.incomplete++
					}
					continue
				}
				sent := time.Now()
				o := exec(runCtx, i, rng)
				done := time.Now()
				if runCtx.Err() != nil && o.Err != nil {
					// Cut off by the drain deadline: not a completion.
					if j.inWin {
						w.incomplete++
					}
					continue
				}
				w.record(c, measureFrom, end, j.due, sent, done, o)
			}
		}(i)
	}

	sch := NewSchedule(start, c.Rate, c.Poisson, c.Seed)
	genLag := hist.New()
	timer := time.NewTimer(time.Hour)
	timer.Stop()
	var sent, sentInWin int64
	stopped := false
	maxDepth := 0
loop:
	for {
		_, due := sch.Next()
		if !due.Before(end) {
			break
		}
		if d := time.Until(due); d > 0 {
			timer.Reset(d)
			select {
			case <-c.Stop:
				timer.Stop()
				stopped = true
				break loop
			case <-ctx.Done():
				timer.Stop()
				stopped = true
				break loop
			case <-timer.C:
			}
		} else {
			select {
			case <-c.Stop:
				stopped = true
				break loop
			case <-ctx.Done():
				stopped = true
				break loop
			default:
			}
		}
		inWin := !due.Before(measureFrom)
		select {
		case q <- job{due: due, inWin: inWin}:
		default:
			// Every connection busy and the queue full: the target is far past
			// its knee. Stop sending; the rest of the schedule is counted unsent.
			res.Status = StatusSaturated
			res.Reason = "queue above max-queue"
			break loop
		}
		if inWin {
			hist.Record(genLag, time.Since(due))
			sentInWin++
		}
		sent++
		if l := len(q); l > maxDepth {
			maxDepth = l
		}
	}
	if stopped {
		res.Status = StatusAborted
		res.Reason = c.StopReason
		if res.Reason == "" {
			res.Reason = "stopped"
		}
	}
	close(q)

	// Drain: let what was sent finish, up to c.Drain after the window.
	doneCh := make(chan struct{})
	go func() { wg.Wait(); close(doneCh) }()
	deadline := time.Until(end.Add(c.Drain))
	if deadline < time.Second {
		deadline = time.Second
	}
	select {
	case <-doneCh:
	case <-time.After(deadline):
		cancel()
		<-doneCh
	}

	res.ScheduledTotal = CountBefore(start, c.Rate, c.Poisson, c.Seed, end)
	res.SentTotal = sent
	res.UnsentTotal = res.ScheduledTotal - sent
	res.Scheduled = res.ScheduledTotal - CountBefore(start, c.Rate, c.Poisson, c.Seed, measureFrom)
	res.Unsent = res.Scheduled - sentInWin
	res.MaxQueueDepth = maxDepth
	res.GenLag = genLag
}

func runClosed(ctx context.Context, c Config, exec Exec, workers []*worker, start, measureFrom, end time.Time, res *Result) {
	runCtx, cancel := context.WithDeadline(ctx, end.Add(c.Drain))
	defer cancel()
	var wg sync.WaitGroup
	var mu sync.Mutex
	stopped := false
	for i := range workers {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			w := workers[i]
			rng := rand.New(rand.NewSource(c.Seed + int64(i+1)*7919))
			time.Sleep(time.Until(start))
			for {
				select {
				case <-c.Stop:
					mu.Lock()
					stopped = true
					mu.Unlock()
					return
				default:
				}
				sent := time.Now()
				if !sent.Before(end) || runCtx.Err() != nil {
					return
				}
				o := exec(runCtx, i, rng)
				w.record(c, measureFrom, end, sent, sent, time.Now(), o)
			}
		}(i)
	}
	wg.Wait()
	if stopped {
		res.Status = StatusAborted
		res.Reason = c.StopReason
		if res.Reason == "" {
			res.Reason = "stopped"
		}
	}
	res.GenLag = hist.New()
}

func merge(c Config, res *Result, workers []*worker, measureFrom time.Time, ni int) {
	res.Latency, res.Allowed, res.Service, res.QueueWait = hist.New(), hist.New(), hist.New(), hist.New()
	res.Classes = map[string]*ClassResult{}
	res.classHists = map[string]*hdr.Histogram{}
	res.Intervals = make([]Interval, ni)
	for i := range res.Intervals {
		s := measureFrom.Add(time.Duration(i) * c.Interval)
		e := s.Add(c.Interval)
		if e.After(res.End) {
			e = res.End
		}
		res.Intervals[i] = Interval{Start: s, End: e, Latency: hist.New()}
	}
	var doneInWindow int64
	for _, w := range workers {
		res.Latency.Merge(w.latency)
		res.Allowed.Merge(w.allowed)
		res.Service.Merge(w.service)
		res.QueueWait.Merge(w.wait)
		res.Completed += w.completed
		res.Incomplete += w.incomplete
		res.Errors += w.errs
		res.Blocked += w.blocked
		res.Stmts += w.stmts
		doneInWindow += w.doneInWindow
		for k, h := range w.classes {
			if _, ok := res.classHists[k]; !ok {
				res.classHists[k] = hist.New()
			}
			res.classHists[k].Merge(h)
		}
		for k, v := range w.classBlocked {
			res.cls(k).Blocked += v
		}
		for k, v := range w.classErrs {
			res.cls(k).Errors += v
		}
		for i := range w.intervals {
			res.Intervals[i].Latency.Merge(w.intervals[i])
			res.Intervals[i].Completed += w.intervalDone[i]
		}
		if w.errSample != "" && len(res.ErrSamples) < 5 {
			res.ErrSamples = append(res.ErrSamples, w.errSample)
		}
	}
	names := make([]string, 0, len(res.classHists))
	for k := range res.classHists {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		res.cls(k).Latency = hist.Summarise(res.classHists[k], false)
	}
	secs := c.Duration.Seconds()
	res.Achieved = float64(doneInWindow) / secs
	res.Statements = float64(res.Stmts) / secs
	if res.Loop == "closed" {
		res.Scheduled = res.Completed
		res.ScheduledTotal = res.Completed
		res.SentTotal = res.Completed
	}
	if res.Status == "" {
		res.Status = StatusOK
		if res.Loop == "open" {
			switch {
			case res.Incomplete > 0:
				res.Status, res.Reason = StatusSaturated, "requests still in flight after the drain"
			case res.Achieved < 0.99*res.Offered && float64(res.Scheduled)-float64(doneInWindow) > 2:
				res.Status, res.Reason = StatusSaturated, "achieved rate below 99% of offered"
			}
		}
	}
}

func (r *Result) cls(k string) *ClassResult {
	c, ok := r.Classes[k]
	if !ok {
		c = &ClassResult{}
		r.Classes[k] = c
	}
	return c
}
