#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Cuts a running suite short and runs a second suite on the same hosts, without
# re-provisioning. Used when the owner trims a campaign while it runs (BENCH-2026-11
# day 1: the "publishable core").
#
#   host/switch-suite.sh <stop-before-curve-id> <second-suite.toml> <subdir> [harness-commit]
#
# 1. Waits until the running runner logs "curve <stop-before-curve-id>:" (the first
#    curve that is not wanted; every curve before it completes as pre-registered).
# 2. Kills the user-data script with SIGKILL, so its EXIT trap (finish.sh, which
#    uploads and stops the hosts) does not run, then stops the runner with SIGINT:
#    its finally block removes the run's containers and writes manifest.json.
# 3. Runs the second suite into <results>/<run_id>/<subdir> (same data root, so the
#    final archive holds both), uploading its log to the progress prefix.
# 4. Calls finish.sh with the second runner's exit code: archives, SHA256SUMS,
#    DONE/FAILED marker, and the hosts stop (AUTO_SHUTDOWN).
# Runs as root on the runner host (load generator), in the background (nohup).
set -uo pipefail
STOP_AT="$1"; SUITE="$2"; SUB="$3"; COMMIT="${4:-}"
# shellcheck disable=SC1091
. /etc/vericto-bench/run.env
RES="/var/lib/vericto-bench/results/$RUN_ID"
RLOG=/var/log/vericto-bench/runner.log
LOG2="/var/log/vericto-bench/runner-$SUB.log"
log() { printf '%s switch-suite: %s\n' "$(date -u +%FT%TZ)" "$*"; }
# The first suite's runner process (user bench), by its suite file name.
FIRST_SUITE="${FIRST_SUITE:-published.toml}"
runner_pid() { pgrep -u bench -f "runner/run.py --suite /opt/vericto-bench/suites/$FIRST_SUITE" | head -1; }
[ -f "$SUITE" ] || { log "no suite file $SUITE"; exit 2; }

log "waiting for 'curve $STOP_AT:' in $RLOG (first suite: $FIRST_SUITE)"
while ! grep -q "curve $STOP_AT:" "$RLOG"; do
  if [ -z "$(runner_pid)" ]; then log "the first runner exited before $STOP_AT; its own finish runs as usual"; exit 0; fi
  sleep 15
done
log "reached $STOP_AT: stopping the first suite"
for p in $(pgrep -f /var/lib/cloud/instance/scripts/part-001); do kill -9 "$p" 2>/dev/null || true; done
RP="$(runner_pid)"
[ -n "$RP" ] && kill -INT "$RP"
for _ in $(seq 1 60); do [ -z "$(runner_pid)" ] && break; sleep 5; done
if [ -n "$(runner_pid)" ]; then log "runner still alive after SIGINT: SIGTERM"; kill -TERM "$(runner_pid)"; sleep 10; fi
cp -a "$RES/manifest.json" "$RES/manifest-first-suite.json" 2>/dev/null || true
log "first suite stopped; running $SUITE into $RES/$SUB"

mkdir -p "$RES/$SUB" && chown bench:bench "$RES/$SUB"
sudo -u bench -H env RUN_ID="$RUN_ID-$SUB" HARNESS_COMMIT="${COMMIT:-${HARNESS_COMMIT:-}}" \
  LIBRARY_MIRROR=public.ecr.aws/docker/library PROXY_FROM_MIRROR=1 python3.11 /opt/vericto-bench/runner/run.py \
  --suite "$SUITE" --topology "$TOPOLOGY" --sut-ssh "bench@$SUT_IP" --day 1 --out "$RES/$SUB" > "$LOG2" 2>&1 &
P2=$!
while kill -0 "$P2" 2>/dev/null; do
  aws s3 cp --only-show-errors --region "$REGION" "$LOG2" "s3://$BUCKET/$RUN_ID/partial/runner-$SUB.log" || true
  sleep 300
done
wait "$P2"; RC=$?
aws s3 cp --only-show-errors --region "$REGION" "$LOG2" "s3://$BUCKET/$RUN_ID/partial/runner-$SUB.log" || true
log "second suite exit $RC; finishing the run"
/opt/vericto-bench/host/finish.sh "$RC"
