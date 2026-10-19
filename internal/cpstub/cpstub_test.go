// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package cpstub

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"net/http"
	"net/http/httptest"
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
