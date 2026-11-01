// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package cpstub

import (
	"bytes"
	"compress/gzip"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func stub(t *testing.T) (*Server, *httptest.Server) {
	t.Helper()
	s, err := New(Config{Rules: RulesExport{EngineVersion: "4.3.0", RulesetVersion: "r1",
		Rules: []Rule{{RuleID: "VERICTO-001", Code: "VERICTO-001", Severity: "critical", DefaultAction: "block", RuleType: "standard"}}},
		SensitiveColumns: []SensitiveColumn{{Table: "payload_m", Column: "email", Policy: "mask", MaskStyle: "email"}}})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(s.Handler())
	t.Cleanup(ts.Close)
	return s, ts
}

func get(t *testing.T, url, apiKey, etag string) (*http.Response, map[string]any) {
	t.Helper()
	req, _ := http.NewRequest(http.MethodGet, url, nil)
	if apiKey != "" {
		req.Header.Set("X-API-Key", apiKey)
	}
	if etag != "" {
		req.Header.Set("If-None-Match", etag)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer res.Body.Close()
	var body map[string]any
	_ = json.NewDecoder(res.Body).Decode(&body)
	return res, body
}

func TestNoRulesIsRefused(t *testing.T) {
	if _, err := New(Config{}); err == nil {
		t.Fatal("a stub without rules must not start")
	}
}

func TestSyncServesModeByKeyWithETag(t *testing.T) {
	_, ts := stub(t)
	res, body := get(t, ts.URL+"/api/v1/sync/rules?database_id=bench-pg", "enforce-pg", "")
	if res.StatusCode != 200 {
		t.Fatalf("status %d", res.StatusCode)
	}
	pol := body["policy"].(map[string]any)
	if pol["monitor_mode"] != false || len(body["rules"].([]any)) != 1 || len(body["sensitive_columns"].([]any)) != 1 {
		t.Fatalf("body %v", body)
	}
	etag := res.Header.Get("ETag")
	if res, _ := get(t, ts.URL+"/api/v1/sync/rules", "enforce-pg", etag); res.StatusCode != http.StatusNotModified {
		t.Fatalf("same ETag: status %d", res.StatusCode)
	}
	res, body = get(t, ts.URL+"/api/v1/sync/rules", "observe-pg", "")
	if body["policy"].(map[string]any)["monitor_mode"] != true || res.Header.Get("ETag") == etag {
		t.Fatalf("observe key: %v", body["policy"])
	}
	if res, _ := get(t, ts.URL+"/api/v1/sync/rules", "", ""); res.StatusCode != http.StatusUnauthorized {
		t.Fatalf("no key: status %d", res.StatusCode)
	}
}

func post(t *testing.T, url, apiKey string, body []byte, gz bool) int {
	t.Helper()
	if gz {
		var b bytes.Buffer
		w := gzip.NewWriter(&b)
		_, _ = w.Write(body)
		_ = w.Close()
		body = b.Bytes()
	}
	req, _ := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	req.Header.Set("X-API-Key", apiKey)
	if gz {
		req.Header.Set("Content-Encoding", "gzip")
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	res.Body.Close()
	return res.StatusCode
}

func TestIngestRecordsLatencyPerVerdict(t *testing.T) {
	s, ts := stub(t)
	body := []byte(`{"events":[{"status":"ALLOWED","latency_ms":0.12},{"status":"ALLOWED","latency_ms":0.30},{"status":"BLOCKED","latency_ms":0.05},{"status":"FLAGGED"}]}`)
	if c := post(t, ts.URL+"/api/v1/ingest/events", "enforce-pg", body, true); c != http.StatusAccepted {
		t.Fatalf("status %d", c)
	}
	if c := post(t, ts.URL+"/api/v1/ingest/events", "enforce-pg", []byte("not json"), false); c != http.StatusBadRequest {
		t.Fatalf("bad body: status %d", c)
	}
	st := s.Snapshot()
	ev := st.Events["enforce-pg"]
	if ev["ALLOWED"] != 2 || ev["BLOCKED"] != 1 || ev["FLAGGED"] != 1 || st.Requests != 1 || st.BadBodies != 1 {
		t.Fatalf("stats %+v", st)
	}
	if p := st.LatencyMs["enforce-pg"]["ALLOWED"].Max; p < 0.29 || p > 0.31 {
		t.Fatalf("max %.3f ms, want 0.30", p)
	}
	if st.BytesPlain != int64(len(body)) || st.BytesWire >= st.BytesPlain+40 {
		t.Fatalf("bytes wire %d plain %d", st.BytesWire, st.BytesPlain)
	}
	s.reset()
	if st := s.Snapshot(); st.Requests != 0 || len(st.Events) != 0 {
		t.Fatalf("after reset %+v", st)
	}
}

func TestSignedBundlesVerifyAndPoliciesGoOnlyToCel(t *testing.T) {
	s, err := New(Config{Rules: RulesExport{RulesetVersion: "r1",
		Rules: []Rule{{RuleID: "VERICTO-001", Code: "VERICTO-001", Severity: "critical", DefaultAction: "block", RuleType: "standard"}}},
		Sign: true, PolicyRules: []Rule{{RuleID: "p1", Code: "POL-1", Severity: "high", DefaultAction: "block", RuleType: "custom"}},
		Principals: json.RawMessage(`{"version":"p1","entries":[]}`)})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(s.Handler())
	t.Cleanup(ts.Close)
	keys, err := s.SigningKeysJSON()
	if err != nil || keys == "" {
		t.Fatalf("keys %q %v", keys, err)
	}
	var ring []map[string]string
	if err := json.Unmarshal([]byte(keys), &ring); err != nil || len(ring) != 1 || ring[0]["key_id"] != "bench-ephemeral" {
		t.Fatalf("keyring %s", keys)
	}
	block, _ := pem.Decode([]byte(ring[0]["public_key"]))
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		t.Fatal(err)
	}
	for _, cel := range []bool{false, true} {
		req, _ := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/sync/rules", nil)
		req.Header.Set("X-API-Key", "enforce-pg")
		if cel {
			req.Header.Set(PolicyLanguageHeader, "cel/1, rewrite_limit")
		}
		res, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(res.Body)
		res.Body.Close()
		header := res.Header.Get(SignatureHeader)
		parts := map[string]string{}
		for _, p := range strings.Split(header, ";") {
			k, v, _ := strings.Cut(strings.TrimSpace(p), "=")
			parts[k] = v
		}
		digest := sha256.Sum256(append([]byte(bundleDomain), body...))
		sig, _ := base64.StdEncoding.DecodeString(parts["sig"])
		if parts["scheme"] != "ed25519-sha256" || parts["sha256"] != hex.EncodeToString(digest[:]) ||
			!ed25519.Verify(pub.(ed25519.PublicKey), digest[:], sig) {
			t.Fatalf("cel=%v: signature %q does not verify", cel, header)
		}
		var b map[string]any
		_ = json.Unmarshal(body, &b)
		_, hasPrincipals := b["principals"]
		if n := len(b["rules"].([]any)); (cel && (n != 2 || !hasPrincipals)) || (!cel && (n != 1 || hasPrincipals)) {
			t.Fatalf("cel=%v: %d rules, principals %v", cel, n, hasPrincipals)
		}
	}
	res, err := http.Get(ts.URL + "/signing-keys")
	if err != nil || res.StatusCode != 200 {
		t.Fatalf("GET /signing-keys: %v %v", res, err)
	}
}

// One stub, two bundles: an API key ending in -alt gets AltPolicyRules
// instead of PolicyRules (cel/1 only), signed with the same key, under
// distinct ETags; without cel/1 or without an alt set the key changes nothing.
func TestAltKeySelectsTheAlternativePolicySet(t *testing.T) {
	base := []Rule{{RuleID: "VERICTO-001", Code: "VERICTO-001", Severity: "critical", DefaultAction: "block", RuleType: "standard"}}
	s, err := New(Config{Rules: RulesExport{RulesetVersion: "r1", Rules: base}, Sign: true,
		PolicyRules:    []Rule{{RuleID: "p-time", Code: "POL-TIME", Severity: "high", DefaultAction: "block", RuleType: "custom"}},
		AltPolicyRules: []Rule{{RuleID: "p-free", Code: "POL-FREE", Severity: "high", DefaultAction: "block", RuleType: "custom"}},
		Principals:     json.RawMessage(`{"version":"p1","entries":[]}`)})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(s.Handler())
	t.Cleanup(ts.Close)
	keys, _ := s.SigningKeysJSON()
	var ring []map[string]string
	_ = json.Unmarshal([]byte(keys), &ring)
	block, _ := pem.Decode([]byte(ring[0]["public_key"]))
	pub, _ := x509.ParsePKIXPublicKey(block.Bytes)
	get := func(key string, cel bool) (codes []string, version, etag string) {
		req, _ := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/sync/rules", nil)
		req.Header.Set("X-API-Key", key)
		if cel {
			req.Header.Set(PolicyLanguageHeader, "cel/1, rewrite_limit")
		}
		res, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(res.Body)
		res.Body.Close()
		parts := map[string]string{}
		for _, p := range strings.Split(res.Header.Get(SignatureHeader), ";") {
			k, v, _ := strings.Cut(strings.TrimSpace(p), "=")
			parts[k] = v
		}
		digest := sha256.Sum256(append([]byte(bundleDomain), body...))
		sig, _ := base64.StdEncoding.DecodeString(parts["sig"])
		if !ed25519.Verify(pub.(ed25519.PublicKey), digest[:], sig) {
			t.Fatalf("%s cel=%v: signature does not verify", key, cel)
		}
		var b struct {
			Version string `json:"version"`
			Rules   []Rule `json:"rules"`
			Policy  struct {
				Monitor bool `json:"monitor_mode"`
			} `json:"policy"`
		}
		_ = json.Unmarshal(body, &b)
		for _, r := range b.Rules {
			codes = append(codes, r.Code)
		}
		return codes, b.Version, res.Header.Get("ETag")
	}
	c1, v1, e1 := get("enforce-pg", true)
	c2, v2, e2 := get("enforce-pg-alt", true)
	c3, _, _ := get("enforce-pg-alt", false)
	if strings.Join(c1, ",") != "VERICTO-001,POL-TIME" || v1 != "r1+policies" {
		t.Fatalf("default key: %v %s", c1, v1)
	}
	if strings.Join(c2, ",") != "VERICTO-001,POL-FREE" || v2 != "r1+policies-alt" || e1 == e2 {
		t.Fatalf("alt key: %v %s (etags %s %s)", c2, v2, e1, e2)
	}
	if strings.Join(c3, ",") != "VERICTO-001" {
		t.Fatalf("alt key without cel/1: %v", c3)
	}
	if !Alt("enforce-pg-alt") || Alt("enforce-pg") || Monitor("enforce-pg-alt") {
		t.Fatal("key classification")
	}
	// No alt set: an -alt key gets the default policies.
	s2, _ := New(Config{Rules: RulesExport{RulesetVersion: "r1", Rules: base},
		PolicyRules: []Rule{{RuleID: "p-time", Code: "POL-TIME", Severity: "high", DefaultAction: "block", RuleType: "custom"}}})
	ts2 := httptest.NewServer(s2.Handler())
	t.Cleanup(ts2.Close)
	req, _ := http.NewRequest(http.MethodGet, ts2.URL+"/api/v1/sync/rules", nil)
	req.Header.Set("X-API-Key", "enforce-pg-alt")
	req.Header.Set(PolicyLanguageHeader, "cel/1")
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(res.Body)
	res.Body.Close()
	if !strings.Contains(string(body), "POL-TIME") {
		t.Fatalf("no alt set: %s", body)
	}
}

func TestSanKeySelectsSanitizedTelemetry(t *testing.T) {
	base := []Rule{{RuleID: "VERICTO-001", Code: "VERICTO-001", Severity: "critical", DefaultAction: "block", RuleType: "standard"}}
	s, err := New(Config{Rules: RulesExport{RulesetVersion: "r1", Rules: base}, Sign: true,
		PolicyRules:    []Rule{{RuleID: "p-time", Code: "POL-TIME", Severity: "high", DefaultAction: "block", RuleType: "custom"}},
		AltPolicyRules: []Rule{{RuleID: "p-free", Code: "POL-FREE", Severity: "high", DefaultAction: "block", RuleType: "custom"}}})
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewServer(s.Handler())
	t.Cleanup(ts.Close)
	mode := func(key string, cel bool) (string, bool, int, string) {
		req, _ := http.NewRequest(http.MethodGet, ts.URL+"/api/v1/sync/rules", nil)
		req.Header.Set("X-API-Key", key)
		if cel {
			req.Header.Set(PolicyLanguageHeader, "cel/1")
		}
		res, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer res.Body.Close()
		var b struct {
			Version string `json:"version"`
			Rules   []Rule `json:"rules"`
			Policy  struct {
				Monitor bool   `json:"monitor_mode"`
				Mode    string `json:"telemetry_query_mode"`
			} `json:"policy"`
		}
		if err := json.NewDecoder(res.Body).Decode(&b); err != nil {
			t.Fatal(err)
		}
		return b.Policy.Mode, b.Policy.Monitor, len(b.Rules), b.Version
	}
	for _, c := range []struct {
		key   string
		cel   bool
		want  string
		mon   bool
		rules int
		ver   string
	}{
		{"enforce-pg", false, "raw", false, 1, "r1"},
		{"enforce-pg-san", false, "sanitized", false, 1, "r1"},
		{"observe-mysql-san", false, "sanitized", true, 1, "r1"},
		{"enforce-pg-san", true, "sanitized", false, 2, "r1+policies"},
		{"enforce-pg-san-alt", true, "sanitized", false, 2, "r1+policies-alt"},
		{"enforce-pg-alt", true, "raw", false, 2, "r1+policies-alt"},
	} {
		m, mon, n, v := mode(c.key, c.cel)
		if m != c.want || mon != c.mon || n != c.rules || v != c.ver {
			t.Errorf("%s cel=%v: mode %q monitor %v rules %d version %q; want %q %v %d %q", c.key, c.cel, m, mon, n, v,
				c.want, c.mon, c.rules, c.ver)
		}
	}
}
