#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
# Laptop smoke run. SMOKE RUN: NOT FOR PUBLISHED NUMBERS.
#
#   compose/smoke.sh            build the images, run suites/smoke.toml, copy
#                               the results to results/<run_id>, remove the
#                               containers, network and volume
#   KEEP_IMAGES=0 compose/smoke.sh   also remove the vericto-bench/* images
#   LIBRARY_MIRROR=public.ecr.aws/docker/library compose/smoke.sh   pull official
#                               images from a mirror (same digests)
set -euo pipefail
cd "$(dirname "$0")/.."
RUN_ID="${RUN_ID:-smoke-$(date -u +%Y%m%dT%H%M%SZ)}"
export RUN_ID SUITE="${SUITE:-smoke}"
lock() { sed -n "s/^$1=//p" versions.lock; }
lib() { local r; r="$(lock "$1")"; if [ -n "${LIBRARY_MIRROR:-}" ]; then echo "${r/docker.io\/library/$LIBRARY_MIRROR}"; else echo "$r"; fi; }
ALPINE_IMAGE="$(lib ALPINE_IMAGE)"
export ALPINE_IMAGE
HARNESS_COMMIT="$(git rev-parse --verify -q HEAD 2>/dev/null || echo unknown)"
export HARNESS_COMMIT
compose=(docker compose -f compose/smoke.yml)
cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  ids=$(docker ps -aq --filter "label=vericto-bench.run=$RUN_ID")
  [ -z "$ids" ] || docker rm -f -v $ids >/dev/null
  if [ "${KEEP_IMAGES:-1}" = 0 ]; then
    make clean-images >/dev/null 2>&1 || true
    docker rmi vericto-bench/runner:local >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
make images LIBRARY_MIRROR="${LIBRARY_MIRROR:-}" GOPROXY="${GOPROXY:-https://proxy.golang.org,direct}"
rc=0
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from runner || rc=$?
mkdir -p results
# Copy the run out of the volume before it is removed.
docker run --rm -v vericto-bench-smoke_data:/data -v "$PWD/results:/out" "$ALPINE_IMAGE" sh -c "cp -r /data/$RUN_ID /out/ && chmod -R a+rX /out/$RUN_ID" || rc=1
echo "smoke run $RUN_ID: exit $rc; results in results/$RUN_ID (SMOKE RUN: NOT FOR PUBLISHED NUMBERS)"
exit $rc
