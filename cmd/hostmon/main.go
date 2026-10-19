// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// hostmon: counters, traffic-cap guard and pre-flight for vericto-bench.
//
//	hostmon sample    -host sut -iface ens5 -nft -cgroup proxy=/sys/fs/cgroup/... -netns db=PID
//	    One JSON line per second of cumulative counters: interface and network
//	    namespace bytes, nftables counters, container cgroup CPU (cpu.stat) and
//	    the host's steal time. Runs on every host of a cell.
//	hostmon guard     -components c.json -stream 'ssh sut hostmon sample ...' -stop-file F
//	    Reads the sample streams, applies the caps (per component 400 Mbps hard,
//	    300 target; aggregate 800 hard, 600 target), writes one verdict per
//	    second, and on a breach writes the stop file (vbench aborts the cell)
//	    and exits 9.
//	hostmon preflight -plan plan.json
//	    Expected traffic of every planned cell from a probe; exit 1 and the
//	    highest rate that fits when a cell would cross a design target.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/vericto/vericto-bench/internal/netcap"
)

type multi []string

func (m *multi) String() string     { return strings.Join(*m, ",") }
func (m *multi) Set(v string) error { *m = append(*m, v); return nil }

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: hostmon sample|guard|preflight [flags]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "sample":
		sample(os.Args[2:])
	case "guard":
		os.Exit(guard(os.Args[2:]))
	case "preflight":
		os.Exit(preflight(os.Args[2:]))
	default:
		fmt.Fprintf(os.Stderr, "hostmon: unknown command %q\n", os.Args[1])
		os.Exit(2)
	}
}

// ---- sample -------------------------------------------------------------------

type cpuStat struct {
	UsageUsec     uint64 `json:"usage_usec"`
	UserUsec      uint64 `json:"user_usec"`
	SystemUsec    uint64 `json:"system_usec"`
	NrPeriods     uint64 `json:"nr_periods"`
	NrThrottled   uint64 `json:"nr_throttled"`
	ThrottledUsec uint64 `json:"throttled_usec"`
}

type sampleLine struct {
	T    time.Time          `json:"t"`
	Host string             `json:"host"`
	C    map[string]uint64  `json:"c"`
	CPU  map[string]cpuStat `json:"cpu,omitempty"`
	Stat map[string]uint64  `json:"stat,omitempty"`
	Errs []string           `json:"errors,omitempty"`
}

func sample(args []string) {
	fs := flag.NewFlagSet("sample", flag.ExitOnError)
	host := fs.String("host", "host", "label prefixed to every counter key")
	proc := fs.String("proc", "/proc", "procfs root (/host/proc in a container)")
	var ifaces, netns, cgroups, cgroupIDs multi
	fs.Var(&ifaces, "iface", "interface of this host's network namespace, or auto for the default route's (repeatable)")
	fs.Var(&cgroupIDs, "cgroup-id", "name=CONTAINER_ID: the container's cgroup, found under -cgroup-root (repeatable)")
	cgroupRoot := fs.String("cgroup-root", "/sys/fs/cgroup", "cgroup v2 mount (/host/cgroup in a container)")
	fs.Var(&netns, "netns", "name=PID: all non-loopback interfaces of PID's network namespace (repeatable)")
	fs.Var(&cgroups, "cgroup", "name=DIR: cgroup v2 directory whose cpu.stat is read (repeatable)")
	nft := fs.Bool("nft", false, "read the nftables counters of table inet vbench")
	nftCmd := fs.String("nft-cmd", "nft", "command that runs nft (e.g. 'sudo nft')")
	interval := fs.Duration("interval", time.Second, "sampling interval")
	count := fs.Int("count", 0, "samples to take (0 = until killed)")
	_ = fs.Parse(args)

	// "auto" samples the default route's interface under the key "default",
	// so a components file does not depend on the interface's name.
	label := map[string]string{}
	for i, ifc := range ifaces {
		label[ifc] = ifc
		if ifc == "auto" {
			d, err := defaultIface(filepath.Join(*proc, "net/route"))
			if err != nil {
				fmt.Fprintf(os.Stderr, "hostmon sample: %v\n", err)
				os.Exit(2)
			}
			ifaces[i] = d
			label[d] = "default"
		}
	}
	for _, kv := range cgroupIDs {
		name, id, ok := strings.Cut(kv, "=")
		dir := ""
		if ok {
			dir = findCgroup(*cgroupRoot, id)
		}
		if dir == "" {
			fmt.Fprintf(os.Stderr, "hostmon sample: no cgroup for %s under %s\n", kv, *cgroupRoot)
			os.Exit(2)
		}
		cgroups = append(cgroups, name+"="+dir)
	}
	enc := json.NewEncoder(os.Stdout)
	next := time.Now().Truncate(*interval).Add(*interval)
	for i := 0; *count == 0 || i < *count; i++ {
		time.Sleep(time.Until(next))
		next = next.Add(*interval)
		l := sampleLine{T: time.Now().UTC(), Host: *host, C: map[string]uint64{}, CPU: map[string]cpuStat{}}
		dev, err := readNetDev(filepath.Join(*proc, "net/dev"))
		if err != nil && len(ifaces) > 0 {
			l.Errs = append(l.Errs, err.Error())
		}
		for _, ifc := range ifaces {
			if d, ok := dev[ifc]; ok {
				l.C[*host+":iface:"+label[ifc]+":rx"], l.C[*host+":iface:"+label[ifc]+":tx"] = d[0], d[1]
			} else {
				l.Errs = append(l.Errs, "no interface "+ifc)
			}
		}
		for _, kv := range netns {
			name, pid, ok := strings.Cut(kv, "=")
			if !ok {
				l.Errs = append(l.Errs, "bad -netns "+kv)
				continue
			}
			d, err := readNetDev(filepath.Join(*proc, pid, "net/dev"))
			if err != nil {
				l.Errs = append(l.Errs, err.Error())
				continue
			}
			var rx, tx uint64
			for ifc, v := range d {
				if ifc != "lo" {
					rx += v[0]
					tx += v[1]
				}
			}
			l.C[*host+":netns:"+name+":rx"], l.C[*host+":netns:"+name+":tx"] = rx, tx
		}
		if *nft {
			c, err := readNft(*nftCmd)
			if err != nil {
				l.Errs = append(l.Errs, err.Error())
			}
			for k, v := range c {
				l.C[*host+":nft:"+k] = v
			}
		}
		for _, kv := range cgroups {
			name, dir, ok := strings.Cut(kv, "=")
			if !ok {
				l.Errs = append(l.Errs, "bad -cgroup "+kv)
				continue
			}
			st, err := readCPUStat(filepath.Join(dir, "cpu.stat"))
			if err != nil {
				l.Errs = append(l.Errs, err.Error())
				continue
			}
			l.CPU[name] = st
		}
		if st, err := readProcStat(filepath.Join(*proc, "stat")); err == nil {
			l.Stat = st
		}
		if err := enc.Encode(l); err != nil {
			return // reader went away
		}
	}
}

// defaultIface returns the interface of the IPv4 default route.
func defaultIface(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	for _, line := range strings.Split(string(b), "\n")[1:] {
		f := strings.Fields(line)
		if len(f) > 2 && f[1] == "00000000" {
			return f[0], nil
		}
	}
	return "", errors.New("no default route")
}

// findCgroup returns the cgroup directory of a container for the systemd and
// cgroupfs drivers of Docker.
func findCgroup(root, id string) string {
	for _, d := range []string{
		filepath.Join(root, "system.slice", "docker-"+id+".scope"),
		filepath.Join(root, "docker", id),
		filepath.Join(root, "docker.slice", "docker-"+id+".scope"),
	} {
		if _, err := os.Stat(filepath.Join(d, "cpu.stat")); err == nil {
			return d
		}
	}
	return ""
}

// readNetDev returns rx and tx bytes per interface.
func readNetDev(path string) (map[string][2]uint64, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	out := map[string][2]uint64{}
	for _, line := range strings.Split(string(b), "\n") {
		name, rest, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		f := strings.Fields(rest)
		if len(f) < 9 {
			continue
		}
		rx, _ := strconv.ParseUint(f[0], 10, 64)
		tx, _ := strconv.ParseUint(f[8], 10, 64)
		out[strings.TrimSpace(name)] = [2]uint64{rx, tx}
	}
	return out, nil
}

func readNft(cmd string) (map[string]uint64, error) {
	parts := strings.Fields(cmd)
	parts = append(parts, "-j", "list", "counters", "table", "inet", "vbench")
	out, err := exec.Command(parts[0], parts[1:]...).Output()
	if err != nil {
		return nil, fmt.Errorf("nft: %w", err)
	}
	return parseNft(out)
}

func parseNft(b []byte) (map[string]uint64, error) {
	var doc struct {
		Nftables []map[string]json.RawMessage `json:"nftables"`
	}
	if err := json.Unmarshal(b, &doc); err != nil {
		return nil, fmt.Errorf("nft json: %w", err)
	}
	out := map[string]uint64{}
	for _, obj := range doc.Nftables {
		raw, ok := obj["counter"]
		if !ok {
			continue
		}
		var c struct {
			Name  string `json:"name"`
			Bytes uint64 `json:"bytes"`
		}
		if err := json.Unmarshal(raw, &c); err == nil && c.Name != "" {
			out[c.Name] = c.Bytes
		}
	}
	return out, nil
}

func readCPUStat(path string) (cpuStat, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return cpuStat{}, err
	}
	var s cpuStat
	for _, line := range strings.Split(string(b), "\n") {
		f := strings.Fields(line)
		if len(f) != 2 {
			continue
		}
		v, _ := strconv.ParseUint(f[1], 10, 64)
		switch f[0] {
		case "usage_usec":
			s.UsageUsec = v
		case "user_usec":
			s.UserUsec = v
		case "system_usec":
			s.SystemUsec = v
		case "nr_periods":
			s.NrPeriods = v
		case "nr_throttled":
			s.NrThrottled = v
		case "throttled_usec":
			s.ThrottledUsec = v
		}
	}
	return s, nil
}

// readProcStat returns the aggregate CPU jiffies: steal and total.
func readProcStat(path string) (map[string]uint64, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	for _, line := range strings.Split(string(b), "\n") {
		f := strings.Fields(line)
		if len(f) > 8 && f[0] == "cpu" {
			var total uint64
			for _, x := range f[1:] {
				v, _ := strconv.ParseUint(x, 10, 64)
				total += v
			}
			steal, _ := strconv.ParseUint(f[8], 10, 64)
			return map[string]uint64{"steal": steal, "total": total}, nil
		}
	}
	return nil, errors.New("no cpu line in /proc/stat")
}

// ---- guard --------------------------------------------------------------------

func loadCaps(path, mode string, n int) (netcap.Caps, error) {
	c := netcap.Default()
	if path != "" {
		b, err := os.ReadFile(path)
		if err != nil {
			return c, err
		}
		if err := json.Unmarshal(b, &c); err != nil {
			return c, err
		}
	}
	switch mode {
	case "consecutive":
		c.Consecutive, c.AverageSamples = n, 0
	case "average":
		c.Consecutive, c.AverageSamples = 0, n
	case "":
	default:
		return c, fmt.Errorf("-rule must be consecutive or average")
	}
	return c, c.Validate()
}

func guard(args []string) int {
	fs := flag.NewFlagSet("guard", flag.ExitOnError)
	compsPath := fs.String("components", "", "JSON: component name -> counter keys (required)")
	capsPath := fs.String("caps", "", "JSON caps (default: 400/300 per component, 800/600 aggregate)")
	rule := fs.String("rule", "", "consecutive | average (default: caps file or consecutive 3)")
	n := fs.Int("n", 3, "samples for -rule")
	var streams multi
	fs.Var(&streams, "stream", "shell command printing `hostmon sample` lines (repeatable)")
	stdin := fs.Bool("stdin", false, "also read sample lines from stdin")
	stopFile := fs.String("stop-file", "", "written with the reason when a hard cap is breached")
	out := fs.String("out", "", "verdict lines (JSONL)")
	raw := fs.String("raw", "", "copy of every sample line (JSONL), for CPU and steal analysis")
	summary := fs.String("summary", "", "summary JSON written at exit")
	duration := fs.Duration("duration", 0, "stop after this long (0: until SIGTERM)")
	_ = fs.Parse(args)
	if *compsPath == "" {
		fmt.Fprintln(os.Stderr, "hostmon guard: -components is required")
		return 2
	}
	var comps netcap.Components
	if b, err := os.ReadFile(*compsPath); err != nil || json.Unmarshal(b, &comps) != nil {
		fmt.Fprintf(os.Stderr, "hostmon guard: cannot read %s\n", *compsPath)
		return 2
	}
	caps, err := loadCaps(*capsPath, *rule, *n)
	if err != nil {
		fmt.Fprintf(os.Stderr, "hostmon guard: %v\n", err)
		return 2
	}
	g, err := netcap.NewGuard(caps, comps)
	if err != nil {
		fmt.Fprintf(os.Stderr, "hostmon guard: %v\n", err)
		return 2
	}
	verdicts := io.Discard
	if *out != "" {
		f, err := os.Create(*out)
		if err != nil {
			fmt.Fprintf(os.Stderr, "hostmon guard: %v\n", err)
			return 2
		}
		defer f.Close()
		verdicts = f
	}
	var rawW io.Writer = io.Discard
	if *raw != "" {
		f, err := os.Create(*raw)
		if err != nil {
			fmt.Fprintf(os.Stderr, "hostmon guard: %v\n", err)
			return 2
		}
		defer f.Close()
		rawW = f
	}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer cancel()
	if *duration > 0 {
		var c2 context.CancelFunc
		ctx, c2 = context.WithTimeout(ctx, *duration)
		defer c2()
	}
	lines := make(chan []byte, 256)
	var wg sync.WaitGroup
	var procs []*exec.Cmd
	read := func(r io.Reader) {
		defer wg.Done()
		sc := bufio.NewScanner(r)
		sc.Buffer(make([]byte, 1<<20), 1<<20)
		for sc.Scan() {
			b := append([]byte(nil), sc.Bytes()...)
			select {
			case lines <- b:
			case <-ctx.Done():
				return
			}
		}
	}
	for _, s := range streams {
		cmd := exec.Command("sh", "-c", s)
		cmd.Stderr = os.Stderr
		pipe, err := cmd.StdoutPipe()
		if err != nil {
			fmt.Fprintf(os.Stderr, "hostmon guard: %v\n", err)
			return 2
		}
		if err := cmd.Start(); err != nil {
			fmt.Fprintf(os.Stderr, "hostmon guard: start %q: %v\n", s, err)
			return 2
		}
		procs = append(procs, cmd)
		wg.Add(1)
		go read(pipe)
	}
	if *stdin {
		wg.Add(1)
		go read(os.Stdin)
	}
	// When every stream has ended (the runner closed stdin, the samplers
	// exited), the guard stops and writes its summary.
	go func() {
		wg.Wait()
		cancel()
	}()
	defer func() {
		for _, p := range procs {
			_ = p.Process.Signal(syscall.SIGTERM)
		}
		for _, p := range procs {
			_ = p.Wait()
		}
	}()

	enc := json.NewEncoder(verdicts)
	tick := time.NewTicker(time.Second)
	defer tick.Stop()
	code := 0
	var reason string
loop:
	for {
		select {
		case <-ctx.Done():
			break loop
		case b := <-lines:
			_, _ = rawW.Write(append(b, '\n'))
			var l sampleLine
			if json.Unmarshal(b, &l) != nil {
				continue
			}
			g.Observe(netcap.Sample{T: l.T, Received: time.Now(), Counters: l.C})
		case now := <-tick.C:
			v := g.Evaluate(now)
			_ = enc.Encode(v)
			for _, w := range v.Warnings {
				fmt.Fprintf(os.Stderr, "hostmon guard: warning: %s\n", w)
			}
			if v.Abort {
				reason = v.Reason
				code = 9
				if *stopFile != "" {
					_ = os.WriteFile(*stopFile+".tmp", []byte(reason+"\n"), 0o644)
					_ = os.Rename(*stopFile+".tmp", *stopFile)
				}
				fmt.Fprintf(os.Stderr, "hostmon guard: ABORT: %s\n", reason)
				break loop
			}
		}
	}
	s := g.Summarise()
	res := map[string]any{"summary": s, "aborted": code == 9, "reason": reason}
	b, _ := json.Marshal(res)
	fmt.Printf("HOSTMON_SUMMARY %s\n", b)
	if *summary != "" {
		_ = os.WriteFile(*summary, append(b, '\n'), 0o644)
	}
	return code
}

// ---- preflight ----------------------------------------------------------------

type planFile struct {
	Caps       *netcap.Caps      `json:"caps"`
	Components netcap.Components `json:"components"`
	Cells      []struct {
		ID    string             `json:"id"`
		Rate  float64            `json:"rate"`
		Fixed map[string]float64 `json:"fixed_mbps"`
		Probe struct {
			Bytes    map[string]uint64 `json:"bytes"`
			Requests int64             `json:"requests"`
		} `json:"probe"`
		Bytes map[string]float64 `json:"bytes_per_request"` // instead of a probe
	} `json:"cells"`
}

func preflight(args []string) int {
	fs := flag.NewFlagSet("preflight", flag.ExitOnError)
	planPath := fs.String("plan", "", "plan JSON (required)")
	_ = fs.Parse(args)
	b, err := os.ReadFile(*planPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "hostmon preflight: %v\n", err)
		return 2
	}
	var p planFile
	if err := json.Unmarshal(b, &p); err != nil {
		fmt.Fprintf(os.Stderr, "hostmon preflight: %v\n", err)
		return 2
	}
	caps := netcap.Default()
	if p.Caps != nil {
		caps = *p.Caps
	}
	if err := caps.Validate(); err != nil {
		fmt.Fprintf(os.Stderr, "hostmon preflight: %v\n", err)
		return 2
	}
	var cells []netcap.PlannedCell
	expected := map[string]any{}
	for _, c := range p.Cells {
		per := c.Bytes
		if per == nil {
			per, err = netcap.Probe(p.Components, c.Probe.Bytes, c.Probe.Requests)
			if err != nil {
				fmt.Fprintf(os.Stderr, "hostmon preflight: cell %s: %v\n", c.ID, err)
				return 2
			}
		}
		pc := netcap.PlannedCell{ID: c.ID, Rate: c.Rate, BytesPerRequest: per, FixedMbps: c.Fixed}
		cells = append(cells, pc)
		m, agg := pc.Expected()
		expected[c.ID] = map[string]any{"mbps": m, "aggregate_mbps": agg, "max_rate": pc.MaxRate(caps), "bytes_per_request": per}
	}
	v := netcap.Preflight(caps, cells)
	sort.Slice(v, func(i, j int) bool { return v[i].Cell+v[i].What < v[j].Cell+v[j].What })
	out, _ := json.MarshalIndent(map[string]any{"caps": caps, "ok": len(v) == 0, "violations": v, "cells": expected}, "", "  ")
	fmt.Println(string(out))
	if len(v) > 0 {
		return 1
	}
	return 0
}
