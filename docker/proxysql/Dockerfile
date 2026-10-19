# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
# ProxySQL from the upstream release .deb for Ubuntu 24.04, verified against
# the per-architecture sha256 in versions.lock.
ARG UBUNTU_IMAGE
FROM ${UBUNTU_IMAGE}
ARG TARGETARCH
ARG PROXYSQL_VERSION
ARG PROXYSQL_DEB_SHA256_ARM64
ARG PROXYSQL_DEB_SHA256_AMD64
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates curl && \
    case "$TARGETARCH" in arm64) SUM=$PROXYSQL_DEB_SHA256_ARM64 ;; amd64) SUM=$PROXYSQL_DEB_SHA256_AMD64 ;; *) echo "unsupported $TARGETARCH"; exit 1 ;; esac && \
    curl -fsSL -o /tmp/p.deb "https://github.com/sysown/proxysql/releases/download/v${PROXYSQL_VERSION}/proxysql_${PROXYSQL_VERSION}-ubuntu24_${TARGETARCH}.deb" && \
    echo "$SUM  /tmp/p.deb" | sha256sum -c - && apt-get install -y -qq /tmp/p.deb && rm -f /tmp/p.deb && \
    apt-get purge -y -qq curl && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["proxysql", "-f", "--idle-threads", "-c", "/etc/proxysql.cnf", "-D", "/var/lib/proxysql"]
