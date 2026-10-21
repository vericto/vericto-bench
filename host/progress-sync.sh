#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Copies a running suite's results and logs to s3://<bucket>/<run_id>/partial/
# every PROGRESS_SYNC_S seconds (default 600), so a long run (the published day
# is 80+ hours) can be followed from outside and its data survives if the host
# stops before finish.sh (runtime guard, spot of bad luck). Started in the
# background by the runner host's user-data; finish.sh stops it and uploads the
# final, checksummed archives. Only this run's prefix is written (IAM).
#   host/progress-sync.sh
set -uo pipefail
# shellcheck disable=SC1091
. /etc/vericto-bench/run.env
RESULTS_DIR="/var/lib/vericto-bench/results/$RUN_ID"
DEST="s3://$BUCKET/$RUN_ID/partial"
EVERY="${PROGRESS_SYNC_S:-600}"
# Owner rule: no traffic near 1 Gbps, harness overhead included. Day 1 showed
# 1-s bursts of ~850 Mbps on the load generator's NIC while this sync uploaded
# (S3 gateway endpoint): cap the CLI at 8 MB/s (64 Mbps) and keep it on the OS core,
# off the load generator's cores.
export AWS_CONFIG_FILE=/etc/vericto-bench/aws-s3-capped.ini
printf '[default]\ns3 =\n  max_bandwidth = 8MB/s\n  max_concurrent_requests = 2\n' > "$AWS_CONFIG_FILE"
CPU_OS="$(sed -n 's/^CPU_OS=//p' /etc/vericto-bench/host.env 2>/dev/null)"
[ -n "$CPU_OS" ] && taskset -cp "$CPU_OS" $$ >/dev/null 2>&1
renice -n 10 $$ >/dev/null 2>&1 || true
echo $$ > /var/run/vericto-bench-progress-sync.pid
while :; do
  sleep "$EVERY"
  # The private key of the run's certificates is deleted by the runner at the
  # end; never copy it while the run is in progress.
  aws s3 sync --only-show-errors --region "$REGION" "$RESULTS_DIR/" "$DEST/results/" --exclude 'certs/server.key' \
    || echo "$(date -u +%FT%TZ) progress-sync: results sync failed"
  aws s3 cp --only-show-errors --region "$REGION" /var/log/vericto-bench/runner.log "$DEST/runner.log" \
    || echo "$(date -u +%FT%TZ) progress-sync: log upload failed"
  date -u +%FT%TZ | aws s3 cp --only-show-errors --region "$REGION" - "$DEST/HEARTBEAT" || true
done
