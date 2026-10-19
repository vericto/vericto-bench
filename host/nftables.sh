#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Byte counters per direction per hop on the bench ports (design §8a). They only
# count; no rule drops or changes a packet.
#
#   host/nftables.sh apply    # (re)create table inet vbench with zeroed counters
#   host/nftables.sh show     # nft -j list counters table inet vbench (what hostmon reads)
#   host/nftables.sh reset    # zero every counter
#   host/nftables.sh remove   # delete the table
#
# Port plan (SUT, host network):
#   5432 PostgreSQL direct      3306 MySQL direct
#   6432 vericto-proxy PG       6433 second PG proxy task
#   6306 vericto-proxy MySQL    6307 second MySQL proxy task
#   7432 HAProxy PG             7306 HAProxy MySQL
#   8432 PgBouncer              8306 ProxySQL (admin 6032 on 127.0.0.1, not counted)
#   9090 cpstub, 127.0.0.1 only
#
# Counter names (nft object names must start with a letter, hence the prefixes).
# Bytes are IP packet lengths (IP + TCP headers included).
#   p<port>_in       input hook,  tcp dport <port>              client -> intermediary (any interface)
#   p<port>_out      output hook, tcp sport <port>              intermediary -> client (any interface)
#   db<port>_in      input hook,  iif != lo, tcp dport <port>   remote client -> database (direct cells, two-host)
#   db<port>_out     output hook, oif != lo, tcp sport <port>   database -> remote client
#   db<port>_lo_in   output hook, oif lo, tcp dport <port>      local process -> database (intermediary upstream hop;
#                                                               in the single topology also the direct client)
#   db<port>_lo_out  output hook, oif lo, tcp sport <port>      database -> local process
#   cp9090_in        output hook, oif lo, tcp dport 9090        proxy -> cpstub (telemetry, rule sync)
#   cp9090_out       output hook, oif lo, tcp sport 9090        cpstub -> proxy
# Loopback packets traverse output and then input; every loopback flow above is
# counted once, in the output hook, except intermediary listener ports, whose
# inbound direction is counted once in input and outbound once in output.
set -euo pipefail

TABLE="inet vbench"
LISTENERS=(6432 6433 6306 6307 7432 7306 8432 8306)
DBS=(5432 3306)

render() {
  echo "table $TABLE {"
  for p in "${LISTENERS[@]}"; do echo "  counter p${p}_in {}"; echo "  counter p${p}_out {}"; done
  for d in "${DBS[@]}"; do
    for s in in out lo_in lo_out; do echo "  counter db${d}_${s} {}"; done
  done
  echo "  counter cp9090_in {}"
  echo "  counter cp9090_out {}"
  echo "  chain input {"
  echo "    type filter hook input priority -10; policy accept;"
  for p in "${LISTENERS[@]}"; do echo "    tcp dport $p counter name \"p${p}_in\""; done
  for d in "${DBS[@]}"; do echo "    iifname != \"lo\" tcp dport $d counter name \"db${d}_in\""; done
  echo "  }"
  echo "  chain output {"
  echo "    type filter hook output priority -10; policy accept;"
  for p in "${LISTENERS[@]}"; do echo "    tcp sport $p counter name \"p${p}_out\""; done
  for d in "${DBS[@]}"; do
    echo "    oifname != \"lo\" tcp sport $d counter name \"db${d}_out\""
    echo "    oifname \"lo\" tcp dport $d counter name \"db${d}_lo_in\""
    echo "    oifname \"lo\" tcp sport $d counter name \"db${d}_lo_out\""
  done
  echo "    oifname \"lo\" tcp dport 9090 counter name \"cp9090_in\""
  echo "    oifname \"lo\" tcp sport 9090 counter name \"cp9090_out\""
  echo "  }"
  echo "}"
}

case "${1:-}" in
  apply)
    nft delete table $TABLE 2>/dev/null || true
    render | nft -f -
    echo "nftables: table $TABLE loaded ($(nft -j list counters table $TABLE | jq '[.nftables[] | select(.counter)] | length') counters)"
    ;;
  show) nft -j list counters table $TABLE ;;
  reset) nft reset counters table $TABLE >/dev/null ;;
  remove) nft delete table $TABLE 2>/dev/null || true ;;
  render) render ;;
  *) echo "usage: $0 apply|show|reset|remove|render" >&2; exit 2 ;;
esac
