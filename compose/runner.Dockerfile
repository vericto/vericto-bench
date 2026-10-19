# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
# The smoke runner: Python 3.12 and the Docker CLI (it drives sibling containers
# through the mounted Docker socket). NOT FOR PUBLISHED NUMBERS.
ARG ALPINE_IMAGE
FROM ${ALPINE_IMAGE}
RUN apk add --no-cache python3 docker-cli
WORKDIR /opt/vericto-bench
