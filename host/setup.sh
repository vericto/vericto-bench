#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Prepares an Amazon Linux 2023 instance for vericto-bench. Idempotent.
#
#   host/setup.sh sut       # two-host: proxy, baselines, databases, cpstub, hostmon
#   host/setup.sh loadgen   # two-host: vbench, pgbench, sysbench, the runner
#   host/setup.sh single    # everything on one instance over loopback (not the
#                           # published topology; flagged in the manifest)
#
# Writes /etc/vericto-bench/host.env (role and CPU partitions), loads the nftables
# byte counters (SUT and single) and captures provenance. Runs as root.
set -euo pipefail

ROLE="${1:-}"
case "$ROLE" in sut|loadgen|single) ;; *) echo "usage: $0 sut|loadgen|single" >&2; exit 2 ;; esac
[ "$(id -u)" -eq 0 ] || { echo "setup.sh must run as root" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$HERE/.." && pwd)"
ETC=/etc/vericto-bench
LOG_DIR=/var/log/vericto-bench
RESULTS_ROOT=/var/lib/vericto-bench/results
mkdir -p "$ETC" "$LOG_DIR" "$RESULTS_ROOT"
chmod 0755 "$LOG_DIR"

log() { printf '%s setup[%s]: %s\n' "$(date -u +%FT%TZ)" "$ROLE" "$*"; }

# ---------------------------------------------------------------- packages
# OS updates at boot: the latest AL2023 release (the AMI is the latest too, from
# its public SSM parameter). A newer kernel would only run after a reboot;
# provenance records the running and the installed kernels.
log "applying OS updates"
dnf -y -q upgrade --releasever=latest >/dev/null
log "installing packages"
dnf -y -q install docker nftables chrony python3 python3.11 git jq sysstat unzip ethtool make tar gzip >/dev/null
command -v aws >/dev/null || dnf -y -q install awscli-2 >/dev/null

# ---------------------------------------------------------------- docker
# systemd cgroup driver: container cgroups are at a predictable path,
# /sys/fs/cgroup/system.slice/docker-<full id>.scope/, readable without root.
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" },
  "live-restore": false
}
JSON
systemctl enable --now docker >/dev/null
systemctl restart docker
systemctl enable --now chronyd >/dev/null

# ---------------------------------------------------------------- bench user
if ! id bench >/dev/null 2>&1; then
  useradd -m -s /bin/bash bench
fi
usermod -aG docker bench
install -d -m 0700 -o bench -g bench /home/bench/.ssh
if [ "$ROLE" = "sut" ] && [ -s "$ETC/sut_authorized_key" ]; then
  install -m 0600 -o bench -g bench "$ETC/sut_authorized_key" /home/bench/.ssh/authorized_keys
fi
NFT="$(command -v nft)"
SHUTDOWN="$(command -v shutdown)"
PROFILE=""
if [ "$ROLE" = sut ]; then
  # CPU profiles (curves with profile_s > 0): perf and FlameGraph's stack
  # collapser, pinned by commit.
  dnf -y -q install perf perl >/dev/null
  FG=/opt/vericto-bench-flamegraph
  # Retried: egress through a just-created NAT gateway can fail for the first
  # minutes after boot.
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    [ -d "$FG/.git" ] && break
    rm -rf "$FG"
    git clone -q https://github.com/brendangregg/FlameGraph.git "$FG" && break
    log "FlameGraph clone failed (attempt $attempt); retrying in 30 s"
    sleep 30
  done
  git -C "$FG" checkout -q 41fee1f99f9276008b7cd112fca19dc3ea84ac32
  PROFILE=", $HERE/profile.sh *"
fi
cat > /etc/sudoers.d/vericto-bench <<SUDO
# vericto-bench: the only commands the bench user may run as root.
bench ALL=(root) NOPASSWD: $SHUTDOWN -h now, $NFT -j list counters table inet vbench, $NFT list *$PROFILE
SUDO
chmod 0440 /etc/sudoers.d/vericto-bench
visudo -cf /etc/sudoers.d/vericto-bench >/dev/null
chown bench:bench "$RESULTS_ROOT"

# ---------------------------------------------------------------- host hygiene
log "tuning: THP never, IRQs on cpu0, background timers off"
for f in /sys/kernel/mm/transparent_hugepage/enabled /sys/kernel/mm/transparent_hugepage/defrag; do
  if [ -w "$f" ]; then echo never > "$f"; fi
done
systemctl disable --now irqbalance >/dev/null 2>&1 || true
echo 1 > /proc/irq/default_smp_affinity 2>/dev/null || true
irq_failed=0
for f in /proc/irq/*/smp_affinity_list; do
  echo 0 > "$f" 2>/dev/null || irq_failed=$((irq_failed + 1))
done
# Some IRQs (per-CPU timers) cannot be moved; that is expected. Recorded.
for t in dnf-makecache.timer update-motd.timer; do
  systemctl disable --now "$t" >/dev/null 2>&1 || true
done

CHRONY_SYNCED=0
if chronyc waitsync 30 0.01 >/dev/null 2>&1; then CHRONY_SYNCED=1; else log "WARNING: chrony not synced within 5 minutes"; fi

# ---------------------------------------------------------------- CPU partitions
NCPU="$(nproc --all)"
# Group logical CPUs by physical core (thread_siblings_list), ordered by first CPU.
mapfile -t CORES < <(for c in /sys/devices/system/cpu/cpu[0-9]*; do
  cat "$c/topology/thread_siblings_list"; done | sort -u -t, -k1,1n)
SMT=0
for c in "${CORES[@]}"; do case "$c" in *,*|*-*) SMT=1 ;; esac; done
first() { echo "${1%%[,-]*}"; }
second() { local s="${1#*[,-]}"; echo "$s"; }

CPU_OS="" CPU_AUX="" CPU_SPARE="" CPU_PROXY="" CPU_PROXY2="" CPU_DB="" CPU_LOADGEN="" CPU_IDLE=""
if [ "$SMT" = 0 ]; then
  case "$ROLE" in
    sut|single)
      [ "$NCPU" -ge 8 ] || { echo "role $ROLE needs 8 physical cores (c7g.2xlarge); found $NCPU" >&2; exit 3; }
      CPU_OS=0; CPU_PROXY=3; CPU_PROXY2=4; CPU_DB=5-7
      if [ "$ROLE" = sut ]; then CPU_AUX=1; CPU_SPARE=2; else CPU_AUX=0; CPU_LOADGEN=1-2; fi ;;
    loadgen)
      [ "$NCPU" -ge 4 ] || { echo "loadgen needs 4 cores; found $NCPU" >&2; exit 3; }
      CPU_OS=0; CPU_LOADGEN="1-$((NCPU - 1))" ;;
  esac
else
  # SMT (c7i: a vCPU is a hyperthread). The proxy and the second intermediary
  # each get one thread of their own core with the sibling left idle, so no
  # other work shares a core with them. On c7i.2xlarge (4 cores x 2 threads):
  #   core 0: OS (thread a) + cpstub/hostmon (thread b)
  #   core 1: proxy under test, sibling idle
  #   core 2: second proxy task / baseline, sibling idle
  #   core 3: database (both threads; 2 vCPUs instead of 3 cores on c7g)
  case "$ROLE" in
    sut)
      [ "${#CORES[@]}" -ge 4 ] || { echo "SMT SUT needs 4 physical cores; found ${#CORES[@]}" >&2; exit 3; }
      CPU_OS="$(first "${CORES[0]}")"; CPU_AUX="$(second "${CORES[0]}")"
      CPU_PROXY="$(first "${CORES[1]}")"; CPU_PROXY2="$(first "${CORES[2]}")"
      CPU_IDLE="$(second "${CORES[1]}"),$(second "${CORES[2]}")"
      CPU_DB="${CORES[3]}"
      if [ "${#CORES[@]}" -gt 4 ]; then CPU_SPARE="$(printf '%s,' "${CORES[@]:4}" | sed 's/,$//')"; fi ;;
    loadgen)
      CPU_OS="$(first "${CORES[0]}")"
      CPU_LOADGEN="$(seq 0 $((NCPU - 1)) | grep -vx "$CPU_OS" | paste -sd, -)" ;;
    single)
      echo "the single topology is not supported on SMT instances: the proxy's sibling thread cannot be kept idle with a load generator on the same host" >&2
      exit 3 ;;
  esac
fi

ARCH="$(uname -m)"
TOKEN="$(curl -sf -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 300' || true)"
imds() { [ -n "$TOKEN" ] && curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1" || echo unknown; }
INSTANCE_TYPE="$(imds instance-type)"

TOPOLOGY=two-host
[ "$ROLE" = single ] && TOPOLOGY=single
cat > "$ETC/host.env" <<ENV
# Written by host/setup.sh on $(date -u +%FT%TZ). CPU lists are cpuset syntax.
ROLE=$ROLE
TOPOLOGY=$TOPOLOGY
INSTANCE_TYPE=$INSTANCE_TYPE
ARCH=$ARCH
NCPU=$NCPU
SMT=$SMT
CPU_OS=$CPU_OS
CPU_AUX=$CPU_AUX
CPU_SPARE=$CPU_SPARE
CPU_PROXY=$CPU_PROXY
CPU_PROXY2=$CPU_PROXY2
CPU_DB=$CPU_DB
CPU_LOADGEN=$CPU_LOADGEN
CPU_IDLE=$CPU_IDLE
CHRONY_SYNCED=$CHRONY_SYNCED
IRQ_PIN_FAILED=$irq_failed
REPO_DIR=$REPO_DIR
RESULTS_ROOT=$RESULTS_ROOT
LOG_DIR=$LOG_DIR
CGROUP_DRIVER=systemd
ENV
chmod 0644 "$ETC/host.env"
log "CPU plan: $(grep '^CPU_' "$ETC/host.env" | tr '\n' ' ')"

# ---------------------------------------------------------------- counters, provenance
if [ "$ROLE" != loadgen ]; then
  "$HERE/nftables.sh" apply
fi
"$HERE/provenance.sh" > "$ETC/provenance.json"
chmod 0644 "$ETC/provenance.json"
log "done"
