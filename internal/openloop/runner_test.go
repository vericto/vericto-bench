// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package openloop

import (
	"context"
	"errors"
	"math"
	"math/rand"
	"sync/atomic"
	"testing"
	"time"

	"github.com/vericto/vericto-bench/internal/hist"
)

func TestConstantScheduleIsExactAndDoesNotDrift(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	s := NewSchedule(start, 8000, false, 1)
	var last time.Time
	for i := int64(0); i < 8000*600; i++ { // ten minutes at 8,000/s
		seq, at := s.Next()
		if seq != i {
			t.Fatalf("seq %d, want %d", seq, i)
		}
		last = at
	}
	want := start.Add(time.Duration(float64(8000*600-1) * float64(time.Second) / 8000))
	if d := last.Sub(want); d < -time.Microsecond || d > time.Microsecond {
		t.Fatalf("last send %v, want %v (drift %v)", last, want, d)
	}
}

func TestPoissonScheduleIsSeededAndHasTheRightMean(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	a := NewSchedule(start, 1000, true, 42)
	b := NewSchedule(start, 1000, true, 42)
	var at time.Time
	for i := 0; i < 100_000; i++ {
		_, x := a.Next()
		_, y := b.Next()
		if !x.Equal(y) {
			t.Fatalf("same seed, different schedule at %d", i)
		}
		at = x
	}
	mean := at.Sub(start).Seconds() / 99_999
	if math.Abs(mean-0.001)/0.001 > 0.02 {
		t.Fatalf("mean gap %.6f s, want 0.001 +- 2%%", mean)
	}
}

func TestCountBeforeMatchesTheSchedule(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	for _, poisson := range []bool{false, true} {
		for _, rate := range []float64{3, 333.3, 1000, 7777} {
			end := start.Add(1700 * time.Millisecond)
			s := NewSchedule(start, rate, poisson, 9)
			var n int64
			for {
				_, at := s.Next()
				if !at.Before(end) {
					break
				}
				n++
			}
			if got := CountBefore(start, rate, poisson, 9, end); got != n {
				t.Fatalf("poisson=%v rate=%v: CountBefore %d, schedule %d", poisson, rate, got, n)
			}
		}
	}
}

func instant(context.Context, int, *rand.Rand) Outcome { return Outcome{Class: "q", Statements: 1} }

// Every request of the schedule is sent and completed when the target keeps up.
func TestNoRequestIsSkipped(t *testing.T) {
	var calls atomic.Int64
	r := Run(context.Background(), Config{Rate: 500, Conns: 4, Duration: time.Second, Interval: 250 * time.Millisecond},
		func(ctx context.Context, c int, rng *rand.Rand) Outcome { calls.Add(1); return instant(ctx, c, rng) })
	if r.Status != StatusOK {
		t.Fatalf("status %s (%s)", r.Status, r.Reason)
	}
	if r.Scheduled != 500 || r.Completed != 500 || r.Unsent != 0 || r.Incomplete != 0 {
		t.Fatalf("scheduled %d completed %d unsent %d incomplete %d", r.Scheduled, r.Completed, r.Unsent, r.Incomplete)
	}
	if calls.Load() != r.SentTotal || r.SentTotal+r.UnsentTotal != r.ScheduledTotal {
		t.Fatalf("accounting: calls %d sent %d unsent %d scheduled %d", calls.Load(), r.SentTotal, r.UnsentTotal, r.ScheduledTotal)
	}
	if r.Latency.TotalCount() != 500 || len(r.Intervals) != 4 {
		t.Fatalf("histogram %d values, %d intervals", r.Latency.TotalCount(), len(r.Intervals))
	}
	var sum int64
	for _, iv := range r.Intervals {
		sum += iv.Latency.TotalCount()
	}
	if sum != 500 {
		t.Fatalf("intervals hold %d values, want 500", sum)
	}
}

// Latency is measured from the intended send time: a 300-ms stall of the
// target appears in every request that was due during it, not only in the one
// request that was in flight (which is all a closed-loop generator would see).
func TestStallIsNotHidden(t *testing.T) {
	var n atomic.Int64
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		if n.Add(1) == 50 {
			time.Sleep(300 * time.Millisecond)
		}
		return Outcome{Class: "q", Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 100, Conns: 1, Duration: 2 * time.Second}, exec)
	if r.Completed != r.Scheduled || r.Unsent != 0 {
		t.Fatalf("completed %d of %d, unsent %d", r.Completed, r.Scheduled, r.Unsent)
	}
	slow := hist.CountAbove(r.Latency, 150_000)
	if slow < 10 {
		t.Fatalf("only %d requests above 150 ms; the stall was hidden", slow)
	}
	if p := r.Latency.ValueAtQuantile(99); p < 200_000 {
		t.Fatalf("p99 %d us, want >= 200 ms", p)
	}
	if p := r.QueueWait.ValueAtQuantile(99); p < 150_000 {
		t.Fatalf("queue wait p99 %d us: the wait was not attributed to the queue", p)
	}
	if p := r.Service.ValueAtQuantile(50); p > 20_000 {
		t.Fatalf("service p50 %d us, want small", p)
	}
}

func TestLatencyIncludesServiceTime(t *testing.T) {
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		time.Sleep(20 * time.Millisecond)
		return Outcome{Class: "q", Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 50, Conns: 8, Duration: time.Second}, exec)
	if r.Status != StatusOK {
		t.Fatalf("status %s (%s)", r.Status, r.Reason)
	}
	if p := r.Latency.ValueAtQuantile(50); p < 20_000 || p > 40_000 {
		t.Fatalf("p50 %d us, want about 20 ms", p)
	}
}

// A target slower than the offered rate is reported saturated, and nothing is
// dropped without being counted.
func TestSaturationIsDetected(t *testing.T) {
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		time.Sleep(10 * time.Millisecond) // capacity about 100/s on one connection
		return Outcome{Class: "q", Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 200, Conns: 1, Duration: time.Second, Drain: 200 * time.Millisecond}, exec)
	if r.Status != StatusSaturated {
		t.Fatalf("status %s, want saturated", r.Status)
	}
	if r.Achieved >= 0.99*r.Offered {
		t.Fatalf("achieved %.1f of %.1f", r.Achieved, r.Offered)
	}
	if r.Completed+r.Incomplete+r.Unsent != r.Scheduled {
		t.Fatalf("completed %d + incomplete %d + unsent %d != scheduled %d", r.Completed, r.Incomplete, r.Unsent, r.Scheduled)
	}
}

func TestQueueOverflowStopsSendingAndCountsTheRest(t *testing.T) {
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		select {
		case <-time.After(5 * time.Millisecond):
		case <-ctx.Done():
		}
		return Outcome{Class: "q", Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 2000, Conns: 1, MaxQueue: 50, Duration: time.Second, Drain: 100 * time.Millisecond}, exec)
	if r.Status != StatusSaturated || r.Reason != "queue above max-queue" {
		t.Fatalf("status %s (%s)", r.Status, r.Reason)
	}
	if r.UnsentTotal == 0 || r.SentTotal+r.UnsentTotal != r.ScheduledTotal {
		t.Fatalf("sent %d + unsent %d != scheduled %d", r.SentTotal, r.UnsentTotal, r.ScheduledTotal)
	}
}

// The stop channel (the network-cap guard) aborts the cell at once and the
// unsent requests are counted.
func TestStopAbortsAndAccounts(t *testing.T) {
	stop := make(chan struct{})
	time.AfterFunc(300*time.Millisecond, func() { close(stop) })
	r := Run(context.Background(), Config{Rate: 1000, Conns: 2, Duration: 2 * time.Second, Stop: stop, StopReason: "network cap"}, instant)
	if r.Status != StatusAborted || r.Reason != "network cap" {
		t.Fatalf("status %s (%s)", r.Status, r.Reason)
	}
	if r.Unsent < 1000 || r.SentTotal+r.UnsentTotal != r.ScheduledTotal {
		t.Fatalf("unsent %d, sent %d, scheduled %d", r.Unsent, r.SentTotal, r.ScheduledTotal)
	}
}

func TestWarmupIsDiscarded(t *testing.T) {
	r := Run(context.Background(), Config{Rate: 200, Conns: 2, Warmup: 500 * time.Millisecond, Duration: 500 * time.Millisecond}, instant)
	if r.ScheduledTotal != 200 || r.Scheduled != 100 || r.Completed != 100 {
		t.Fatalf("total %d window %d completed %d", r.ScheduledTotal, r.Scheduled, r.Completed)
	}
}

func TestErrorsAndBlocksAreCountedApart(t *testing.T) {
	var n atomic.Int64
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		switch n.Add(1) % 10 {
		case 0:
			return Outcome{Class: "bad", Err: errors.New("boom")}
		case 1:
			return Outcome{Class: "blocked", Blocked: true, Statements: 1}
		}
		return Outcome{Class: "ok", Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 500, Conns: 2, Duration: time.Second}, exec)
	if r.Errors != 50 || r.Blocked != 50 {
		t.Fatalf("errors %d blocked %d", r.Errors, r.Blocked)
	}
	if r.Latency.TotalCount() != 450 || r.Allowed.TotalCount() != 400 {
		t.Fatalf("latency %d allowed %d", r.Latency.TotalCount(), r.Allowed.TotalCount())
	}
	if r.Classes["bad"].Errors != 50 || r.Classes["blocked"].Blocked != 50 || len(r.ErrSamples) == 0 {
		t.Fatalf("classes %+v", r.Classes)
	}
}

func TestClosedLoopMeasuresServiceTime(t *testing.T) {
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		time.Sleep(2 * time.Millisecond)
		return Outcome{Class: "q", Statements: 1}
	}
	r := Run(context.Background(), Config{Closed: true, Conns: 4, Duration: 500 * time.Millisecond}, exec)
	if r.Loop != "closed" || r.Status != StatusOK {
		t.Fatalf("loop %s status %s", r.Loop, r.Status)
	}
	// 4 connections x ~2 ms: well over 1,000/s is impossible, well under 500/s is a bug.
	if r.Achieved < 500 || r.Achieved > 2100 {
		t.Fatalf("achieved %.0f/s", r.Achieved)
	}
}

func TestAllBlockedWorkloadKeepsAHeadline(t *testing.T) {
	exec := func(ctx context.Context, c int, rng *rand.Rand) Outcome {
		return Outcome{Class: "blocked_delete", Blocked: true, Statements: 1}
	}
	r := Run(context.Background(), Config{Rate: 200, Conns: 2, Duration: 500 * time.Millisecond, BlockedInHeadline: true}, exec)
	if r.Allowed.TotalCount() != 100 || r.Intervals[0].Latency.TotalCount() != 100 {
		t.Fatalf("headline %d, interval %d", r.Allowed.TotalCount(), r.Intervals[0].Latency.TotalCount())
	}
}
