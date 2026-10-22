// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package workload

import (
	"fmt"
	"math/rand"
	"strings"
)

// ORM dataset sizes (vbench schema): small enough to seed in seconds, large
// enough that lookups are index probes rather than cached constants.
const (
	nUsers      = 20000
	nProducts   = 2000
	nOrders     = 100000
	nOrderItems = 300000
	nCustomers  = 1000
	inListSize  = 20
)

func interval(engine string, days int) string {
	if engine == "pg" {
		return fmt.Sprintf("now() - interval '%d days'", days)
	}
	return fmt.Sprintf("NOW() - INTERVAL %d DAY", days)
}

func userID(r *rand.Rand) int64    { return int64(r.Intn(nUsers) + 1) }
func productID(r *rand.Rand) int64 { return int64(r.Intn(nProducts) + 1) }
func orderID(r *rand.Rand) int64   { return int64(r.Intn(nOrders) + 1) }

var eventKinds = []string{"login", "view", "click", "search", "checkout"}

func eventArgs(r *rand.Rand) []any {
	return []any{userID(r), eventKinds[r.Intn(len(eventKinds))], fmt.Sprintf(`{"page":"/p/%d","ms":%d}`, r.Intn(500), r.Intn(900))}
}

// Mix is the W4 ORM mix: what an ORM-backed web application sends. Weights
// are per execution (a transaction is one execution of five statements).
// About 80% allowed, 17% flagged, 3% blocked (engine v4.3.0, 42 rules). Unchanged from Vericto's
// earlier (2026-10) Fargate measurements, for continuity.
func Mix() []Op {
	return []Op{
		{Name: "pk_lookup", Weight: 30, Verdict: Allow,
			SQL: func(e string) string {
				return "SELECT id, name, email, active, created_at FROM vbench.users WHERE id = " + ph(e, 1) + " LIMIT 1"
			},
			Args: func(r *rand.Rand) []any { return []any{userID(r)} }},
		// JPA find-by-id: no LIMIT, so VERICTO-050 flags it. Kept on purpose: it is
		// what real ORMs send and it exercises the flag path end to end.
		{Name: "pk_lookup_nolimit", Weight: 8, Verdict: Flag,
			SQL: func(e string) string {
				return "SELECT id, user_id, status, total, created_at FROM vbench.orders WHERE id = " + ph(e, 1)
			},
			Args: func(r *rand.Rand) []any { return []any{orderID(r)} }},
		{Name: "fk_list", Weight: 10, Verdict: Allow,
			SQL: func(e string) string {
				return "SELECT id, status, total, created_at FROM vbench.orders WHERE user_id = " + ph(e, 1) + " ORDER BY created_at DESC LIMIT 20"
			},
			Args: func(r *rand.Rand) []any { return []any{userID(r)} }},
		{Name: "join", Weight: 8, Verdict: Allow,
			SQL: func(e string) string {
				return "SELECT o.id, o.total, oi.product_id, oi.qty, p.name FROM vbench.orders o " +
					"JOIN vbench.order_items oi ON oi.order_id = o.id JOIN vbench.products p ON p.id = oi.product_id " +
					"WHERE o.user_id = " + ph(e, 1) + " ORDER BY o.id DESC LIMIT 50"
			},
			Args: func(r *rand.Rand) []any { return []any{userID(r)} }},
		{Name: "in_list", Weight: 6, Verdict: Allow,
			SQL: func(e string) string {
				return "SELECT id, name, price FROM vbench.products WHERE id IN (" + phList(e, 1, inListSize) + ") LIMIT 50"
			},
			Args: func(r *rand.Rand) []any {
				a := make([]any, inListSize)
				for i := range a {
					a[i] = productID(r)
				}
				return a
			}},
		{Name: "update_where", Weight: 10, Verdict: Allow,
			SQL: func(e string) string {
				if e == "pg" {
					return "UPDATE vbench.users SET last_seen = now() WHERE id = $1"
				}
				return "UPDATE vbench.users SET last_seen = NOW() WHERE id = ?"
			},
			Args: func(r *rand.Rand) []any { return []any{userID(r)} }},
		{Name: "insert", Weight: 10, Verdict: Allow,
			SQL: func(e string) string {
				return "INSERT INTO vbench.events (user_id, kind, payload) VALUES (" + phList(e, 1, 3) + ")"
			},
			Args: eventArgs},
		{Name: "txn", Weight: 6, Verdict: Flag, Txn: true, // the SELECT ... FOR UPDATE has no LIMIT: VERICTO-050
			TxnVerdicts: []Verdict{Flag, Allow, Allow},
			TxnSQL: func(e string) []string {
				return []string{
					"SELECT stock FROM vbench.products WHERE id = " + ph(e, 1) + " FOR UPDATE",
					"UPDATE vbench.products SET stock = stock - 1 WHERE id = " + ph(e, 1),
					"INSERT INTO vbench.orders (user_id, status, total) VALUES (" + phList(e, 1, 3) + ")",
				}
			},
			TxnArgs: func(r *rand.Rand) [][]any {
				p := productID(r)
				return [][]any{{p}, {p}, {userID(r), "pending", float64(r.Intn(50000)) / 100}}
			}},
		{Name: "analytic_groupby", Weight: 1, Verdict: Allow, Simple: true,
			SQL: func(e string) string {
				return "SELECT status, count(*) AS n, sum(total) AS revenue, avg(total) AS avg_total FROM vbench.orders " +
					"WHERE created_at >= " + interval(e, 7) + " GROUP BY status ORDER BY n DESC LIMIT 10"
			}},
		{Name: "analytic_window", Weight: 1, Verdict: Allow, Simple: true,
			SQL: func(e string) string {
				return "WITH r AS (SELECT user_id, sum(total) AS t, rank() OVER (ORDER BY sum(total) DESC) AS rk " +
					"FROM vbench.orders WHERE created_at >= " + interval(e, 30) + " GROUP BY user_id) " +
					"SELECT user_id, t FROM r WHERE rk <= 10 ORDER BY rk LIMIT 10"
			}},
		// A small lookup table read whole: legitimate, flagged by VERICTO-050/051.
		{Name: "flagged_select", Weight: 4, Verdict: Flag, Simple: true,
			SQL: func(e string) string { return "SELECT * FROM vbench.categories" }},
		// Mistakes a rule blocks. They target an always-empty table, so on the
		// direct path and in observe mode, where they really run, they change nothing.
		{Name: "blocked_delete", Weight: 2, Verdict: Block, Simple: true,
			SQL: func(e string) string { return "DELETE FROM vbench.scratch" }},
		{Name: "blocked_update", Weight: 1, Verdict: Block, Simple: true,
			SQL: func(e string) string { return "UPDATE vbench.scratch SET n = 0" }},
	}
}

// Masked is a PK lookup of a column the stub tags `mask` (vbench.customers_masked.email).
func Masked() []Op {
	return []Op{{Name: "masked_lookup", Weight: 1, Verdict: Flag, // VERICTO-085 flags and rewrites a masked column
		SQL: func(e string) string {
			return "SELECT id, name, email FROM vbench.customers_masked WHERE id = " + ph(e, 1) + " LIMIT 1"
		},
		Args: func(r *rand.Rand) []any { return []any{int64(r.Intn(nCustomers) + 1)} }}}
}

// SelectOnly is pgbench's built-in select-only script (`-S`): one PK lookup on
// pgbench_accounts. Used where pgbench itself cannot run (a Fargate client) and
// to cross-check pgbench; Tier P's W1 figures come from pgbench.
func SelectOnly(p Params) []Op {
	n := 100000 * p.PgbenchScale
	return []Op{{Name: "select_only", Weight: 1, Verdict: Flag, // no LIMIT: VERICTO-050 flags it, as on pgbench
		SQL: func(e string) string {
			return "SELECT abalance FROM pgbench_accounts WHERE aid = " + ph(e, 1)
		},
		Args: func(r *rand.Rand) []any { return []any{int64(r.Intn(n) + 1)} }}}
}

// SysbenchRO replays sysbench oltp_read_only (1.0.20) statement for statement:
// BEGIN, point_selects x `SELECT c FROM sbtestN WHERE id=?`, one simple range,
// one SUM range, one ORDER BY range, one DISTINCT range, COMMIT, on a random
// table. sysbench's own --rate latency excludes its queue time, so the MySQL
// latency curve uses this replay (open loop) and sysbench is kept for closed-loop
// throughput.
func SysbenchRO(p Params) []Op {
	tables, rows, rng, points := p.SysbenchTables, p.SysbenchRows, p.SysbenchRange, p.SysbenchPoints
	if rng <= 0 {
		rng = 100
	}
	if points <= 0 {
		points = 10
	}
	// One op per table, so the SQL text is fixed per op and prepared-statement
	// caching behaves as in sysbench (one statement set per table).
	ops := make([]Op, 0, tables)
	for t := 1; t <= tables; t++ {
		tbl := fmt.Sprintf("sbtest%d", t)
		ops = append(ops, Op{Name: "sysbench_ro", Weight: 1, Verdict: Flag, Txn: true,
			TxnSQL: func(e string) []string {
				q := make([]string, 0, points+4)
				for i := 0; i < points; i++ {
					q = append(q, "SELECT c FROM "+tbl+" WHERE id="+ph(e, 1))
				}
				between := " WHERE id BETWEEN " + ph(e, 1) + " AND " + ph(e, 2)
				q = append(q,
					"SELECT c FROM "+tbl+between,
					"SELECT SUM(k) FROM "+tbl+between,
					"SELECT c FROM "+tbl+between+" ORDER BY c",
					"SELECT DISTINCT c FROM "+tbl+between+" ORDER BY c")
				return q
			},
			TxnArgs: func(r *rand.Rand) [][]any {
				a := make([][]any, 0, points+4)
				for i := 0; i < points; i++ {
					a = append(a, []any{int64(r.Intn(rows) + 1)})
				}
				for i := 0; i < 4; i++ {
					lo := int64(r.Intn(rows-rng+1) + 1)
					a = append(a, []any{lo, lo + int64(rng) - 1})
				}
				return a
			}})
	}
	return ops
}

// Batch is the W5 size sweep: one multi-row INSERT of n rows with bound
// parameters, what an ORM's bulk create sends. It is the legitimate way a
// statement gets large.
func Batch(n int) []Op {
	return []Op{{Name: fmt.Sprintf("batch_insert_%d", n), Weight: 1, Verdict: Allow,
		SQL: func(e string) string {
			rows := make([]string, n)
			for i := 0; i < n; i++ {
				rows[i] = "(" + phList(e, 3*i+1, 3) + ")"
			}
			return "INSERT INTO vbench.events (user_id, kind, payload) VALUES " + strings.Join(rows, ", ")
		},
		Args: func(r *rand.Rand) []any {
			a := make([]any, 0, 3*n)
			for i := 0; i < n; i++ {
				a = append(a, eventArgs(r)...)
			}
			return a
		}}}
}

// InList is the second W5 shape: a SELECT with an IN list of n bound ids.
func InList(n int) []Op {
	return []Op{{Name: fmt.Sprintf("in_list_%d", n), Weight: 1, Verdict: Allow,
		SQL: func(e string) string {
			return "SELECT id, name FROM vbench.users WHERE id IN (" + phList(e, 1, n) + ") LIMIT 50"
		},
		Args: func(r *rand.Rand) []any {
			a := make([]any, n)
			for i := range a {
				a[i] = userID(r)
			}
			return a
		}}}
}

// Blocked is W6: a DELETE / UPDATE without WHERE on the always-empty scratch
// table (blocked by VERICTO-001 / VERICTO-030), and the same statements with a
// WHERE (allowed), all over the extended protocol / text mode.
func Blocked(name string) []Op {
	switch name {
	case "blocked-delete":
		return []Op{{Name: "blocked_delete", Weight: 1, Verdict: Block,
			SQL: func(e string) string { return "DELETE FROM vbench.scratch" }}}
	case "blocked-update":
		return []Op{{Name: "blocked_update", Weight: 1, Verdict: Block,
			SQL: func(e string) string { return "UPDATE vbench.scratch SET n = 0" }}}
	case "delete-where":
		return []Op{{Name: "delete_where", Weight: 1, Verdict: Allow,
			SQL:  func(e string) string { return "DELETE FROM vbench.scratch WHERE id = " + ph(e, 1) },
			Args: func(r *rand.Rand) []any { return []any{int64(r.Intn(1000) + 1)} }}}
	default:
		return []Op{{Name: "update_where_scratch", Weight: 1, Verdict: Allow,
			SQL:  func(e string) string { return "UPDATE vbench.scratch SET n = 0 WHERE id = " + ph(e, 1) },
			Args: func(r *rand.Rand) []any { return []any{int64(r.Intn(1000) + 1)} }}}
	}
}

// PayloadRowBytes is the approximate size of one vbench.payload row in a result
// (id + 24-byte email + 1,000-byte payload + framing).
const PayloadRowBytes = 1040

// Payload is W8: a PK range SELECT returning about 10 KB, 100 KB or 1 MB, from
// vbench.payload (no tag) or vbench.payload_m (its `email` column tagged `mask`
// by the stub). Only the small email column is masked, so plain and masked
// results are the same size and the difference is the proxy's masking work.
func Payload(name string, p Params) ([]Op, error) {
	rows := map[string]int{"10k": 10, "100k": 100, "1m": 1000}
	parts := strings.Split(strings.TrimPrefix(name, "payload-"), "-")
	n, ok := rows[parts[0]]
	if !ok || len(parts) > 2 || (len(parts) == 2 && parts[1] != "masked") {
		return nil, fmt.Errorf("workload %s: want payload-10k|100k|1m[-masked]", name)
	}
	table := "vbench.payload"
	if len(parts) == 2 {
		table = "vbench.payload_m"
	}
	total := p.PayloadRowsTotal
	if total < n {
		return nil, fmt.Errorf("payload table has %d rows, %s needs %d", total, name, n)
	}
	verdict := Allow
	if len(parts) == 2 {
		verdict = Flag // VERICTO-085: flagged, and the projection rewritten to mask the column
	}
	return []Op{{Name: strings.ReplaceAll(name, "-", "_"), Weight: 1, Verdict: verdict,
		SQL: func(e string) string {
			return "SELECT id, email, payload FROM " + table + " WHERE id BETWEEN " + ph(e, 1) + " AND " + ph(e, 2) +
				fmt.Sprintf(" ORDER BY id LIMIT %d", n)
		},
		Args: func(r *rand.Rand) []any {
			lo := int64(r.Intn(total-n+1) + 1)
			return []any{lo, lo + int64(n) - 1}
		}}}, nil
}
