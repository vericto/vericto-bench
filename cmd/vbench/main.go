// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// vbench: open-loop (and closed-loop) SQL load generator for vericto-bench.
//
//	vbench run      -engine pg -host H -port P -workload orm -loop open -rate 2000 -out DIR
//	vbench seed     -engine pg -host H -port P -dataset orm|payload|pgbench|sysbench
//	vbench checksum -engine pg -host H -port P -dataset orm
//	vbench probe    -engine pg -host H -port P -workload orm -expect-enforce
//	vbench dump     -engine pg -workload orm,batch100
//	vbench drop     -engine pg -host H -port P
//	vbench scalar   -engine pg -host H -port P -sql "SELECT 1"
//	vbench certs    -out DIR -names host1,10.0.0.5
//
// Password: DB_PASSWORD in the environment. Exit codes: 0 ok (a saturated cell
// is a status, not an error), 2 usage, 3 setup failure (connect or
// authentication; never retried), 4 unexpected errors above -max-err, 5 a probe
// verdict disagrees with the workload's declaration, 9 stopped by the stop file
// (the network-cap guard).
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"

	hdr "github.com/HdrHistogram/hdrhistogram-go"

	"github.com/vericto/vericto-bench/internal/db"
	"github.com/vericto/vericto-bench/internal/hist"
	"github.com/vericto/vericto-bench/internal/openloop"
	"github.com/vericto/vericto-bench/internal/workload"
)

// Version is set at build time.
var Version = "dev"

type opts struct {
	engine, mode, workload, dataset, loop, arrival, connMode string
	label, target, out, stopFile, tls, ports, sqlText        string
	t                                                        db.Target
	rate, maxErr                                             float64
	conns, maxQueue                                          int
	warmup, duration, drain, interval                        time.Duration
	seed                                                     int64
	expectEnforce                                            bool
	p                                                        workload.Params
}

func fatal(stage string, err error) {
	fmt.Fprintf(os.Stderr, "vbench: %s: %v\n", stage, err)
	emit("VBENCH_FATAL", map[string]any{"fatal": stage, "error": trunc(err.Error(), 400)})
	os.Exit(3)
}

func usage(err error) {
	fmt.Fprintf(os.Stderr, "vbench: %v\n", err)
	os.Exit(2)
}

func trunc(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func emit(prefix string, v any) {
	b, _ := json.Marshal(v)
	fmt.Printf("%s %s\n", prefix, b)
}

func main() {
	if len(os.Args) < 2 {
		usage(errors.New("usage: vbench run|seed|checksum|scalar|probe|dump|drop|certs|version [flags]"))
	}
	cmd := os.Args[1]
	if cmd == "version" {
		fmt.Println(Version)
		return
	}
	if cmd == "certs" {
		cf := flag.NewFlagSet("certs", flag.ExitOnError)
		dir := cf.String("out", "certs", "directory")
		names := cf.String("names", "localhost,127.0.0.1", "comma-separated DNS names and IPs of the server certificate")
		_ = cf.Parse(os.Args[2:])
		if err := certs(*dir, *names); err != nil {
			fatal("certs", err)
		}
		return
	}
	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	var o opts
	o.p = workload.DefaultParams()
	fs.StringVar(&o.engine, "engine", "pg", "pg | mysql")
	fs.StringVar(&o.t.Host, "host", "127.0.0.1", "host")
	fs.IntVar(&o.t.Port, "port", 0, "port")
	fs.StringVar(&o.t.User, "user", "bench", "database user")
	fs.StringVar(&o.t.DB, "db", "bench", "database (pg: dbname; mysql: default schema, may be empty)")
	fs.StringVar(&o.tls, "tls", "require", "require | disable")
	fs.StringVar(&o.ports, "ports", "", "run: comma-separated PORT or HOST:PORT; connection i uses item i mod n (two proxy tasks)")
	fs.StringVar(&o.sqlText, "sql", "", "scalar: one statement returning one value")
	fs.StringVar(&o.label, "label", "", "free-form label copied to the result")
	fs.StringVar(&o.target, "target", "", "target name copied to the result (direct, haproxy-tcp, vericto-enforce, ...)")
	fs.StringVar(&o.mode, "mode", "", "pg: simple|extended|prepared ; mysql: text|prepare|prepared")
	fs.StringVar(&o.workload, "workload", "orm", "workload (dump: comma-separated list)")
	fs.StringVar(&o.dataset, "dataset", "orm", "seed/checksum: orm | payload | pgbench | sysbench")
	fs.StringVar(&o.loop, "loop", "open", "open | closed")
	fs.StringVar(&o.arrival, "arrival", "constant", "open loop: constant | poisson")
	fs.StringVar(&o.connMode, "conn", "pooled", "pooled | newconn (W7: connect, TLS, auth, one PK lookup per request)")
	fs.Float64Var(&o.rate, "rate", 0, "open loop: requests per second")
	fs.IntVar(&o.conns, "conns", 0, "connections (open loop: pool, default max(8, rate x 10 ms x 4); closed loop: concurrency)")
	fs.IntVar(&o.maxQueue, "max-queue", 0, "open loop: queue length that marks the cell saturated (default 10 x rate)")
	fs.DurationVar(&o.warmup, "warmup", 60*time.Second, "discarded warm-up")
	fs.DurationVar(&o.duration, "duration", 300*time.Second, "measured window")
	fs.DurationVar(&o.drain, "drain", 30*time.Second, "after the window, time allowed for in-flight requests")
	fs.DurationVar(&o.interval, "interval", 10*time.Second, "histogram interval length")
	fs.Float64Var(&o.maxErr, "max-err", 0.001, "unexpected-error ratio above which the cell is invalid (exit 4)")
	fs.Int64Var(&o.seed, "seed", 42, "PRNG seed (schedule and parameters)")
	fs.StringVar(&o.out, "out", "", "run: directory for result.json, latency.hlog, intervals.jsonl")
	fs.StringVar(&o.stopFile, "stop-file", "", "run: abort the cell (exit 9) when this file appears; its content is the reason")
	fs.BoolVar(&o.expectEnforce, "expect-enforce", false, "probe: the target enforces the built-in rules (blocked classes must be blocked)")
	fs.IntVar(&o.p.PgbenchScale, "pgbench-scale", o.p.PgbenchScale, "pgbench scale of the dataset")
	fs.IntVar(&o.p.SysbenchTables, "sysbench-tables", o.p.SysbenchTables, "sysbench --tables of the dataset")
	fs.IntVar(&o.p.SysbenchRows, "sysbench-rows", o.p.SysbenchRows, "sysbench --table-size of the dataset")
	fs.IntVar(&o.p.PayloadRowsTotal, "payload-rows", o.p.PayloadRowsTotal, "rows of vbench.payload")
	_ = fs.Parse(os.Args[2:])

	var err error
	if o.mode, err = db.NormaliseMode(o.engine, o.mode); err != nil {
		usage(err)
	}
	switch o.tls {
	case "require":
		o.t.TLS = true
	case "disable":
	default:
		usage(fmt.Errorf("-tls must be require or disable"))
	}
	o.t.Password = os.Getenv("DB_PASSWORD")

	if cmd == "dump" {
		dump(o)
		return
	}
	if o.t.Port == 0 {
		usage(errors.New("-port is required"))
	}
	if o.t.Password == "" {
		fatal("config", errors.New("DB_PASSWORD is not set"))
	}
	ctx := context.Background()
	switch cmd {
	case "seed", "drop", "checksum":
		seedLike(ctx, cmd, o)
	case "scalar":
		s, err := db.Connect(ctx, o.engine, o.t, "text")
		if err != nil {
			fatal("connect", err)
		}
		v, err := s.Scalar(ctx, o.sqlText)
		s.Close()
		if err != nil {
			fatal("scalar", err)
		}
		emit("VBENCH_SCALAR", map[string]any{"value": v})
	case "probe":
		probe(ctx, o)
	case "run":
		os.Exit(run(ctx, o))
	default:
		usage(fmt.Errorf("unknown command %q", cmd))
	}
}

func seedLike(ctx context.Context, cmd string, o opts) {
	s, err := db.Connect(ctx, o.engine, o.t, "text")
	if err != nil {
		fatal("connect", err)
	}
	defer s.Close()
	if cmd == "checksum" {
		q := workload.ChecksumSQL(o.dataset, o.engine)
		if q == "" {
			usage(fmt.Errorf("no checksum for dataset %s", o.dataset))
		}
		v, err := s.Scalar(ctx, q)
		if err != nil {
			fatal("checksum", err)
		}
		emit("VBENCH_CHECKSUM", map[string]any{"engine": o.engine, "dataset": o.dataset, "value": v})
		return
	}
	stmts := workload.DropSQL(o.engine)
	if cmd == "seed" {
		if stmts, err = workload.SeedSQL(o.dataset, o.engine, o.p); err != nil {
			usage(err)
		}
	}
	t0 := time.Now()
	for _, q := range stmts {
		if err := s.Exec(ctx, q); err != nil {
			fatal(cmd, fmt.Errorf("%s: %w", trunc(q, 80), err))
		}
	}
	emit("VBENCH_"+strings.ToUpper(cmd), map[string]any{"engine": o.engine, "dataset": o.dataset, "statements": len(stmts), "seconds": time.Since(t0).Seconds()})
}

// probe runs every class of the workload once and checks the target did what
// the declaration says: on an enforcing target, exactly the Block classes are
// blocked; anywhere else, nothing is.
func probe(ctx context.Context, o opts) {
	ops, err := workload.Get(o.workload, o.p)
	if err != nil {
		usage(err)
	}
	t0 := time.Now()
	s, err := db.Connect(ctx, o.engine, o.t, o.mode)
	if err != nil {
		fatal("connect", err)
	}
	connect := time.Since(t0)
	defer s.Close()
	r := rand.New(rand.NewSource(o.seed))
	type row struct {
		Class    string `json:"class"`
		Expected string `json:"expected"`
		Blocked  bool   `json:"blocked"`
		Error    string `json:"error,omitempty"`
		Agree    bool   `json:"agree"`
	}
	var rows []row
	agree := true
	seen := map[string]bool{}
	for i := range ops {
		op := &ops[i]
		if seen[op.Name] {
			continue
		}
		seen[op.Name] = true
		var args []any
		var targs [][]any
		if op.Txn {
			targs = op.TxnArgs(r)
		} else if op.Args != nil {
			args = op.Args(r)
		}
		err := db.ExecOp(ctx, s, op, o.engine, args, targs)
		x := row{Class: op.Name, Expected: string(op.Verdict), Blocked: db.IsBlocked(err)}
		if err != nil && !x.Blocked {
			x.Error = trunc(err.Error(), 300)
		}
		wantBlocked := o.expectEnforce && op.Verdict == workload.Block
		x.Agree = x.Blocked == wantBlocked && x.Error == ""
		agree = agree && x.Agree
		rows = append(rows, x)
	}
	out := map[string]any{"engine": o.engine, "target": o.target, "workload": o.workload, "mode": o.mode,
		"connect_ms": float64(connect.Microseconds()) / 1000, "expect_enforce": o.expectEnforce, "classes": rows, "agree": agree}
	vq := "SELECT version()"
	if o.engine == "mysql" {
		vq = "SELECT VERSION()"
	}
	if v, err := s.Scalar(ctx, vq); err == nil {
		out["server_version"] = v
	}
	emit("VBENCH_PROBE", out)
	if !agree {
		os.Exit(5)
	}
}

func dump(o opts) {
	r := rand.New(rand.NewSource(o.seed))
	enc := json.NewEncoder(os.Stdout)
	dialect := map[string]string{"pg": "postgres", "mysql": "mysql"}[o.engine]
	seen := map[string]bool{}
	for _, w := range strings.Split(o.workload, ",") {
		ops, err := workload.Get(strings.TrimSpace(w), o.p)
		if err != nil {
			usage(err)
		}
		for i := range ops {
			op := &ops[i]
			if seen[op.Name] {
				continue
			}
			seen[op.Name] = true
			var texts []string
			if op.Txn {
				args := op.TxnArgs(r)
				for j, q := range op.TxnSQL(o.engine) {
					texts = append(texts, render(o.engine, q, args[j], false, o.mode))
				}
			} else {
				var args []any
				if op.Args != nil {
					args = op.Args(r)
				}
				texts = []string{render(o.engine, op.SQL(o.engine), args, op.Simple, o.mode)}
			}
			for j, t := range texts {
				_ = enc.Encode(map[string]any{"workload": w, "class": op.Name, "part": j, "verdict": op.PartVerdict(j),
					"dialect": dialect, "bytes": len(t), "sql": t})
			}
		}
	}
}

// render returns the statement text the proxy sees: placeholders for the
// PostgreSQL extended protocol and MySQL prepared statements, literals for MySQL
// text mode (client-side interpolation).
func render(engine, q string, args []any, simple bool, mode string) string {
	if engine == "pg" || simple || len(args) == 0 || mode != "text" {
		return q
	}
	var b strings.Builder
	i := 0
	for _, ch := range q {
		if ch == '?' && i < len(args) {
			switch v := args[i].(type) {
			case string:
				b.WriteString("'" + strings.ReplaceAll(v, "'", "''") + "'")
			default:
				b.WriteString(fmt.Sprint(v))
			}
			i++
			continue
		}
		b.WriteRune(ch)
	}
	return b.String()
}

func watchStopFile(path string, stop chan<- struct{}, reason *string, done <-chan struct{}) {
	t := time.NewTicker(100 * time.Millisecond)
	defer t.Stop()
	for {
		select {
		case <-done:
			return
		case <-t.C:
			if b, err := os.ReadFile(path); err == nil {
				*reason = strings.TrimSpace(string(b))
				if *reason == "" {
					*reason = "stop file"
				}
				close(stop)
				return
			}
		}
	}
}

func run(ctx context.Context, o opts) int {
	ops, err := workload.Get(o.workload, o.p)
	if err != nil {
		usage(err)
	}
	closed := o.loop == "closed"
	if !closed && o.loop != "open" {
		usage(errors.New("-loop must be open or closed"))
	}
	if !closed && o.rate <= 0 {
		usage(errors.New("open loop needs -rate > 0"))
	}
	if o.arrival != "constant" && o.arrival != "poisson" {
		usage(errors.New("-arrival must be constant or poisson"))
	}
	if o.conns <= 0 {
		if closed {
			o.conns = 1
		} else {
			o.conns = int(o.rate * 0.010 * 4) // rate x 10 ms x 4: never the limit below the knee
			if o.conns < 8 {
				o.conns = 8
			}
		}
	}
	if o.out != "" {
		if err := os.MkdirAll(o.out, 0o755); err != nil {
			fatal("out", err)
		}
	}
	stop := make(chan struct{})
	var stopReason string
	doneWatch := make(chan struct{})
	defer close(doneWatch)
	if o.stopFile != "" {
		if _, err := os.Stat(o.stopFile); err == nil {
			fatal("stop-file", fmt.Errorf("%s exists before the cell started", o.stopFile))
		}
		go watchStopFile(o.stopFile, stop, &stopReason, doneWatch)
	}

	picker := workload.NewPicker(ops)
	var exec openloop.Exec
	var sessions []db.Session
	connFailed := make(chan error, 1)
	if o.connMode == "pooled" {
		// Open every connection before the clock starts, serially; one failure
		// stops the cell before any load, with no retry.
		// -ports: PORT or HOST:PORT items; connection i uses item i mod n.
		type addr struct {
			host string
			port int
		}
		var addrs []addr
		for _, item := range strings.Split(o.ports, ",") {
			item = strings.TrimSpace(item)
			h, p := o.t.Host, item
			if i := strings.LastIndex(item, ":"); i >= 0 {
				h, p = item[:i], item[i+1:]
			}
			if n, err := strconv.Atoi(p); err == nil && n > 0 {
				addrs = append(addrs, addr{h, n})
			}
		}
		for i := 0; i < o.conns; i++ {
			t := o.t
			if len(addrs) > 0 {
				t.Host, t.Port = addrs[i%len(addrs)].host, addrs[i%len(addrs)].port
			}
			s, err := db.Connect(ctx, o.engine, t, o.mode)
			if err != nil {
				for _, x := range sessions {
					x.Close()
				}
				fatal("connect", err)
			}
			sessions = append(sessions, s)
		}
		defer func() {
			for _, s := range sessions {
				s.Close()
			}
		}()
		exec = func(ctx context.Context, conn int, r *rand.Rand) openloop.Outcome {
			op := picker.Pick(r)
			var args []any
			var targs [][]any
			if op.Txn {
				targs = op.TxnArgs(r)
			} else if op.Args != nil {
				args = op.Args(r)
			}
			err := db.ExecOp(ctx, sessions[conn], op, o.engine, args, targs)
			out := openloop.Outcome{Class: op.Name, Statements: op.Statements()}
			if db.IsBlocked(err) {
				out.Blocked = true
			} else {
				out.Err = err
			}
			return out
		}
	} else if o.connMode == "newconn" {
		op := &ops[0]
		exec = func(ctx context.Context, conn int, r *rand.Rand) openloop.Outcome {
			s, err := db.Connect(ctx, o.engine, o.t, o.mode)
			if err != nil {
				select { // never retry a failed login: stop the cell
				case connFailed <- err:
				default:
				}
				return openloop.Outcome{Class: "connect", Err: err}
			}
			defer s.Close()
			err = db.ExecOp(ctx, s, op, o.engine, op.Args(r), nil)
			return openloop.Outcome{Class: "connect_plus_pk", Statements: 1, Err: err}
		}
	} else {
		usage(errors.New("-conn must be pooled or newconn"))
	}
	// The stop file, SIGTERM/SIGINT (the runner or a task stop) and a failed
	// login in newconn mode all stop the cell; what was not sent is counted.
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(sigs)
	stopMerged := make(chan struct{})
	go func() {
		select {
		case <-stop:
		case s := <-sigs:
			stopReason = "signal " + s.String()
		case err := <-connFailed:
			stopReason = "connection failure: " + trunc(err.Error(), 200)
		case <-doneWatch:
			return
		}
		close(stopMerged)
	}()

	var ru0 syscall.Rusage
	_ = syscall.Getrusage(syscall.RUSAGE_SELF, &ru0)
	cfg := openloop.Config{Closed: closed, Rate: o.rate, Poisson: o.arrival == "poisson", Seed: o.seed,
		Conns: o.conns, Warmup: o.warmup, Duration: o.duration, MaxQueue: o.maxQueue, Drain: o.drain,
		Interval: o.interval, Stop: stopMerged, BlockedInHeadline: allBlocked(ops)}
	r := openloop.Run(ctx, cfg, exec)
	var ru1 syscall.Rusage
	_ = syscall.Getrusage(syscall.RUSAGE_SELF, &ru1)
	if r.Status == openloop.StatusAborted {
		r.Reason = stopReason
	}

	cpu := func(t syscall.Timeval) float64 { return float64(t.Sec) + float64(t.Usec)/1e6 }
	wall := time.Since(r.Start).Seconds()
	res := map[string]any{
		"tool": "vbench", "version": Version, "label": o.label, "target": o.target,
		"engine": o.engine, "mode": o.mode, "workload": o.workload, "conn_mode": o.connMode, "tls": o.t.TLS,
		"loop": r.Loop, "arrival": o.arrival, "conns": o.conns, "seed": o.seed,
		"warmup_s": o.warmup.Seconds(), "duration_s": o.duration.Seconds(), "interval_s": o.interval.Seconds(),
		"status": r.Status, "reason": r.Reason,
		"offered_rate": r.Offered, "achieved_rate": r.Achieved, "statements_per_s": r.Statements,
		"start": r.Start.UTC().Format(time.RFC3339Nano), "measure_from": r.MeasureFrom.UTC().Format(time.RFC3339Nano),
		"end":             r.End.UTC().Format(time.RFC3339Nano),
		"scheduled_total": r.ScheduledTotal, "sent_total": r.SentTotal, "unsent_total": r.UnsentTotal,
		"scheduled": r.Scheduled, "completed": r.Completed, "incomplete": r.Incomplete, "unsent": r.Unsent,
		"errors": r.Errors, "blocked": r.Blocked, "statements": r.Stmts, "max_queue_depth": r.MaxQueueDepth,
		"error_samples": r.ErrSamples,
		"latency":       hist.Summarise(r.Allowed, true),
		"latency_scope": map[bool]string{true: "blocked statements (every class of the workload is blocked on an enforcing target)", false: "statements not blocked"}[allBlocked(ops)],
		"latency_all":   hist.Summarise(r.Latency, false),
		"service":       hist.Summarise(r.Service, false),
		"queue_wait":    hist.Summarise(r.QueueWait, false),
		"gen_lag":       hist.Summarise(r.GenLag, false),
		"classes":       r.Classes,
		"client": map[string]any{"ncpu": runtime.NumCPU(), "gomaxprocs": runtime.GOMAXPROCS(0),
			"cpu_user_s": cpu(ru1.Utime) - cpu(ru0.Utime), "cpu_sys_s": cpu(ru1.Stime) - cpu(ru0.Stime), "wall_s": wall},
	}
	if done := r.Completed; done > 0 && float64(r.Errors)/float64(done) > o.maxErr {
		res["invalid"] = fmt.Sprintf("unexpected error ratio %.5f above %.5f", float64(r.Errors)/float64(done), o.maxErr)
	}
	if o.out != "" {
		writeOutputs(o.out, res, r)
	}
	summary := map[string]any{}
	for _, k := range []string{"target", "engine", "mode", "workload", "loop", "status", "reason", "offered_rate", "achieved_rate", "errors", "blocked", "unsent", "incomplete", "invalid"} {
		if v, ok := res[k]; ok {
			summary[k] = v
		}
	}
	lat := hist.Summarise(r.Allowed, false)
	summary["p50_ms"], summary["p99_ms"], summary["p999_ms"], summary["max_ms"] = lat.P50, lat.P99, lat.P999, lat.Max
	emit("VBENCH", summary)
	switch {
	case r.Status == openloop.StatusAborted && strings.HasPrefix(r.Reason, "connection failure"):
		return 3
	case r.Status == openloop.StatusAborted:
		return 9
	case res["invalid"] != nil:
		return 4
	}
	return 0
}

// allBlocked reports whether every class of the workload is expected blocked.
func allBlocked(ops []workload.Op) bool {
	for _, op := range ops {
		if op.Verdict != workload.Block {
			return false
		}
	}
	return len(ops) > 0
}

func writeOutputs(dir string, res map[string]any, r *openloop.Result) {
	b, _ := json.MarshalIndent(res, "", "  ")
	if err := os.WriteFile(filepath.Join(dir, "result.json"), append(b, '\n'), 0o644); err != nil {
		fatal("write result", err)
	}
	// HdrHistogram interval log (standard format, readable by HistogramLogProcessor).
	f, err := os.Create(filepath.Join(dir, "latency.hlog"))
	if err != nil {
		fatal("write hlog", err)
	}
	w := hdr.NewHistogramLogWriter(f)
	base := r.MeasureFrom.UnixMilli()
	_ = w.OutputLogFormatVersion()
	_ = w.OutputComment("vbench latency from intended send time, microseconds; allowed statements only")
	_ = w.OutputStartTime(base)
	w.SetBaseTime(base)
	_ = w.OutputBaseTime(base)
	_ = w.OutputLegend()
	for _, iv := range r.Intervals {
		h := iv.Latency
		h.SetStartTimeMs(iv.Start.UnixMilli())
		h.SetEndTimeMs(iv.End.UnixMilli())
		_ = w.OutputIntervalHistogram(h)
	}
	f.Close()
	// The same intervals as sparse buckets, for the analysis (no HDR library needed).
	g, err := os.Create(filepath.Join(dir, "intervals.jsonl"))
	if err != nil {
		fatal("write intervals", err)
	}
	enc := json.NewEncoder(g)
	for i, iv := range r.Intervals {
		_ = enc.Encode(map[string]any{"i": i, "start": iv.Start.UTC().Format(time.RFC3339Nano), "end": iv.End.UTC().Format(time.RFC3339Nano),
			"completed": iv.Completed, "buckets_us": hist.Sparse(iv.Latency)})
	}
	g.Close()
}
