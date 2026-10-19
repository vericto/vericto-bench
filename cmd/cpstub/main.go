// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// cpstub: local stand-in for the Vericto control plane (see internal/cpstub).
//
//	cpstub -listen 127.0.0.1:9090 -rules rules.json [-sensitive sensitive.json]
//
// On Tier P it listens on loopback only: the proxy accepts an http:// API URL
// for a loopback host without any flag.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/vericto/vericto-bench/internal/cpstub"
)

func main() {
	listen := flag.String("listen", "127.0.0.1:9090", "address")
	rules := flag.String("rules", "", "rules export from engine-eval --export-rules (required)")
	sensitive := flag.String("sensitive", "", "JSON array of sensitive-column tags (optional)")
	flag.Parse()
	if *rules == "" {
		log.Fatal("cpstub: -rules is required")
	}
	var cfg cpstub.Config
	if err := readJSON(*rules, &cfg.Rules); err != nil {
		log.Fatalf("cpstub: %v", err)
	}
	if *sensitive != "" {
		if err := readJSON(*sensitive, &cfg.SensitiveColumns); err != nil {
			log.Fatalf("cpstub: %v", err)
		}
	}
	s, err := cpstub.New(cfg)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("cpstub: %d rules (engine %s, ruleset %s), %d sensitive columns, listening on %s",
		len(cfg.Rules.Rules), cfg.Rules.EngineVersion, cfg.Rules.RulesetVersion, len(cfg.SensitiveColumns), *listen)
	srv := &http.Server{Addr: *listen, Handler: s.Handler(), ReadHeaderTimeout: 10 * time.Second}
	log.Fatal(srv.ListenAndServe())
}

func readJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(b, v); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	return nil
}
