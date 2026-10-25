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
//
// Business policies (proxy VERICTO_POLICY_RULES on): with Config.Sign the stub
// holds an Ed25519 key generated in memory at start (never written, never a
// Vericto key) and signs every /sync/rules body as the control plane does
// (X-Vericto-Bundle-Signature, scheme ed25519-sha256 over
// "vericto-sync-bundle/1\n" + body). GET /signing-keys returns the public key
// as the proxy's VERICTO_BUNDLE_SIGNING_KEYS JSON. To a proxy that announces
// the policy language (X-Vericto-Policy-Language: cel/1...) the body also
// carries Config.PolicyRules after the built-in rules, and Config.Principals.
//
// A second policy set (Config.AltPolicyRules) goes instead to a proxy whose
// API key ends in AltKeySuffix ("-alt"), so one stub serves two bundles to the
// variants of one run (e.g. a time-dependent and a time-free policy): each
// variant picks its bundle with VERICTO_API_KEY. Both are signed with the same
// ephemeral key.
package cpstub

import (
	"compress/gzip"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
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
	// Sign: sign every /sync/rules body with an ephemeral Ed25519 key.
	Sign bool
	// KeyID: the signature's key-id (default "bench-ephemeral").
	KeyID string
	// PolicyRules: business policy rules (rule_type custom, the policy YAML in
	// ast_condition_yaml), sent only to a proxy that announces cel/1.
	PolicyRules []Rule
	// Principals: the principals section, with PolicyRules.
	Principals json.RawMessage
	// AltPolicyRules: the business policy rules sent, instead of PolicyRules,
	// to a proxy that announces cel/1 with an API key ending in AltKeySuffix.
	AltPolicyRules []Rule
}

// AltKeySuffix selects Config.AltPolicyRules (an API key such as "enforce-pg-alt").
const AltKeySuffix = "-alt"

// Alt reports whether an API key selects the alternative policy set.
func Alt(apiKey string) bool { return strings.HasSuffix(apiKey, AltKeySuffix) }

// PolicyLanguageHeader is the request header a proxy with business policies
// on announces its policy language in.
const PolicyLanguageHeader = "X-Vericto-Policy-Language"

// SignatureHeader carries the bundle signature.
const SignatureHeader = "X-Vericto-Bundle-Signature"

// bundleDomain prefixes the signed digest's input (as vericto-fmw).
const bundleDomain = "vericto-sync-bundle/1\n"

// variant of a /sync/rules body: monitor mode, whether the proxy speaks the
// policy language, and whether its API key selects the alternative policy set.
type variant struct{ monitor, cel, alt bool }

// DefaultSeverityActions is EnforcementPolicy::default() of vericto-engine.
func DefaultSeverityActions() map[string]string {
	return map[string]string{"critical": "block", "high": "block", "medium": "flag", "low": "monitor", "informational": "monitor"}
}

type key struct{ apiKey, status string }

// Server is the stub.
type Server struct {
	cfg        Config
	bodies     map[variant][]byte
	etags      map[variant]string
	signatures map[variant]string // header value, with Config.Sign
	publicKey  ed25519.PublicKey

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
	if cfg.KeyID == "" {
		cfg.KeyID = "bench-ephemeral"
	}
	s := &Server{cfg: cfg, bodies: map[variant][]byte{}, etags: map[variant]string{}, signatures: map[variant]string{}}
	var private ed25519.PrivateKey
	if cfg.Sign {
		public, priv, err := ed25519.GenerateKey(rand.Reader)
		if err != nil {
			return nil, err
		}
		s.publicKey, private = public, priv
	}
	for _, v := range []variant{{false, false, false}, {true, false, false}, {false, true, false}, {true, true, false},
		{false, true, true}, {true, true, true}} {
		if v.alt && len(cfg.AltPolicyRules) == 0 {
			continue
		}
		rules := cfg.Rules.Rules
		version := cfg.Rules.RulesetVersion
		if v.alt {
			rules = append(append([]Rule{}, rules...), cfg.AltPolicyRules...)
			version += "+policies-alt"
		} else if v.cel && len(cfg.PolicyRules) > 0 {
			rules = append(append([]Rule{}, rules...), cfg.PolicyRules...)
			version += "+policies"
		}
		body := map[string]any{
			"version": version,
			"rules":   rules,
			"policy": map[string]any{
				"severity_actions":     cfg.SeverityActions,
				"parse_error_action":   "allow_report",
				"monitor_mode":         v.monitor,
				"telemetry_query_mode": "raw",
			},
			"sensitive_columns": cfg.SensitiveColumns,
			"agent_access":      map[string]any{},
			"telemetry_quota":   "ok",
		}
		if v.cel && len(cfg.Principals) > 0 {
			body["principals"] = cfg.Principals
		}
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		sum := sha256.Sum256(b)
		s.bodies[v] = b
		s.etags[v] = `"` + hex.EncodeToString(sum[:8]) + `"`
		if cfg.Sign {
			digest := sha256.Sum256(append([]byte(bundleDomain), b...))
			sig := ed25519.Sign(private, digest[:])
			s.signatures[v] = fmt.Sprintf("scheme=ed25519-sha256; key-id=%s; sha256=%s; sig=%s",
				cfg.KeyID, hex.EncodeToString(digest[:]), base64.StdEncoding.EncodeToString(sig))
		}
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
	mux.HandleFunc("/signing-keys", s.signingKeys)
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
	v := variant{monitor: Monitor(apiKey), cel: strings.HasPrefix(r.Header.Get(PolicyLanguageHeader), "cel/1")}
	if v.cel && Alt(apiKey) && len(s.cfg.AltPolicyRules) > 0 {
		v.alt = true
	}
	w.Header().Set("ETag", s.etags[v])
	if r.Header.Get("If-None-Match") == s.etags[v] {
		w.WriteHeader(http.StatusNotModified)
		return
	}
	if sig, ok := s.signatures[v]; ok {
		w.Header().Set(SignatureHeader, sig)
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(s.bodies[v])
}

// SigningKeysJSON is the proxy's VERICTO_BUNDLE_SIGNING_KEYS for this stub's
// key; empty without Config.Sign.
func (s *Server) SigningKeysJSON() (string, error) {
	if s.publicKey == nil {
		return "", nil
	}
	der, err := x509.MarshalPKIXPublicKey(s.publicKey)
	if err != nil {
		return "", err
	}
	pemKey := string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: der}))
	b, err := json.Marshal([]map[string]string{{"key_id": s.cfg.KeyID, "public_key": pemKey}})
	return string(b), err
}

func (s *Server) signingKeys(w http.ResponseWriter, r *http.Request) {
	keys, err := s.SigningKeysJSON()
	if err != nil || keys == "" {
		http.Error(w, `{"error":"not signing"}`, http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = io.WriteString(w, keys)
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
