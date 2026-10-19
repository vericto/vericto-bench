// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package openloop

import (
	"math"
	"math/rand"
	"time"
)

// Schedule yields the intended send time of every request of a cell. Times are
// fixed before the cell starts and never move: a request whose time has passed
// is still sent (late), and its lateness is part of its latency. That is what
// makes the generator open loop and free of coordinated omission.
type Schedule struct {
	start   time.Time
	rate    float64
	poisson bool
	rng     *rand.Rand
	i       int64
	offset  float64 // seconds since start of the next Poisson arrival
}

// NewSchedule returns a constant-rate schedule (t_i = start + i/rate) or, with
// poisson, exponential gaps of mean 1/rate drawn from a PRNG seeded with seed,
// so a schedule is reproducible.
func NewSchedule(start time.Time, rate float64, poisson bool, seed int64) *Schedule {
	if rate <= 0 || math.IsNaN(rate) || math.IsInf(rate, 0) {
		panic("openloop: rate must be a positive finite number")
	}
	return &Schedule{start: start, rate: rate, poisson: poisson, rng: rand.New(rand.NewSource(seed))}
}

// Next returns the sequence number and intended send time of the next request.
// Constant times are computed from the index, not accumulated, so there is no
// drift over a long cell.
func (s *Schedule) Next() (int64, time.Time) {
	i := s.i
	s.i++
	if !s.poisson {
		return i, s.start.Add(time.Duration(float64(i) * float64(time.Second) / s.rate))
	}
	if i > 0 {
		s.offset += s.rng.ExpFloat64() / s.rate
	}
	return i, s.start.Add(time.Duration(s.offset * float64(time.Second)))
}

// CountBefore returns how many requests of a constant schedule fall in
// [start, t): used to account for requests that were never sent when a cell is
// stopped early. For a Poisson schedule it walks a copy of the PRNG.
func CountBefore(start time.Time, rate float64, poisson bool, seed int64, t time.Time) int64 {
	if !t.After(start) {
		return 0
	}
	if !poisson {
		n := int64(math.Ceil(t.Sub(start).Seconds() * rate))
		// Guard the boundary against float rounding: t_n must be >= t.
		for n > 0 && !start.Add(time.Duration(float64(n-1)*float64(time.Second)/rate)).Before(t) {
			n--
		}
		for start.Add(time.Duration(float64(n) * float64(time.Second) / rate)).Before(t) {
			n++
		}
		return n
	}
	s := NewSchedule(start, rate, true, seed)
	var n int64
	for {
		_, at := s.Next()
		if !at.Before(t) {
			return n
		}
		n++
	}
}
