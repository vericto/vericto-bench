// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseNft(t *testing.T) {
	b := []byte(`{"nftables":[{"metainfo":{"version":"1.0.9"}},{"counter":{"family":"inet","name":"p6432_in","table":"vbench","handle":3,"packets":10,"bytes":1234}},{"counter":{"family":"inet","name":"db5432_lo_out","table":"vbench","handle":4,"packets":1,"bytes":99}}]}`)
	c, err := parseNft(b)
	if err != nil || c["p6432_in"] != 1234 || c["db5432_lo_out"] != 99 || len(c) != 2 {
		t.Fatalf("%v %v", c, err)
	}
}

func TestReadNetDevAndCPUStat(t *testing.T) {
	dir := t.TempDir()
	dev := "Inter-|   Receive                                                |  Transmit\n" +
		" face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n" +
		"    lo: 500 5 0 0 0 0 0 0 500 5 0 0 0 0 0 0\n" +
		"  ens5: 123456 100 0 0 0 0 0 0 654321 90 0 0 0 0 0 0\n"
	_ = os.WriteFile(filepath.Join(dir, "dev"), []byte(dev), 0o644)
	d, err := readNetDev(filepath.Join(dir, "dev"))
	if err != nil || d["ens5"] != [2]uint64{123456, 654321} || d["lo"][0] != 500 {
		t.Fatalf("%v %v", d, err)
	}
	_ = os.WriteFile(filepath.Join(dir, "cpu.stat"), []byte("usage_usec 1000\nuser_usec 600\nsystem_usec 400\nnr_periods 10\nnr_throttled 2\nthrottled_usec 5000\n"), 0o644)
	s, err := readCPUStat(filepath.Join(dir, "cpu.stat"))
	if err != nil || s.UsageUsec != 1000 || s.NrThrottled != 2 || s.ThrottledUsec != 5000 {
		t.Fatalf("%+v %v", s, err)
	}
}
