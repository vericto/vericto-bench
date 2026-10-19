#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# Exit 0 when the SUT finished its setup, 2 when its setup failed (the load
# generator stops waiting), 1 while it is still preparing.
set -euo pipefail
if [ -f /etc/vericto-bench/failed ]; then cat /etc/vericto-bench/failed >&2; exit 2; fi
[ -f /etc/vericto-bench/ready ]
