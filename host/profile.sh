#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# CPU profile of one process on the SUT (a curve with profile_s > 0). Run by the
# bench user through sudo (host/setup.sh allows exactly this script):
#
#   sudo /opt/vericto-bench/host/profile.sh record <pid> <seconds> <name>
#   sudo /opt/vericto-bench/host/profile.sh script <name>      # folded stacks on stdout (gzip)
#   sudo /opt/vericto-bench/host/profile.sh report <name>      # perf report --stdio on stdout
#   sudo /opt/vericto-bench/host/profile.sh clean  <name>
#
# perf runs on the spare core (CPU_SPARE), samples at 499 Hz and unwinds with
# DWARF (.eh_frame): the vericto-proxy release binaries keep their symbols but
# omit frame pointers, so frame-pointer stacks would be truncated. The binary is
# copied out of the container and added to perf's build-id cache before the
# container goes away, so symbols resolve after the cell.
set -euo pipefail
DIR=/var/lib/vericto-bench/profiles
FG=/opt/vericto-bench-flamegraph
mkdir -p "$DIR"
cmd="${1:-}"
name="${3:-${2:-}}"
case "$cmd" in record) name="${4:-}" ;; esac
[[ "$name" =~ ^[A-Za-z0-9._-]{1,120}$ ]] || { echo "bad name" >&2; exit 2; }
spare="$(sed -n 's/^CPU_SPARE=//p' /etc/vericto-bench/host.env)"
pin=(); [ -n "$spare" ] && pin=(taskset -c "$spare")
case "$cmd" in
  record)
    pid="$2" secs="$3"
    [[ "$pid" =~ ^[0-9]+$ && "$secs" =~ ^[0-9]+$ ]] || { echo "bad pid/seconds" >&2; exit 2; }
    cp "/proc/$pid/exe" "$DIR/$name.exe"
    perf buildid-cache -a "$DIR/$name.exe" >/dev/null 2>&1 || true
    "${pin[@]}" perf record -q -F 499 --call-graph dwarf,16384 -p "$pid" -o "$DIR/$name.data" -- sleep "$secs" >/dev/null 2>&1
    ls -l "$DIR/$name.data" | awk '{print $5}'
    ;;
  script)
    "${pin[@]}" perf script -i "$DIR/$name.data" 2>/dev/null | "$FG/stackcollapse-perf.pl" --all | gzip -c
    ;;
  report)
    "${pin[@]}" perf report -i "$DIR/$name.data" --stdio --no-children --sort symbol --percent-limit 0.3 -g none 2>/dev/null | head -400
    ;;
  clean)
    rm -f "$DIR/$name.data" "$DIR/$name.exe"
    ;;
  *) echo "usage: $0 record|script|report|clean ..." >&2; exit 2 ;;
esac
