// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package hist wraps HdrHistogram with the conventions used by every vericto-bench
// tool: values in microseconds, 1 us to 120 s, 3 significant digits, and two
// export formats (the HdrHistogram V2 compressed encoding for exact merging, and
// a sparse bucket list that the Python analysis reads without an HDR library).
package hist

import (
	"time"

	hdr "github.com/HdrHistogram/hdrhistogram-go"
)

// Lowest and highest trackable values, in microseconds.
const (
	Lowest  = 1
	Highest = 120_000_000
	Digits  = 3
)

// New returns an empty microsecond histogram.
func New() *hdr.Histogram { return hdr.New(Lowest, Highest, Digits) }

// Record adds one duration, clamped to the trackable range so that a value is
// never silently dropped (RecordValue refuses out-of-range values).
func Record(h *hdr.Histogram, d time.Duration) {
	us := d.Microseconds()
	if us < Lowest {
		us = Lowest
	}
	if us > Highest {
		us = Highest
	}
	_ = h.RecordValue(us)
}

// Summary is the percentile set every report uses, in milliseconds.
type Summary struct {
	Count int64   `json:"count"`
	Mean  float64 `json:"mean_ms"`
	P50   float64 `json:"p50_ms"`
	P90   float64 `json:"p90_ms"`
	P99   float64 `json:"p99_ms"`
	P999  float64 `json:"p999_ms"`
	Max   float64 `json:"max_ms"`
	// Encoded is the HdrHistogram V2 compressed encoding (base64), so cells and
	// repetitions can be merged exactly later.
	Encoded string `json:"hdr,omitempty"`
}

// Summarise returns the percentiles of h; withEncoding adds the HDR encoding.
func Summarise(h *hdr.Histogram, withEncoding bool) Summary {
	ms := func(v int64) float64 { return float64(v) / 1000 }
	s := Summary{Count: h.TotalCount()}
	if s.Count == 0 {
		return s
	}
	s.Mean = h.Mean() / 1000
	s.P50 = ms(h.ValueAtQuantile(50))
	s.P90 = ms(h.ValueAtQuantile(90))
	s.P99 = ms(h.ValueAtQuantile(99))
	s.P999 = ms(h.ValueAtQuantile(99.9))
	s.Max = ms(h.Max())
	if withEncoding {
		if b, err := h.Encode(hdr.V2CompressedEncodingCookieBase); err == nil {
			s.Encoded = string(b)
		}
	}
	return s
}

// Sparse lists the non-empty buckets of h as [value_us, count] pairs, where
// value_us is the highest value equivalent to the bucket (what HdrHistogram
// reports for a percentile). Summing the pairs of several histograms and taking
// the cumulative count gives the same percentiles as merging them.
func Sparse(h *hdr.Histogram) [][2]int64 {
	out := [][2]int64{} // [] rather than null in JSON for an empty interval
	for _, b := range h.Distribution() {
		if b.Count > 0 {
			out = append(out, [2]int64{b.To, b.Count})
		}
	}
	return out
}

// CountAbove returns how many recorded values are above v microseconds.
func CountAbove(h *hdr.Histogram, v int64) int64 {
	var n int64
	for _, b := range h.Distribution() {
		if b.From > v {
			n += b.Count
		}
	}
	return n
}
