# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
# PgBouncer built from the release tarball (there is no official image),
# verified against PGBOUNCER_SHA256 from versions.lock.
ARG UBUNTU_IMAGE
FROM ${UBUNTU_IMAGE} AS build
ARG PGBOUNCER_VERSION
ARG PGBOUNCER_SHA256
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates curl build-essential pkg-config libevent-dev libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSL -o p.tgz "https://www.pgbouncer.org/downloads/files/${PGBOUNCER_VERSION}/pgbouncer-${PGBOUNCER_VERSION}.tar.gz" && \
    echo "${PGBOUNCER_SHA256}  p.tgz" | sha256sum -c - && tar xzf p.tgz && cd pgbouncer-${PGBOUNCER_VERSION} && \
    ./configure --prefix=/usr/local --without-cares --without-pam --without-ldap --without-systemd >/dev/null && make -j"$(nproc)" >/dev/null && make install >/dev/null

FROM ${UBUNTU_IMAGE}
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends libevent-2.1-7t64 libssl3t64 ca-certificates && rm -rf /var/lib/apt/lists/* && \
    useradd -r -u 10002 pgbouncer && mkdir -p /etc/pgbouncer && chown pgbouncer /etc/pgbouncer
COPY --from=build /usr/local/bin/pgbouncer /usr/local/bin/pgbouncer
USER pgbouncer
ENTRYPOINT ["/usr/local/bin/pgbouncer"]
CMD ["/etc/pgbouncer/pgbouncer.ini"]
