// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package workload defines the statements vbench sends. Legitimate SQL only:
// adversarial input belongs to the fuzz jobs, not to a latency benchmark.
//
// Every class declares the verdict the built-in ruleset (vericto-engine v4.3.0,
// 42 rules, default policy) is expected to give it. The pre-flight checks the
// declaration twice: offline with engine-eval over `vbench dump`, and against
// the running proxy with `vbench probe`. A disagreement stops the suite.
package workload

import (
	"fmt"
	"math/rand"
	"sort"
	"strconv"
	"strings"
)

// Verdict expected from the built-in ruleset with the default policy.
type Verdict string

// Verdicts.
const (
	Allow Verdict = "allow"
	Flag  Verdict = "flag"
	Block Verdict = "block"
)

// Op is one statement class. SQL is per engine ("pg" or "mysql"); Args draws
// fresh parameters for every execution. Simple marks statements an application
// sends as plain text, which go over the simple query protocol on PostgreSQL
// whatever the mode. Txn marks a BEGIN ... COMMIT unit whose latency is the
// whole transaction.
type Op struct {
	Name    string
	Weight  int
	Verdict Verdict
	Simple  bool
	Txn     bool
	SQL     func(engine string) string
	Args    func(r *rand.Rand) []any
	TxnSQL  func(engine string) []string
	TxnArgs func(r *rand.Rand) [][]any
	// TxnVerdicts: per statement of a transaction, when they differ from
	// Verdict (which is then the strongest of them).
	TxnVerdicts []Verdict
}

// PartVerdict is the expected verdict of statement i of the op.
func (o *Op) PartVerdict(i int) Verdict {
	if o.Txn && i < len(o.TxnVerdicts) {
		return o.TxnVerdicts[i]
	}
	return o.Verdict
}

// Statements per execution: a transaction counts BEGIN, its statements, COMMIT.
func (o *Op) Statements() int {
	if o.Txn {
		return 2 + len(o.TxnSQL("pg"))
	}
	return 1
}

// Params sizes the datasets the workloads read.
type Params struct {
	PgbenchScale     int // pgbench -i -s
	SysbenchTables   int // sysbench --tables
	SysbenchRows     int // sysbench --table-size
	SysbenchRange    int // sysbench --range_size (default 100)
	SysbenchPoints   int // sysbench --point_selects (default 10)
	PayloadRowsTotal int // rows in vbench.payload / payload_m
}

// DefaultParams are the Tier P dataset sizes (design §5).
func DefaultParams() Params {
	return Params{PgbenchScale: 100, SysbenchTables: 8, SysbenchRows: 1_000_000, SysbenchRange: 100, SysbenchPoints: 10, PayloadRowsTotal: 10_000}
}

// Picker draws ops by weight.
type Picker struct {
	ops   []Op
	cum   []int
	total int
}

// NewPicker returns a picker over ops.
func NewPicker(ops []Op) *Picker {
	p := &Picker{ops: ops}
	for _, o := range ops {
		p.total += o.Weight
		p.cum = append(p.cum, p.total)
	}
	return p
}

// Pick draws one op.
func (p *Picker) Pick(r *rand.Rand) *Op {
	if len(p.ops) == 1 {
		return &p.ops[0]
	}
	n := r.Intn(p.total)
	i := sort.SearchInts(p.cum, n+1)
	return &p.ops[i]
}

// Names lists every workload Get accepts (N stands for a number).
func Names() []string {
	return []string{"orm", "orm-oltp", "masked", "select-only", "sysbench-ro",
		"batchN", "inlistN", "blocked-delete", "blocked-update", "delete-where", "update-where",
		"payload-10k", "payload-100k", "payload-1m", "payload-10k-masked", "payload-100k-masked", "payload-1m-masked",
		"connect"}
}

// Get returns the ops of a workload.
func Get(name string, p Params) ([]Op, error) {
	switch name {
	case "orm", "mix":
		return Mix(), nil
	case "orm-oltp":
		var out []Op
		for _, o := range Mix() {
			if !strings.HasPrefix(o.Name, "analytic") {
				out = append(out, o)
			}
		}
		return out, nil
	case "masked":
		return Masked(), nil
	case "select-only":
		return SelectOnly(p), nil
	case "sysbench-ro":
		return SysbenchRO(p), nil
	case "blocked-delete", "blocked-update", "delete-where", "update-where":
		return Blocked(name), nil
	case "connect":
		return Mix()[:1], nil
	}
	for _, pre := range []string{"batch", "inlist"} {
		if strings.HasPrefix(name, pre) {
			n, err := strconv.Atoi(strings.TrimPrefix(name, pre))
			if err != nil || n < 1 || n > 20_000 {
				return nil, fmt.Errorf("workload %s: want %s1 to %s20000", name, pre, pre)
			}
			if pre == "batch" {
				return Batch(n), nil
			}
			return InList(n), nil
		}
	}
	if strings.HasPrefix(name, "payload-") {
		return Payload(name, p)
	}
	return nil, fmt.Errorf("unknown workload %q (known: %s)", name, strings.Join(Names(), ", "))
}

func ph(engine string, i int) string {
	if engine == "pg" {
		return fmt.Sprintf("$%d", i)
	}
	return "?"
}

func phList(engine string, from, n int) string {
	parts := make([]string, n)
	for i := 0; i < n; i++ {
		parts[i] = ph(engine, from+i)
	}
	return strings.Join(parts, ", ")
}
