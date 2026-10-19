#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Downloads the run's results, checks them, then destroys every resource of the
# run. Refuses to destroy if the download or the checksum check failed (the
# bucket is force_destroy: destroying it deletes what was not downloaded).
#   ./teardown.sh [-var-file=run.tfvars ...]   # the same -var/-var-file as apply
set -euo pipefail
cd "$(dirname "$0")"

bucket="$(terraform output -raw results_bucket)"
run_id="$(terraform output -raw run_id)"
region="$(terraform output -raw region)"
dest="../../results/$run_id"
mkdir -p "$dest"

echo "syncing s3://$bucket/$run_id/ -> $dest"
if ! aws s3 sync --only-show-errors --region "$region" "s3://$bucket/$run_id/" "$dest/" --exclude 'harness/*'; then
  echo "sync failed: not destroying (results would be lost)" >&2
  exit 1
fi
if [ -f "$dest/SHA256SUMS" ]; then
  ( cd "$dest" && shasum -a 256 -c SHA256SUMS ) || { echo "checksum mismatch: not destroying" >&2; exit 1; }
elif [ -z "${ALLOW_NO_RESULTS:-}" ]; then
  echo "no SHA256SUMS in s3://$bucket/$run_id/ (run unfinished or failed)." >&2
  echo "Set ALLOW_NO_RESULTS=1 to destroy anyway." >&2
  exit 1
fi
for m in DONE FAILED; do [ -f "$dest/$m" ] && { echo "marker $m:"; cat "$dest/$m"; }; done

terraform destroy "$@"
