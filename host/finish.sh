#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Always runs at the end of a run (EXIT trap of the runner host's user-data):
# packs the results and logs with SHA256SUMS, uploads them to
# s3://<bucket>/<run_id>/, writes a DONE or FAILED marker, then stops the hosts
# when AUTO_SHUTDOWN=1.
#   host/finish.sh <runner exit code>
# Runs as root on the load generator (two-host) or the single host.
set -uo pipefail
RC="${1:-1}"
# shellcheck disable=SC1091
. /etc/vericto-bench/run.env
RESULTS_DIR="/var/lib/vericto-bench/results/$RUN_ID"
STAGE="$(mktemp -d /var/tmp/vbench-finish.XXXXXX)"
DEST="s3://$BUCKET/$RUN_ID"
log() { printf '%s finish: %s\n' "$(date -u +%FT%TZ)" "$*"; }

mkdir -p "$RESULTS_DIR" "$STAGE/logs/$ROLE"
cp -a /var/log/vericto-bench/. "$STAGE/logs/$ROLE/" 2>/dev/null || true
cp /etc/vericto-bench/provenance.json "$STAGE/logs/$ROLE/" 2>/dev/null || true
if [ "$TOPOLOGY" = two-host ] && [ -n "${SUT_IP:-}" ]; then
  mkdir -p "$STAGE/logs/sut"
  sudo -u bench -H scp -q -r -o BatchMode=yes -o ConnectTimeout=10 \
    "bench@$SUT_IP:/var/log/vericto-bench/." "$STAGE/logs/sut/" 2>/dev/null || log "WARNING: could not copy the SUT logs"
  sudo -u bench -H scp -q -o BatchMode=yes -o ConnectTimeout=10 \
    "bench@$SUT_IP:/etc/vericto-bench/provenance.json" "$STAGE/logs/sut/" 2>/dev/null || true
fi

tar -C "$(dirname "$RESULTS_DIR")" -czf "$STAGE/results-$RUN_ID.tar.gz" "$RUN_ID"
tar -C "$STAGE" -czf "$STAGE/logs-$RUN_ID.tar.gz" logs
( cd "$STAGE" && sha256sum "results-$RUN_ID.tar.gz" "logs-$RUN_ID.tar.gz" > SHA256SUMS )

upload_ok=1
for f in "results-$RUN_ID.tar.gz" "logs-$RUN_ID.tar.gz" SHA256SUMS; do
  aws s3 cp --only-show-errors --region "$REGION" "$STAGE/$f" "$DEST/$f" || upload_ok=0
done
marker=DONE
[ "$RC" = 0 ] && [ "$upload_ok" = 1 ] || marker=FAILED
printf 'run_id=%s\nrunner_exit=%s\nupload_ok=%s\nfinished_at=%s\n' "$RUN_ID" "$RC" "$upload_ok" "$(date -u +%FT%TZ)" > "$STAGE/$marker"
aws s3 cp --only-show-errors --region "$REGION" "$STAGE/$marker" "$DEST/$marker" || log "WARNING: marker upload failed"
log "results uploaded to $DEST ($marker, runner exit $RC)"

if [ "${AUTO_SHUTDOWN:-1}" = 1 ]; then
  if [ "$TOPOLOGY" = two-host ] && [ -n "${SUT_IP:-}" ]; then
    sudo -u bench -H ssh -o BatchMode=yes -o ConnectTimeout=10 "bench@$SUT_IP" sudo /usr/sbin/shutdown -h now \
      || log "WARNING: could not stop the SUT; its runtime guard stops it later"
  fi
  log "stopping this host"
  /usr/sbin/shutdown -h +1 >/dev/null 2>&1 || true
fi
exit 0
