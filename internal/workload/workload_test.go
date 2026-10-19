// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package workload

import (
	"math/rand"
	"strings"
	"testing"
)

func TestEveryWorkloadBuildsForBothEngines(t *testing.T) {
	p := DefaultParams()
	for _, name := range []string{"orm", "orm-oltp", "masked", "select-only", "sysbench-ro", "batch1", "batch2000",
		"inlist10000", "blocked-delete", "blocked-update", "delete-where", "update-where", "payload-10k", "payload-1m-masked", "connect"} {
		ops, err := Get(name, p)
		if err != nil || len(ops) == 0 {
			t.Fatalf("%s: %v", name, err)
		}
		r := rand.New(rand.NewSource(1))
		for _, e := range []string{"pg", "mysql"} {
			for i := range ops {
				op := &ops[i]
				if op.Txn {
					q, a := op.TxnSQL(e), op.TxnArgs(r)
					if len(q) != len(a) {
						t.Fatalf("%s/%s: %d statements, %d argument sets", name, op.Name, len(q), len(a))
					}
					continue
				}
				sql := op.SQL(e)
				var n int
				if op.Args != nil {
					n = len(op.Args(r))
				}
				if e == "mysql" && strings.Count(sql, "?") != n {
					t.Fatalf("%s/%s: %d placeholders, %d arguments", name, op.Name, strings.Count(sql, "?"), n)
				}
			}
		}
	}
	for _, bad := range []string{"nope", "batch0", "batch99999", "payload-2m", "payload-10k-plain"} {
		if _, err := Get(bad, p); err == nil {
			t.Fatalf("%s must be refused", bad)
		}
	}
}

func TestOrmOltpDropsOnlyTheAnalyticalClasses(t *testing.T) {
	all, _ := Get("orm", DefaultParams())
	oltp, _ := Get("orm-oltp", DefaultParams())
	if len(all)-len(oltp) != 2 {
		t.Fatalf("orm %d classes, orm-oltp %d", len(all), len(oltp))
	}
}

func TestPickerFollowsWeights(t *testing.T) {
	p := NewPicker(Mix())
	r := rand.New(rand.NewSource(7))
	n := map[string]int{}
	for i := 0; i < 100_000; i++ {
		n[p.Pick(r).Name]++
	}
	// pk_lookup has weight 30 of 97.
	if f := float64(n["pk_lookup"]) / 100_000; f < 0.29 || f > 0.33 {
		t.Fatalf("pk_lookup drawn %.3f, want about 0.309", f)
	}
	if n["blocked_update"] == 0 {
		t.Fatal("a weight-1 class was never drawn")
	}
}

func TestStatementsPerExecution(t *testing.T) {
	ro := SysbenchRO(DefaultParams())[0]
	if ro.Statements() != 16 { // BEGIN + 10 point selects + 4 ranges + COMMIT
		t.Fatalf("sysbench_ro: %d statements", ro.Statements())
	}
	if (&Mix()[0]).Statements() != 1 {
		t.Fatal("pk_lookup is one statement")
	}
}

func TestSeedsExistForEveryDataset(t *testing.T) {
	for _, d := range Datasets() {
		for _, e := range []string{"pg", "mysql"} {
			q, err := SeedSQL(d, e, DefaultParams())
			if d == "pgbench" && e == "mysql" {
				if err == nil {
					t.Fatal("pgbench on mysql must be refused")
				}
				continue
			}
			if err != nil || len(q) == 0 || ChecksumSQL(d, e) == "" {
				t.Fatalf("%s/%s: %v", d, e, err)
			}
		}
	}
}
