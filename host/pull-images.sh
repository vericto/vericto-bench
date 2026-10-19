#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Pulls every image in versions.lock by digest and builds the local images.
#   host/pull-images.sh [path/to/versions.lock]
# versions.lock: KEY=value lines; every key ending in _IMAGE is an image that
# must be pinned by digest (...@sha256:<64 hex>). PROXY_IMAGE_OVERRIDE, when set
# in the environment or in /etc/vericto-bench/run.env, is pulled as well.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$HERE/.." && pwd)"
LOCK="${1:-$REPO_DIR/versions.lock}"
[ -f "$LOCK" ] || { echo "no versions.lock at $LOCK" >&2; exit 2; }
if [ -z "${PROXY_IMAGE_OVERRIDE:-}" ] && [ -f /etc/vericto-bench/run.env ]; then
  PROXY_IMAGE_OVERRIDE="$(sed -n 's/^PROXY_IMAGE_OVERRIDE=//p' /etc/vericto-bench/run.env)"
fi

images=()
while IFS= read -r line; do
  line="${line%%#*}"; line="$(echo "$line" | tr -d '[:space:]')"
  [ -n "$line" ] || continue
  key="${line%%=*}"; val="${line#*=}"
  case "$key" in *_IMAGE) ;; *) continue ;; esac
  [[ "$val" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "$key is not pinned by digest: $val" >&2; exit 3; }
  images+=("$val")
done < "$LOCK"
if [ -n "${PROXY_IMAGE_OVERRIDE:-}" ]; then
  [[ "$PROXY_IMAGE_OVERRIDE" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "PROXY_IMAGE_OVERRIDE is not pinned by digest" >&2; exit 3; }
  images+=("$PROXY_IMAGE_OVERRIDE")
fi
[ "${#images[@]}" -gt 0 ] || { echo "no *_IMAGE entries in $LOCK" >&2; exit 3; }

# Same rewriting as runner/run.py: official images from LIBRARY_MIRROR, the
# proxy from its mirror (GHCR), by the same digest. Docker Hub's anonymous pull
# limit is shared by many EC2 hosts, so the user-data sets both.
LIBRARY_MIRROR="${LIBRARY_MIRROR:-}"
PROXY_MIRROR="$(sed -n 's/^VERICTO_PROXY_MIRROR=//p' "$LOCK")"
rewrite() {
  local ref="$1" name digest
  digest="${ref#*@}"; name="${ref%@*}"
  if [ -n "$LIBRARY_MIRROR" ] && [[ "$name" == docker.io/library/* ]]; then
    name="$LIBRARY_MIRROR/${name#docker.io/library/}"
  elif [ "${PROXY_FROM_MIRROR:-}" = 1 ] && [[ "$name" == docker.io/vericto/vericto-proxy* ]]; then
    name="$PROXY_MIRROR"
  fi
  # name@digest (a tag next to a digest is only a label)
  case "${name##*/}" in *:*) name="${name%:*}" ;; esac
  echo "$name@$digest"
}
for raw in "${images[@]}"; do
  img="$(rewrite "$raw")"
  echo "pull $img"
  for attempt in 1 2 3; do
    docker pull -q "$img" >/dev/null && break
    [ "$attempt" = 3 ] && { echo "pull failed: $img" >&2; exit 4; }
    sleep $((attempt * 10))
  done
done

# Images built from this checkout (pgbouncer, sysbench, vbench, cpstub, engine-eval).
if [ -f "$REPO_DIR/Makefile" ] && grep -q '^images:' "$REPO_DIR/Makefile"; then
  make -C "$REPO_DIR" images LIBRARY_MIRROR="$LIBRARY_MIRROR"
fi
echo "images ready (${#images[@]} pulled)"
