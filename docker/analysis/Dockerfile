# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
# The report generator: Python 3.12 and matplotlib from Ubuntu 24.04.
ARG UBUNTU_IMAGE
FROM ${UBUNTU_IMAGE}
ARG MATPLOTLIB_APT_VERSION
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 "python3-matplotlib=${MATPLOTLIB_APT_VERSION}" && rm -rf /var/lib/apt/lists/*
COPY analysis /opt/vericto-bench/analysis
ENTRYPOINT ["python3", "-I", "/opt/vericto-bench/analysis/report.py"]
