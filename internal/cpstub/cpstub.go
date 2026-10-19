// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package cpstub is a local stand-in for the Vericto control plane, so the
// proxy's full telemetry path (serialise, sanitise, normalise, gzip, POST) runs
// as in production while the backend's cost does not enter the measurement.
//
//	GET  /api/v1/sync/rules     the engine's built-in rules (exported by
//	                            engine-eval --export-rules, so the stub and the
//	                            proxy agree by construction), a policy object and
//	                            the sensitive-column tags, with an ETag.
//	POST /api/v1/ingest/events  202; gzip decoded; per API key and verdict, an
//	                            HdrHistogram of each event's latency_ms (the
//	                            in-proxy evaluation time).
//	GET  /stats, POST /reset    for the runner, between cells.
//	GET  /healthz
//
// The mode is chosen by the proxy's API key: a key starting with "observe"
// gets monitor_mode=true, any other key gets monitor_mode=false. Nothing is
// written to disk.
package cpstub

import (
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"

	hdr "github.com/HdrHistogram/hdrhistogram-go"

	"github.com/vericto/vericto-bench/internal/hist"
)

// Rule is one rule as /sync/rules sends it.
type Rule struct {
	RuleID        string  `json:"rule_id"`
	Code          string  `json:"code"`
	Severity      string  `json:"severity"`
	DefaultAction string  `json:"default_action"`
	RuleType      string  `json:"rule_type"`
	ASTCondition  *string `json:"ast_condition_yaml"`
}

// RulesExport is the file engine-eval --export-rules writes.
type RulesExport struct {
	EngineVersion  string `json:"engine_version"`
	RulesetVersion string `json:"ruleset_version"`
	Rules          []Rule `json:"rules"`
}

// SensitiveColumn is one tag, in the engine's JSON shape.
type SensitiveColumn struct {
	Schema    *string `json:"schema"`
	Table     string  `json:"table"`
	Column    string  `json:"column"`
	Policy    string  `json:"policy"`
	MaskStyle string  `json:"mask_style,omitempty"`
}

// Config of a stub.
type Config struct {
	Rules            RulesExport
	SensitiveColumns []SensitiveColumn
	// Policy: the default policy of the proxy (critical/high block, medium
	// flag, low/informational monitor, parse errors allowed and reported).
	SeverityActions map[string]string
}

// DefaultSeverityActions is EnforcementPolicy::default() of vericto-engine.
func DefaultSeverityActions() map[string]string {
	return map[string]string{"critical": "block", "high": "block", "medium": "flag", "low": "monitor", "informational": "monitor"}
}

type key struct{ apiKey, status string }

// Server is the stub.
type Server struct {
	cfg    Config
	bodies map[bool][]byte // monitor_mode -> response body
	etags  map[bool]string

	mu         sync.Mutex
	hists      map[key]*hdr.Histogram
	events     map[key]int64
	requests   int64
	syncs      int64
	bytesWire  int64 // request bodies as received (compressed)
	bytesPlain int64 // after gzip decoding
	badBodies  int64
	lastEvent  time.Time
	since      time.Time
}

// New builds a stub; it fails if the rules are empty (a stub serving no rules
// would make every proxy cell measure an empty ruleset).
func New(cfg Config) (*Server, error) {
	if len(cfg.Rules.Rules) == 0 {
		return nil, fmt.Errorf("cpstub: no rules")
	}
	if cfg.SeverityActions == nil {
		cfg.SeverityActions = DefaultSeverityActions()
	}
	s := &Server{cfg: cfg, bodies: map[bool][]byte{}, etags: map[bool]string{}}
	for _, monitor := range []bool{false, true} {
		body := map[string]any{
			"version": cfg.Rules.RulesetVersion,
			"rules":   cfg.Rules.Rules,
			"policy": map[string]any{
				"severity_actions":     cfg.SeverityActions,
				"parse_error_action":   "allow_report",
				"monitor_mode":         monitor,
				"telemetry_query_mode": "raw",
			},
			"sensitive_columns": cfg.SensitiveColumns,
			"agent_access":      map[string]any{},
			"telemetry_quota":   "ok",
		}
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		sum := sha256.Sum256(b)
		s.bodies[monitor] = b
		s.etags[monitor] = `"` + hex.EncodeToString(sum[:8]) + `"`
	}
	s.reset()
	return s, nil
}

func (s *Server) reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.hists, s.events = map[key]*hdr.Histogram{}, map[key]int64{}
	s.requests, s.syncs, s.bytesWire, s.bytesPlain, s.badBodies = 0, 0, 0, 0, 0
	s.since = time.Now()
	s.lastEvent = time.Time{}
}

// Monitor reports whether an API key selects observe mode.
func Monitor(apiKey string) bool { return strings.HasPrefix(apiKey, "observe") }

// Handler returns the HTTP handler.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/sync/rules", s.sync)
	mux.HandleFunc("/api/v1/ingest/events", s.ingest)
	mux.HandleFunc("/stats", s.stats)
	mux.HandleFunc("/reset", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST", http.StatusMethodNotAllowed)
			return
		}
		s.reset()
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) { _, _ = io.WriteString(w, "ok\n") })
	return mux
}

func (s *Server) sync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "GET", http.StatusMethodNotAllowed)
		return
	}
	apiKey := r.Header.Get("X-API-Key")
	if apiKey == "" {
		http.Error(w, `{"error":"missing API key"}`, http.StatusUnauthorized)
		return
	}
	s.mu.Lock()
	s.syncs++
	s.mu.Unlock()
	m := Monitor(apiKey)
	w.Header().Set("ETag", s.etags[m])
	if r.Header.Get("If-None-Match") == s.etags[m] {
		w.WriteHeader(http.StatusNotModified)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(s.bodies[m])
}

type ingestEvent struct {
	Status    string   `json:"status"`
	LatencyMs *float64 `json:"latency_ms"`
}

func (s *Server) ingest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	apiKey := r.Header.Get("X-API-Key")
	if apiKey == "" {
		http.Error(w, `{"error":"missing API key"}`, http.StatusUnauthorized)
		return
	}
	raw, err := io.ReadAll(io.LimitReader(r.Body, 64<<20))
	if err != nil {
		http.Error(w, "read", http.StatusBadRequest)
		return
	}
	plain := raw
	if strings.EqualFold(r.Header.Get("Content-Encoding"), "gzip") {
		zr, err := gzip.NewReader(strings.NewReader(string(raw)))
		if err == nil {
			plain, err = io.ReadAll(io.LimitReader(zr, 256<<20))
		}
		if err != nil {
			s.bad()
			http.Error(w, `{"error":"bad gzip"}`, http.StatusBadRequest)
			return
		}
	}
	var body struct {
		Events []ingestEvent `json:"events"`
	}
	if err := json.Unmarshal(plain, &body); err != nil {
		s.bad()
		http.Error(w, `{"error":"bad json"}`, http.StatusBadRequest)
		return
	}
	s.mu.Lock()
	s.requests++
	s.bytesWire += int64(len(raw))
	s.bytesPlain += int64(len(plain))
	for _, e := range body.Events {
		k := key{apiKey: apiKey, status: e.Status}
		s.events[k]++
		if e.LatencyMs != nil {
			h, ok := s.hists[k]
			if !ok {
				h = hist.New()
				s.hists[k] = h
			}
			hist.Record(h, time.Duration(*e.LatencyMs*float64(time.Millisecond)))
		}
	}
	if len(body.Events) > 0 {
		s.lastEvent = time.Now()
	}
	s.mu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_, _ = fmt.Fprintf(w, `{"accepted":%d}`, len(body.Events))
}

func (s *Server) bad() {
	s.mu.Lock()
	s.badBodies++
	s.mu.Unlock()
}

// Stats is what GET /stats returns.
type Stats struct {
	Since      time.Time                          `json:"since"`
	LastEvent  *time.Time                         `json:"last_event,omitempty"`
	Requests   int64                              `json:"requests"`
	Syncs      int64                              `json:"syncs"`
	BytesWire  int64                              `json:"bytes_wire"`
	BytesPlain int64                              `json:"bytes_plain"`
	BadBodies  int64                              `json:"bad_bodies"`
	Events     map[string]map[string]int64        `json:"events"`       // api key -> status -> count
	LatencyMs  map[string]map[string]hist.Summary `json:"eval_latency"` // api key -> status -> latency_ms percentiles
}

// Snapshot returns the current counters.
func (s *Server) Snapshot() Stats {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := Stats{Since: s.since, Requests: s.requests, Syncs: s.syncs, BytesWire: s.bytesWire, BytesPlain: s.bytesPlain,
		BadBodies: s.badBodies, Events: map[string]map[string]int64{}, LatencyMs: map[string]map[string]hist.Summary{}}
	if !s.lastEvent.IsZero() {
		t := s.lastEvent
		st.LastEvent = &t
	}
	keys := make([]key, 0, len(s.events))
	for k := range s.events {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		return keys[i].apiKey+keys[i].status < keys[j].apiKey+keys[j].status
	})
	for _, k := range keys {
		if st.Events[k.apiKey] == nil {
			st.Events[k.apiKey] = map[string]int64{}
			st.LatencyMs[k.apiKey] = map[string]hist.Summary{}
		}
		st.Events[k.apiKey][k.status] = s.events[k]
		if h, ok := s.hists[k]; ok {
			st.LatencyMs[k.apiKey][k.status] = hist.Summarise(h, true)
		}
	}
	return st
}

func (s *Server) stats(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(s.Snapshot())
}
