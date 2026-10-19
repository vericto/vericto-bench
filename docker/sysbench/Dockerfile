# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
ARG UBUNTU_IMAGE
FROM ${UBUNTU_IMAGE}
ARG SYSBENCH_APT_VERSION
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates "sysbench=${SYSBENCH_APT_VERSION}" && rm -rf /var/lib/apt/lists/* && sysbench --version
ENTRYPOINT ["sysbench"]
