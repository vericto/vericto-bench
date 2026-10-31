**day 1 + day 2.**

# vericto-bench report: pub421-day1-pg, pub421-day1-my, pub421-day2, pub421-scaling

| Run | Profile | Topology | Proxy image | Harness commit | Started | Finished |
| --- | --- | --- | --- | --- | --- | --- |
| bench-2026-11-proxy-421-p | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `f041a49d177d` | 2026-10-31T13:42:43.715702+00:00 | 2026-10-31T21:20:58.052441+00:00 |
| bench-2026-11-proxy-421-m | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `f041a49d177d` | 2026-10-31T13:42:41.821712+00:00 | 2026-10-31T20:38:45.259058+00:00 |
| bench-2026-11-proxy-421-d2 | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `30131ce74266` | 2026-10-31T14:14:31.272904+00:00 | 2026-10-31T18:57:40.836082+00:00 |
| bench-2026-11-proxy-421-h2 | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `30131ce74266` | 2026-10-31T14:14:54.693556+00:00 | 2026-10-31T18:52:58.730505+00:00 |

Cells: 221 recorded, 213 used, 2 invalid (listed at the end, not used).

## Added latency (open loop, from intended send time; target minus direct, paired)

| Curve | Target | Rate/s | % of S | n | added p50 ms [95%] | added p99 ms [95%] | added p99.9 ms [95%] | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h2-pg-w1-05 | vericto-enforce | 2900 | 30 | 2 | 0.085 [0.060, 0.110] | 0.283 [0.276, 0.289] | 1.213 [1.175, 1.251] |  |
| h2-pg-w1-2x05 | vericto-enforce | 2900 | 30 | 2 | 0.085 [0.078, 0.091] | 0.169 [0.144, 0.194] | 1.091 [0.971, 1.212] |  |
| h2-pg-w1-2x05 | vericto-enforce | 5801 | 60 | 2 | 0.081 [0.068, 0.094] | 0.297 [0.240, 0.355] | 1.115 [1.084, 1.147] |  |
| h2-pg-w1-2x05 | vericto-enforce | 8701 | 90 | 2 | 0.082 [0.075, 0.088] | 0.501 [0.463, 0.539] | 1.171 [1.076, 1.267] |  |
| h2-pg-w1-2x05 | vericto-enforce | 11601 | 120 | 2 | 0.095 [0.075, 0.114] | 0.860 [0.167, 1.552] | 2.381 [0.584, 4.179] |  |
| h2-pg-w1-2x05 | vericto-enforce | 14502 | 150 | 2 | 0.116 [0.116, 0.116] | 1.377 [0.849, 1.904] | 5.146 [-1.442, 11.735] | not distinguishable from the direct path |
| h2-pg-w1-2x05 | vericto-enforce | 17402 | 180 | 2 | 4.272 [-45.491, 54.036] | 46.506 [-221.794, 314.806] | 24.462 [-1126.308, 1175.232] | not distinguishable from the direct path |
| head-my-w3-05 | haproxy-tcp | 36 | 10 | 4 | 0.532 [0.494, 0.569] | 0.551 [0.511, 0.591] | 0.762 [0.374, 1.150] |  |
| head-my-w3-05 | haproxy-tcp | 107 | 30 | 4 | 0.438 [0.382, 0.494] | 0.486 [0.456, 0.516] | 0.597 [0.393, 0.801] |  |
| head-my-w3-05 | haproxy-tcp | 178 | 50 | 4 | 0.467 [0.406, 0.528] | 0.477 [0.404, 0.549] | 0.551 [0.399, 0.704] |  |
| head-my-w3-05 | haproxy-tcp | 250 | 70 | 4 | 0.473 [0.461, 0.485] | 0.474 [0.457, 0.491] | 0.476 [0.286, 0.666] |  |
| head-my-w3-05 | haproxy-tcp | 285 | 80 | 4 | 0.474 [0.450, 0.497] | 0.525 [0.478, 0.573] | 0.711 [0.238, 1.183] |  |
| head-my-w3-05 | haproxy-tcp | 321 | 90 | 4 | 0.429 [0.412, 0.446] | 0.483 [0.439, 0.526] | 0.522 [0.391, 0.653] |  |
| head-my-w3-05 | haproxy-tcp | 357 | 100 | 4 | 0.285 [0.252, 0.317] | 0.515 [0.475, 0.555] | 0.620 [0.547, 0.692] |  |
| head-my-w3-05 | vericto-enforce | 36 | 10 | 4 | 1.193 [1.112, 1.274] | 1.319 [1.238, 1.400] | 2.358 [1.912, 2.804] |  |
| head-my-w3-05 | vericto-enforce | 107 | 30 | 4 | 1.095 [1.055, 1.134] | 1.569 [1.486, 1.651] | 2.731 [2.380, 3.082] |  |
| head-my-w3-05 | vericto-enforce | 178 | 50 | 4 | 1.119 [1.051, 1.186] | 1.890 [1.785, 1.996] | 2.923 [2.416, 3.431] |  |
| head-my-w3-05 | vericto-enforce | 250 | 70 | 4 | 1.081 [1.048, 1.115] | 2.012 [1.969, 2.054] | 4.267 [3.924, 4.610] |  |
| head-my-w3-05 | vericto-enforce | 285 | 80 | 4 | 1.015 [0.974, 1.056] | 2.153 [2.077, 2.228] | 4.393 [4.180, 4.606] |  |
| head-my-w3-05 | vericto-enforce | 321 | 90 | 4 | 0.686 [0.622, 0.751] | 1.643 [1.530, 1.756] | 4.887 [4.692, 5.082] |  |
| head-my-w3-05 | vericto-enforce | 357 | 100 | 4 | 0.848 [0.815, 0.881] | 1.917 [1.822, 2.011] | 7.473 [5.556, 9.390] |  |
| head-pg-w1-05 | haproxy-tcp | 967 | 10 | 4 | 0.035 [0.034, 0.037] | 0.043 [0.039, 0.046] | 0.082 [0.070, 0.094] |  |
| head-pg-w1-05 | haproxy-tcp | 2900 | 30 | 4 | 0.034 [0.029, 0.038] | 0.045 [0.037, 0.052] | 0.100 [0.092, 0.108] |  |
| head-pg-w1-05 | haproxy-tcp | 4834 | 50 | 4 | 0.032 [0.031, 0.034] | 0.083 [0.078, 0.089] | 0.123 [0.118, 0.129] |  |
| head-pg-w1-05 | haproxy-tcp | 6767 | 70 | 4 | 0.033 [0.030, 0.037] | 0.090 [0.084, 0.096] | 0.137 [0.130, 0.144] |  |
| head-pg-w1-05 | haproxy-tcp | 7734 | 80 | 4 | 0.031 [0.028, 0.034] | 0.088 [0.073, 0.102] | 0.145 [0.123, 0.166] |  |
| head-pg-w1-05 | haproxy-tcp | 8701 | 90 | 4 | 0.033 [0.030, 0.036] | 0.097 [0.087, 0.107] | 0.161 [0.147, 0.175] |  |
| head-pg-w1-05 | haproxy-tcp | 9668 | 100 | 4 | 0.035 [0.034, 0.035] | 0.110 [0.106, 0.114] | 0.174 [0.163, 0.185] |  |
| head-pg-w1-05 | vericto-enforce | 967 | 10 | 4 | 0.084 [0.078, 0.090] | 0.135 [0.122, 0.147] | 1.184 [1.126, 1.243] |  |
| head-pg-w1-05 | vericto-enforce | 2900 | 30 | 4 | 0.080 [0.072, 0.088] | 0.279 [0.246, 0.312] | 1.191 [1.139, 1.242] |  |
| head-pg-w1-05 | vericto-enforce | 4834 | 50 | 4 | 0.081 [0.078, 0.083] | 0.595 [0.584, 0.607] | 1.309 [1.259, 1.360] |  |
| head-pg-w1-05 | vericto-enforce | 6767 | 70 | 4 | 0.088 [0.082, 0.094] | 1.271 [1.125, 1.416] | 13.844 [5.650, 22.037] |  |
| head-pg-w1-05 | vericto-enforce | 7734 | 80 | 4 | 0.090 [0.082, 0.098] | 7.936 [-1.202, 17.074] | 31.732 [19.819, 43.644] | not distinguishable from the direct path |

## Between days (days 1, 2; the pooled rows above use every day)

Day 1 intervals are Student t 95% over its repetitions; a later day's value outside them is flagged.

| Curve | Target | Rate/s | day 1 added p50 / p99 ms (n) | day 2 added p50 / p99 ms (n) | day 1 p50 [95%] | day 1 p99 [95%] | difference p50 / p99 ms | flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | haproxy-tcp | 36 | 0.537 / 0.555 (3) | 0.514 / 0.540 (1) | [0.474, 0.601] | [0.481, 0.628] | -0.023 / -0.015 | within |
| head-my-w3-05 | haproxy-tcp | 107 | 0.453 / 0.493 (3) | 0.392 / 0.466 (1) | [0.402, 0.504] | [0.451, 0.534] | -0.061 / -0.027 | day 2 p50 outside day 1's 95% interval |
| head-my-w3-05 | haproxy-tcp | 178 | 0.463 / 0.471 (3) | 0.480 / 0.494 (1) | [0.349, 0.576] | [0.336, 0.605] | 0.017 / 0.023 | within |
| head-my-w3-05 | haproxy-tcp | 250 | 0.470 / 0.472 (3) | 0.482 / 0.480 (1) | [0.455, 0.485] | [0.441, 0.503] | 0.012 / 0.008 | within |
| head-my-w3-05 | haproxy-tcp | 285 | 0.474 / 0.519 (3) | 0.472 / 0.544 (1) | [0.429, 0.519] | [0.437, 0.601] | -0.002 / 0.025 | within |
| head-my-w3-05 | haproxy-tcp | 321 | 0.433 / 0.491 (3) | 0.418 / 0.456 (1) | [0.409, 0.456] | [0.427, 0.556] | -0.015 / -0.035 | within |
| head-my-w3-05 | haproxy-tcp | 357 | 0.295 / 0.515 (3) | 0.254 / 0.514 (1) | [0.289, 0.300] | [0.439, 0.591] | -0.041 / -0.001 | day 2 p50 outside day 1's 95% interval |
| head-my-w3-05 | vericto-enforce | 36 | 1.205 / 1.325 (3) | 1.158 / 1.300 (1) | [1.068, 1.341] | [1.176, 1.475] | -0.047 / -0.025 | within |
| head-my-w3-05 | vericto-enforce | 107 | 1.093 / 1.544 (3) | 1.098 / 1.642 (1) | [1.018, 1.169] | [1.492, 1.596] | 0.005 / 0.098 | day 2 p99 outside day 1's 95% interval |
| head-my-w3-05 | vericto-enforce | 178 | 1.112 / 1.870 (3) | 1.138 / 1.952 (1) | [0.990, 1.234] | [1.711, 2.029] | 0.026 / 0.082 | within |
| head-my-w3-05 | vericto-enforce | 250 | 1.082 / 2.008 (3) | 1.080 / 2.022 (1) | [1.017, 1.147] | [1.930, 2.086] | -0.002 / 0.014 | within |
| head-my-w3-05 | vericto-enforce | 285 | 1.027 / 2.143 (3) | 0.980 / 2.182 (1) | [0.992, 1.062] | [2.011, 2.275] | -0.047 / 0.039 | day 2 p50 outside day 1's 95% interval |
| head-my-w3-05 | vericto-enforce | 321 | 0.667 / 1.647 (3) | 0.746 / 1.632 (1) | [0.641, 0.692] | [1.433, 1.861] | 0.079 / -0.015 | day 2 p50 outside day 1's 95% interval |
| head-my-w3-05 | vericto-enforce | 357 | 0.842 / 1.891 (3) | 0.866 / 1.994 (1) | [0.790, 0.894] | [1.803, 1.978] | 0.024 / 0.103 | day 2 p99 outside day 1's 95% interval |
| head-pg-w1-05 | haproxy-tcp | 967 | 0.035 / 0.042 (3) | 0.036 / 0.044 (1) | [0.033, 0.037] | [0.036, 0.049] | 0.001 / 0.002 | within |
| head-pg-w1-05 | haproxy-tcp | 2900 | 0.033 / 0.044 (3) | 0.034 / 0.048 (1) | [0.026, 0.041] | [0.031, 0.056] | 0.001 / 0.004 | within |
| head-pg-w1-05 | haproxy-tcp | 4834 | 0.032 / 0.082 (3) | 0.033 / 0.086 (1) | [0.030, 0.034] | [0.073, 0.092] | 0.001 / 0.004 | within |
| head-pg-w1-05 | haproxy-tcp | 6767 | 0.033 / 0.089 (3) | 0.034 / 0.092 (1) | [0.026, 0.040] | [0.079, 0.099] | 0.001 / 0.003 | within |
| head-pg-w1-05 | haproxy-tcp | 7734 | 0.030 / 0.085 (3) | 0.033 / 0.096 (1) | [0.025, 0.036] | [0.063, 0.107] | 0.003 / 0.011 | within |
| head-pg-w1-05 | haproxy-tcp | 8701 | 0.033 / 0.097 (3) | 0.033 / 0.099 (1) | [0.028, 0.038] | [0.078, 0.115] | 0.000 / 0.002 | within |
| head-pg-w1-05 | haproxy-tcp | 9668 | 0.035 / 0.109 (3) | 0.034 / 0.112 (1) | [0.033, 0.036] | [0.102, 0.116] | -0.001 / 0.003 | within |
| head-pg-w1-05 | vericto-enforce | 967 | 0.082 / 0.132 (3) | 0.090 / 0.142 (1) | [0.080, 0.084] | [0.114, 0.151] | 0.008 / 0.010 | day 2 p50 outside day 1's 95% interval |
| head-pg-w1-05 | vericto-enforce | 2900 | 0.080 / 0.276 (3) | 0.080 / 0.288 (1) | [0.065, 0.095] | [0.216, 0.336] | 0.000 / 0.012 | within |
| head-pg-w1-05 | vericto-enforce | 4834 | 0.081 / 0.595 (3) | 0.080 / 0.596 (1) | [0.075, 0.086] | [0.573, 0.617] | -0.001 / 0.001 | within |
| head-pg-w1-05 | vericto-enforce | 6767 | 0.086 / 1.225 (3) | 0.093 / 1.407 (1) | [0.083, 0.090] | [1.190, 1.261] | 0.007 / 0.182 | day 2 p50 outside day 1's 95% interval; day 2 p99 outside day 1's 95% interval |
| head-pg-w1-05 | vericto-enforce | 7734 | 0.088 / 5.827 (3) | 0.096 / 14.264 (1) | [0.078, 0.098] | [-6.034, 17.687] | 0.008 / 8.437 | within |

## Every cell

| Cell | Status | Achieved/s | p50 ms | p99 ms | p99.9 ms | max ms | proxy vCPU | max aggregate Mbps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sat-pg-w1-05.vericto-enforce.c1.rep1 | ok | 5971.1 | 0.161 | 0.225 | 1.167 | 7.947 | 0.337 | 88.1 |
| sat-pg-w1-05.vericto-enforce.c2.rep1 | ok | 8541.0 | 0.169 | 0.486 | 23.280 | 34.315 | 0.500 | 123.8 |
| sat-pg-w1-05.vericto-enforce.c4.rep1 | ok | 9472.0 | 0.234 | 0.823 | 41.388 | 47.261 | 0.500 | 136.2 |
| sat-pg-w1-05.vericto-enforce.c8.rep1 | ok | 9667.7 | 0.384 | 2.635 | 56.993 | 63.093 | 0.500 | 208.6 |
| validate-generator-pg.direct.r1000.rep1 | ok | 1000 | 0.756 | 477.695 | 997.375 | 1063.935 | - | 16.9 |
| validate-generator-pg.direct.r1000.rep2 | ok | 1000 | 0.752 | 479.743 | 999.423 | 1063.935 | - | 71.7 |
| head-pg-w1-05.vericto-enforce.r50.rep0.netprobe | ok | 47.6 | 0.558 | 0.742 | 0.776 | 0.776 | 0.007 | 1.4 |
| head-pg-w1-05.haproxy-tcp.r6767.4.rep1 | ok | 6765.3 | 0.323 | 0.479 | 0.610 | 126.262 | 0.136 | 169.2 |
| head-pg-w1-05.vericto-enforce.r6767.4.rep1 | ok | 6754.1 | 0.375 | 1.598 | 10.379 | 150.263 | 0.433 | 98.4 |
| head-pg-w1-05.direct.r6767.4.rep1 | ok | 6770.1 | 0.287 | 0.385 | 0.471 | 124.560 | - | 59.8 |
| head-pg-w1-05.vericto-enforce.r7734.2.rep1 | ok | 7725.8 | 0.375 | 2.688 | 25.621 | 119.990 | 0.479 | 184.9 |
| head-pg-w1-05.direct.r7734.2.rep1 | ok | 7727.2 | 0.291 | 0.416 | 0.504 | 187.892 | - | 67.4 |
| head-pg-w1-05.haproxy-tcp.r7734.2.rep1 | ok | 7734.6 | 0.319 | 0.491 | 0.630 | 218.696 | 0.152 | 109.8 |
| head-pg-w1-05.direct.r2900.3.rep1 | ok | 2898.2 | 0.299 | 0.349 | 0.416 | 170.145 | - | 98.3 |
| head-pg-w1-05.haproxy-tcp.r2900.3.rep1 | ok | 2901.1 | 0.335 | 0.397 | 0.517 | 243.590 | 0.063 | 42.5 |
| head-pg-w1-05.vericto-enforce.r2900.3.rep1 | ok | 2901.7 | 0.385 | 0.648 | 1.606 | 139.705 | 0.208 | 103.9 |
| head-pg-w1-05.direct.r966.8.rep1 | ok | 968.4 | 0.318 | 0.368 | 0.425 | 106.454 | - | 72.9 |
| head-pg-w1-05.vericto-enforce.r966.8.rep1 | ok | 964.9 | 0.400 | 0.497 | 1.628 | 157.913 | 0.077 | 17.6 |
| head-pg-w1-05.haproxy-tcp.r966.8.rep1 | ok | 966.9 | 0.352 | 0.410 | 0.499 | 131.346 | 0.024 | 61.8 |
| head-pg-w1-05.haproxy-tcp.r8700.9.rep1 | ok | 8698.1 | 0.324 | 0.531 | 0.687 | 114.793 | 0.176 | 201.8 |
| head-pg-w1-05.direct.r8700.9.rep1 | ok | 8695.4 | 0.289 | 0.427 | 0.518 | 74.432 | - | 75.8 |
| head-pg-w1-05.vericto-enforce.r8700.9.rep1 | saturated (achieved rate below 99% of offered) | 8596.0 | 635.018 | 9926.084 | 10234.593 | 10368.233 | 0.500 | 204.4 |
| head-pg-w1-05.vericto-enforce.r4833.9.rep1 | ok | 4830.2 | 0.376 | 0.949 | 1.718 | 91.381 | 0.323 | 145.0 |
| head-pg-w1-05.haproxy-tcp.r4833.9.rep1 | ok | 4832.4 | 0.328 | 0.448 | 0.574 | 138.902 | 0.102 | 69.8 |
| head-pg-w1-05.direct.r4833.9.rep1 | ok | 4834.2 | 0.296 | 0.364 | 0.451 | 133.840 | - | 116.3 |
| head-pg-w1-05.haproxy-tcp.r9667.7.rep1 | ok | 9668.1 | 0.323 | 0.548 | 0.710 | 139.168 | 0.190 | 209.3 |
| head-pg-w1-05.vericto-enforce.r9667.7.rep1 | saturated (achieved rate below 99% of offered) | 8560.3 | 30357.621 | 67698.527 | 68749.075 | 68911.084 | 0.500 | 139.1 |
| head-pg-w1-05.direct.r9667.7.rep1 | ok | 9662.7 | 0.288 | 0.440 | 0.541 | 95.308 | - | 160.2 |
| head-pg-w1-05.vericto-enforce.r4833.9.rep2 | ok | 4835.7 | 0.375 | 0.966 | 1.779 | 158.845 | 0.318 | 146.3 |
| head-pg-w1-05.direct.r4833.9.rep2 | ok | 4831.9 | 0.296 | 0.364 | 0.452 | 176.439 | - | 42.8 |
| head-pg-w1-05.haproxy-tcp.r4833.9.rep2 | ok | 4834.7 | 0.329 | 0.449 | 0.577 | 107.704 | 0.102 | 139.7 |
| head-pg-w1-05.direct.r8700.9.rep2 | ok | 8695.5 | 0.289 | 0.425 | 0.516 | 122.300 | - | 146.9 |
| head-pg-w1-05.haproxy-tcp.r8700.9.rep2 | ok | 8703.4 | 0.322 | 0.522 | 0.672 | 138.919 | 0.171 | 124.0 |
| head-pg-w1-05.vericto-enforce.r8700.9.rep2 | saturated (achieved rate below 99% of offered) | 8545.6 | 317.415 | 14535.138 | 15025.194 | 15148.858 | 0.500 | 191.8 |
| head-pg-w1-05.direct.r2900.3.rep2 | ok | 2892.6 | 0.301 | 0.351 | 0.418 | 139.191 | - | 103.5 |
| head-pg-w1-05.vericto-enforce.r2900.3.rep2 | ok | 2893.1 | 0.381 | 0.629 | 1.600 | 98.295 | 0.201 | 43.1 |
| head-pg-w1-05.haproxy-tcp.r2900.3.rep2 | ok | 2904.5 | 0.335 | 0.396 | 0.518 | 137.043 | 0.064 | 111.6 |
| head-pg-w1-05.haproxy-tcp.r966.8.rep2 | ok | 970.2 | 0.351 | 0.410 | 0.505 | 138.707 | 0.025 | 80.0 |
| head-pg-w1-05.direct.r966.8.rep2 | ok | 967.1 | 0.315 | 0.365 | 0.418 | 114.520 | - | 10.7 |
| head-pg-w1-05.vericto-enforce.r966.8.rep2 | ok | 967.1 | 0.396 | 0.492 | 1.636 | 121.448 | 0.075 | 79.4 |
| head-pg-w1-05.vericto-enforce.r7734.2.rep2 | ok | 7732.7 | 0.384 | 11.666 | 35.129 | 119.771 | 0.494 | 183.8 |
| head-pg-w1-05.haproxy-tcp.r7734.2.rep2 | ok | 7738.1 | 0.324 | 0.504 | 0.655 | 157.802 | 0.156 | 110.0 |
| head-pg-w1-05.direct.r7734.2.rep2 | ok | 7729.1 | 0.292 | 0.413 | 0.498 | 132.089 | - | 139.8 |
| head-pg-w1-05.haproxy-tcp.r6767.4.rep2 | ok | 6762.0 | 0.325 | 0.485 | 0.618 | 109.359 | 0.138 | 167.0 |
| head-pg-w1-05.vericto-enforce.r6767.4.rep2 | ok | 6761.4 | 0.380 | 1.639 | 14.289 | 208.321 | 0.443 | 99.7 |
| head-pg-w1-05.direct.r6767.4.rep2 | ok | 6767.6 | 0.294 | 0.398 | 0.485 | 122.522 | - | 128.3 |
| head-pg-w1-05.vericto-enforce.r9667.7.rep2 | saturated (achieved rate below 99% of offered) | 8630.7 | 28122.458 | 64255.741 | 65802.077 | 66055.254 | 0.500 | 201.6 |
| head-pg-w1-05.direct.r9667.7.rep2 | ok | 9651.6 | 0.288 | 0.437 | 0.535 | 88.990 | - | 83.7 |
| head-pg-w1-05.haproxy-tcp.r9667.7.rep2 | ok | 9670.2 | 0.323 | 0.549 | 0.719 | 105.084 | 0.190 | 204.5 |
| head-pg-w1-05.direct.r8700.9.rep3 | ok | 8694.5 | 0.290 | 0.429 | 0.521 | 134.269 | - | 150.8 |
| head-pg-w1-05.haproxy-tcp.r8700.9.rep3 | ok | 8692.1 | 0.321 | 0.518 | 0.672 | 75.560 | 0.172 | 124.2 |
| head-pg-w1-05.vericto-enforce.r8700.9.rep3 | ok | 8700.7 | 16.626 | 86.495 | 122.952 | 179.848 | 0.500 | 195.7 |
| head-pg-w1-05.direct.r4833.9.rep3 | ok | 4829.9 | 0.293 | 0.361 | 0.448 | 123.532 | - | 112.6 |
| head-pg-w1-05.vericto-enforce.r4833.9.rep3 | ok | 4839.6 | 0.376 | 0.959 | 1.753 | 130.641 | 0.321 | 71.5 |
| head-pg-w1-05.haproxy-tcp.r4833.9.rep3 | ok | 4823.9 | 0.324 | 0.439 | 0.567 | 137.256 | 0.100 | 139.4 |
| head-pg-w1-05.haproxy-tcp.r7734.2.rep3 | ok | 7726.4 | 0.321 | 0.496 | 0.634 | 100.413 | 0.154 | 176.6 |
| head-pg-w1-05.direct.r7734.2.rep3 | ok | 7730.4 | 0.290 | 0.407 | 0.491 | 120.990 | - | 67.5 |
| head-pg-w1-05.vericto-enforce.r7734.2.rep3 | ok | 7728.6 | 0.379 | 4.362 | 26.693 | 128.996 | 0.487 | 188.6 |
| head-pg-w1-05.vericto-enforce.r6767.4.rep3 | ok | 6759.8 | 0.375 | 1.612 | 11.007 | 120.541 | 0.436 | 169.6 |
| head-pg-w1-05.haproxy-tcp.r6767.4.rep3 | ok | 6770.7 | 0.322 | 0.477 | 0.609 | 130.004 | 0.136 | 96.8 |
| head-pg-w1-05.direct.r6767.4.rep3 | ok | 6756.8 | 0.290 | 0.390 | 0.475 | 133.800 | - | 130.9 |
| head-pg-w1-05.haproxy-tcp.r966.8.rep3 | ok | 965.9 | 0.349 | 0.404 | 0.505 | 121.967 | 0.024 | 87.5 |
| head-pg-w1-05.vericto-enforce.r966.8.rep3 | ok | 963.2 | 0.397 | 0.505 | 1.562 | 135.870 | 0.077 | 17.3 |
| head-pg-w1-05.direct.r966.8.rep3 | ok | 965.0 | 0.314 | 0.364 | 0.428 | 155.232 | - | 76.4 |
| head-pg-w1-05.vericto-enforce.r2900.3.rep3 | ok | 2897.6 | 0.376 | 0.604 | 1.577 | 114.635 | 0.196 | 114.1 |
| head-pg-w1-05.direct.r2900.3.rep3 | ok | 2893.2 | 0.302 | 0.353 | 0.421 | 168.070 | - | 25.7 |
| head-pg-w1-05.haproxy-tcp.r2900.3.rep3 | ok | 2898.0 | 0.332 | 0.391 | 0.514 | 123.972 | 0.063 | 109.2 |
| head-pg-w1-05.direct.r9667.7.rep3 | ok | 9658.0 | 0.286 | 0.432 | 0.529 | 103.415 | - | 84.0 |
| head-pg-w1-05.haproxy-tcp.r9667.7.rep3 | ok | 9668.9 | 0.320 | 0.539 | 0.700 | 117.199 | 0.189 | 137.6 |
| head-pg-w1-05.vericto-enforce.r9667.7.rep3 | saturated (achieved rate below 99% of offered) | 7658.1 | 59061.763 | 109727.763 | 111170.284 | 111484.400 | 0.500 | 199.2 |
| head-pg-w1-05.vericto-enforce.r8700.9.rep3.rerun | ok | 8694.2 | 0.429 | 52.960 | 76.965 | 104.707 | 0.500 | 126.6 |
| head-my-w3-05.vericto-enforce.r35.7.rep0.netprobe | ok | 35.7 | 3.979 | 4.611 | 5.255 | 5.255 | 0.040 | 62.3 |
| head-my-w3-05.vericto-enforce.r35.7.rep1 | ok | 35.7 | 4.013 | 4.703 | 5.779 | 11.271 | 0.042 | 62.8 |
| head-my-w3-05.direct.r35.7.rep1 | ok | 35.7 | 2.755 | 3.329 | 3.479 | 4.003 | - | 44.5 |
| head-my-w3-05.haproxy-tcp.r35.7.rep1 | ok | 35.7 | 3.309 | 3.909 | 4.215 | 14.887 | 0.012 | 70.2 |
| head-my-w3-05.direct.r320.9.rep1 | ok | 320.9 | 2.585 | 3.175 | 3.339 | 4.559 | - | 332.8 |
| head-my-w3-05.haproxy-tcp.r320.9.rep1 | ok | 320.9 | 3.021 | 3.693 | 3.961 | 12.695 | 0.101 | 564.9 |
| head-my-w3-05.vericto-enforce.r320.9.rep1 | ok | 320.9 | 3.249 | 4.911 | 8.163 | 17.839 | 0.322 | 564.8 |
| head-my-w3-05.haproxy-tcp.r107.rep1 | ok | 107 | 3.177 | 3.777 | 4.079 | 8.295 | 0.034 | 184.4 |
| head-my-w3-05.vericto-enforce.r107.rep1 | ok | 107 | 3.829 | 4.803 | 6.151 | 13.767 | 0.113 | 201.1 |
| head-my-w3-05.direct.r107.rep1 | ok | 107 | 2.701 | 3.271 | 3.385 | 4.447 | - | 122.7 |
| head-my-w3-05.haproxy-tcp.r285.3.rep1 | ok | 285.3 | 3.041 | 3.663 | 3.887 | 6.831 | 0.090 | 490.4 |
| head-my-w3-05.direct.r285.3.rep1 | ok | 285.3 | 2.585 | 3.177 | 3.363 | 4.231 | - | 310.9 |
| head-my-w3-05.vericto-enforce.r285.3.rep1 | ok | 285.3 | 3.613 | 5.287 | 7.883 | 16.543 | 0.284 | 503.8 |
| head-my-w3-05.vericto-enforce.r178.3.rep1 | ok | 178.3 | 3.779 | 5.127 | 6.303 | 16.607 | 0.188 | 308.7 |
| head-my-w3-05.haproxy-tcp.r178.3.rep1 | ok | 178.3 | 3.101 | 3.685 | 3.949 | 12.919 | 0.056 | 318.9 |
| head-my-w3-05.direct.r178.3.rep1 | ok | 178.3 | 2.647 | 3.235 | 3.443 | 4.823 | - | 192.1 |
| head-my-w3-05.direct.r249.6.rep1 | ok | 249.6 | 2.593 | 3.183 | 3.363 | 4.795 | - | 259.2 |
| head-my-w3-05.vericto-enforce.r249.6.rep1 | ok | 249.6 | 3.691 | 5.219 | 7.595 | 17.007 | 0.258 | 443.6 |
| head-my-w3-05.haproxy-tcp.r249.6.rep1 | ok | 249.6 | 3.069 | 3.669 | 3.941 | 6.751 | 0.079 | 429.0 |
| head-my-w3-05.vericto-enforce.r356.6.rep1 | ok | 356.6 | 3.365 | 5.091 | 11.319 | 19.631 | 0.364 | 615.4 |
| head-my-w3-05.direct.r356.6.rep1 | ok | 356.6 | 2.533 | 3.205 | 3.373 | 5.707 | - | 381.2 |
| head-my-w3-05.haproxy-tcp.r356.6.rep1 | ok | 356.6 | 2.825 | 3.685 | 3.927 | 223.103 | 0.113 | 612.6 |
| head-my-w3-05.direct.r178.3.rep2 | ok | 178.3 | 2.619 | 3.199 | 3.353 | 4.851 | - | 185.6 |
| head-my-w3-05.haproxy-tcp.r178.3.rep2 | ok | 178.3 | 3.131 | 3.731 | 4.037 | 6.759 | 0.057 | 317.4 |
| head-my-w3-05.vericto-enforce.r178.3.rep2 | ok | 178.3 | 3.767 | 5.119 | 6.719 | 15.111 | 0.182 | 308.4 |
| head-my-w3-05.haproxy-tcp.r35.7.rep2 | ok | 35.7 | 3.259 | 3.863 | 4.123 | 12.551 | 0.012 | 73.9 |
| head-my-w3-05.vericto-enforce.r35.7.rep2 | ok | 35.7 | 3.899 | 4.599 | 5.603 | 9.823 | 0.040 | 71.2 |
| head-my-w3-05.direct.r35.7.rep2 | ok | 35.7 | 2.751 | 3.341 | 3.597 | 4.395 | - | 37.8 |
| head-my-w3-05.haproxy-tcp.r285.3.rep2 | ok | 285.3 | 3.045 | 3.671 | 3.873 | 6.539 | 0.090 | 501.1 |
| head-my-w3-05.direct.r285.3.rep2 | ok | 285.3 | 2.571 | 3.151 | 3.347 | 4.219 | - | 307.9 |
| head-my-w3-05.vericto-enforce.r285.3.rep2 | ok | 285.3 | 3.611 | 5.355 | 7.779 | 16.511 | 0.286 | 493.0 |
| head-my-w3-05.vericto-enforce.r249.6.rep2 | ok | 249.6 | 3.691 | 5.211 | 7.795 | 16.911 | 0.254 | 447.7 |
| head-my-w3-05.haproxy-tcp.r249.6.rep2 | ok | 249.6 | 3.065 | 3.659 | 3.923 | 13.167 | 0.079 | 443.1 |
| head-my-w3-05.direct.r249.6.rep2 | ok | 249.6 | 2.595 | 3.197 | 3.397 | 5.247 | - | 259.0 |
| head-my-w3-05.direct.r320.9.rep2 | ok | 320.9 | 2.609 | 3.231 | 3.407 | 4.287 | - | 345.5 |
| head-my-w3-05.vericto-enforce.r320.9.rep2 | ok | 320.9 | 3.267 | 4.871 | 8.263 | 17.199 | 0.320 | 562.3 |
| head-my-w3-05.haproxy-tcp.r320.9.rep2 | ok | 320.9 | 3.049 | 3.721 | 3.931 | 6.991 | 0.101 | 551.5 |
| head-my-w3-05.vericto-enforce.r107.rep2 | ok | 107 | 3.823 | 4.823 | 5.995 | 13.703 | 0.110 | 201.9 |
| head-my-w3-05.direct.r107.rep2 | ok | 107 | 2.743 | 3.291 | 3.581 | 4.871 | - | 125.6 |
| head-my-w3-05.haproxy-tcp.r107.rep2 | ok | 107 | 3.191 | 3.789 | 4.049 | 9.751 | 0.034 | 185.1 |
| head-my-w3-05.direct.r356.6.rep2 | ok | 356.6 | 2.537 | 3.209 | 3.381 | 4.267 | - | 387.7 |
| head-my-w3-05.haproxy-tcp.r356.6.rep2 | ok | 356.6 | 2.833 | 3.743 | 4.019 | 5.599 | 0.112 | 623.4 |
| head-my-w3-05.vericto-enforce.r356.6.rep2 | ok | 356.6 | 3.365 | 5.067 | 9.079 | 17.055 | 0.349 | 615.5 |
| head-my-w3-05.haproxy-tcp.r178.3.rep3 | ok | 178.3 | 3.111 | 3.703 | 3.929 | 5.935 | 0.057 | 320.3 |
| head-my-w3-05.vericto-enforce.r178.3.rep3 | ok | 178.3 | 3.745 | 5.071 | 6.331 | 14.727 | 0.182 | 308.3 |
| head-my-w3-05.direct.r178.3.rep3 | ok | 178.3 | 2.689 | 3.273 | 3.467 | 4.263 | - | 185.5 |
| head-my-w3-05.haproxy-tcp.r320.9.rep3 | ok | 320.9 | 3.029 | 3.697 | 3.931 | 7.555 | 0.101 | 563.7 |
| head-my-w3-05.direct.r320.9.rep3 | ok | 320.9 | 2.607 | 3.231 | 3.511 | 4.363 | - | 332.8 |
| head-my-w3-05.vericto-enforce.r320.9.rep3 | ok | 320.9 | 3.285 | 4.795 | 8.311 | 17.535 | 0.328 | 570.9 |
| head-my-w3-05.vericto-enforce.r249.6.rep3 | ok | 249.6 | 3.651 | 5.171 | 7.867 | 16.815 | 0.244 | 439.5 |
| head-my-w3-05.haproxy-tcp.r249.6.rep3 | ok | 249.6 | 3.063 | 3.665 | 3.903 | 13.223 | 0.079 | 429.0 |
| head-my-w3-05.direct.r249.6.rep3 | ok | 249.6 | 2.599 | 3.197 | 3.407 | 4.077 | - | 273.8 |
| head-my-w3-05.direct.r107.rep3 | ok | 107 | 2.723 | 3.275 | 3.495 | 5.227 | - | 125.6 |
| head-my-w3-05.vericto-enforce.r107.rep3 | ok | 107 | 3.795 | 4.843 | 6.415 | 14.271 | 0.109 | 185.8 |
| head-my-w3-05.haproxy-tcp.r107.rep3 | ok | 107 | 3.159 | 3.749 | 4.001 | 5.899 | 0.035 | 203.4 |
| head-my-w3-05.vericto-enforce.r35.7.rep3 | ok | 35.7 | 3.967 | 4.679 | 5.943 | 13.599 | 0.041 | 77.6 |
| head-my-w3-05.direct.r35.7.rep3 | ok | 35.7 | 2.759 | 3.335 | 3.491 | 3.937 | - | 37.7 |
| head-my-w3-05.haproxy-tcp.r35.7.rep3 | ok | 35.7 | 3.309 | 3.897 | 4.175 | 12.671 | 0.012 | 75.7 |
| head-my-w3-05.direct.r285.3.rep3 | ok | 285.3 | 2.601 | 3.193 | 3.383 | 4.107 | - | 305.2 |
| head-my-w3-05.haproxy-tcp.r285.3.rep3 | ok | 285.3 | 3.093 | 3.745 | 4.027 | 4.983 | 0.090 | 490.4 |
| head-my-w3-05.vericto-enforce.r285.3.rep3 | ok | 285.3 | 3.613 | 5.307 | 7.799 | 16.143 | 0.286 | 504.7 |
| head-my-w3-05.haproxy-tcp.r356.6.rep3 | ok | 356.6 | 2.835 | 3.739 | 4.027 | 5.227 | 0.113 | 629.5 |
| head-my-w3-05.vericto-enforce.r356.6.rep3 | ok | 356.6 | 3.405 | 5.135 | 11.231 | 20.463 | 0.370 | 616.2 |
| head-my-w3-05.direct.r356.6.rep3 | ok | 356.6 | 2.539 | 3.207 | 3.367 | 4.863 | - | 385.0 |
| head-pg-w1-05-day2.vericto-enforce.r50.rep0.netprobe | ok | 49.4 | 0.573 | 0.752 | 0.901 | 0.901 | 0.007 | 1.2 |
| head-pg-w1-05-day2.vericto-enforce.r966.8.rep1 | ok | 962.0 | 0.413 | 0.521 | 1.609 | 103.535 | 0.078 | 17.4 |
| head-pg-w1-05-day2.direct.r966.8.rep1 | ok | 963.8 | 0.323 | 0.379 | 0.426 | 110.983 | - | 41.1 |
| head-pg-w1-05-day2.haproxy-tcp.r966.8.rep1 | ok | 965.4 | 0.359 | 0.423 | 0.516 | 117.213 | 0.025 | 68.6 |
| head-pg-w1-05-day2.direct.r7734.2.rep1 | ok | 7722.9 | 0.295 | 0.422 | 0.509 | 116.694 | - | 67.6 |
| head-pg-w1-05-day2.haproxy-tcp.r7734.2.rep1 | ok | 7725.0 | 0.328 | 0.518 | 0.661 | 152.328 | 0.160 | 174.1 |
| head-pg-w1-05-day2.vericto-enforce.r7734.2.rep1 | ok | 7733.5 | 0.391 | 14.686 | 41.485 | 121.235 | 0.496 | 179.4 |
| head-pg-w1-05-day2.haproxy-tcp.r8700.9.rep1 | ok | 8686.1 | 0.327 | 0.540 | 0.703 | 104.518 | 0.178 | 123.8 |
| head-pg-w1-05-day2.vericto-enforce.r8700.9.rep1 | saturated (achieved rate below 99% of offered) | 8474.6 | 3721.003 | 19999.116 | 20780.101 | 20876.190 | 0.500 | 195.1 |
| head-pg-w1-05-day2.direct.r8700.9.rep1 | ok | 8704.8 | 0.294 | 0.441 | 0.536 | 103.666 | - | 150.6 |
| head-pg-w1-05-day2.haproxy-tcp.r6767.4.rep1 | ok | 6759.2 | 0.330 | 0.498 | 0.636 | 113.536 | 0.142 | 96.3 |
| head-pg-w1-05-day2.direct.r6767.4.rep1 | ok | 6769.9 | 0.296 | 0.406 | 0.494 | 126.867 | - | 135.3 |
| head-pg-w1-05-day2.vericto-enforce.r6767.4.rep1 | ok | 6754.4 | 0.389 | 1.813 | 21.625 | 119.944 | 0.463 | 165.4 |
| head-pg-w1-05-day2.vericto-enforce.r4833.9.rep1 | ok | 4830.0 | 0.380 | 0.969 | 1.799 | 129.135 | 0.321 | 72.0 |
| head-pg-w1-05-day2.haproxy-tcp.r4833.9.rep1 | ok | 4836.2 | 0.333 | 0.459 | 0.587 | 131.959 | 0.104 | 137.1 |
| head-pg-w1-05-day2.direct.r4833.9.rep1 | ok | 4827.0 | 0.300 | 0.373 | 0.460 | 144.601 | - | 120.1 |
| head-pg-w1-05-day2.direct.r2900.3.rep1 | ok | 2889.7 | 0.305 | 0.357 | 0.427 | 239.285 | - | 26.1 |
| head-pg-w1-05-day2.vericto-enforce.r2900.3.rep1 | ok | 2905.9 | 0.385 | 0.645 | 1.661 | 119.037 | 0.203 | 111.5 |
| head-pg-w1-05-day2.haproxy-tcp.r2900.3.rep1 | ok | 2901.3 | 0.339 | 0.405 | 0.532 | 149.614 | 0.065 | 110.7 |
| head-pg-w1-05-day2.vericto-enforce.r9667.7.rep1 | saturated (achieved rate below 99% of offered) | 8430.7 | 34171.656 | 76843.665 | 78125.490 | 78387.309 | 0.500 | 141.1 |
| head-pg-w1-05-day2.direct.r9667.7.rep1 | ok | 9655.3 | 0.293 | 0.455 | 0.559 | 93.851 | - | 158.7 |
| head-pg-w1-05-day2.haproxy-tcp.r9667.7.rep1 | ok | 9661.3 | 0.327 | 0.567 | 0.731 | 121.878 | 0.196 | 208.9 |
| head-my-w3-05-day2.vericto-enforce.r35.7.rep0.netprobe | ok | 35.7 | 3.973 | 4.655 | 5.835 | 5.835 | 0.040 | 62.4 |
| head-my-w3-05-day2.vericto-enforce.r178.3.rep1 | ok | 178.3 | 3.819 | 5.215 | 6.087 | 15.247 | 0.183 | 308.2 |
| head-my-w3-05-day2.direct.r178.3.rep1 | ok | 178.3 | 2.681 | 3.263 | 3.483 | 4.223 | - | 262.8 |
| head-my-w3-05-day2.haproxy-tcp.r178.3.rep1 | ok | 178.3 | 3.161 | 3.757 | 4.037 | 13.655 | 0.056 | 318.4 |
| head-my-w3-05-day2.direct.r320.9.rep1 | ok | 320.9 | 2.631 | 3.267 | 3.443 | 4.515 | - | 333.0 |
| head-my-w3-05-day2.haproxy-tcp.r320.9.rep1 | ok | 320.9 | 3.049 | 3.723 | 3.965 | 6.379 | 0.101 | 566.5 |
| head-my-w3-05-day2.vericto-enforce.r320.9.rep1 | ok | 320.9 | 3.377 | 4.899 | 8.511 | 18.511 | 0.332 | 562.1 |
| head-my-w3-05-day2.haproxy-tcp.r107.rep1 | ok | 107 | 3.193 | 3.791 | 4.199 | 5.459 | 0.034 | 184.4 |
| head-my-w3-05-day2.vericto-enforce.r107.rep1 | ok | 107 | 3.899 | 4.967 | 6.303 | 14.991 | 0.116 | 199.0 |
| head-my-w3-05-day2.direct.r107.rep1 | ok | 107 | 2.801 | 3.325 | 3.479 | 5.959 | - | 124.7 |
| head-my-w3-05-day2.haproxy-tcp.r285.3.rep1 | ok | 285.3 | 3.099 | 3.769 | 4.619 | 7.307 | 0.090 | 490.4 |
| head-my-w3-05-day2.direct.r285.3.rep1 | ok | 285.3 | 2.627 | 3.225 | 3.471 | 4.647 | - | 313.4 |
| head-my-w3-05-day2.vericto-enforce.r285.3.rep1 | ok | 285.3 | 3.607 | 5.407 | 7.675 | 16.375 | 0.293 | 505.8 |
| head-my-w3-05-day2.vericto-enforce.r249.6.rep1 | ok | 249.6 | 3.723 | 5.271 | 7.631 | 17.903 | 0.254 | 432.0 |
| head-my-w3-05-day2.haproxy-tcp.r249.6.rep1 | ok | 249.6 | 3.125 | 3.729 | 3.957 | 6.931 | 0.079 | 440.8 |
| head-my-w3-05-day2.direct.r249.6.rep1 | ok | 249.6 | 2.643 | 3.249 | 3.653 | 4.735 | - | 271.9 |
| head-my-w3-05-day2.direct.r35.7.rep1 | ok | 35.7 | 2.805 | 3.379 | 3.497 | 3.789 | - | 37.7 |
| head-my-w3-05-day2.vericto-enforce.r35.7.rep1 | ok | 35.7 | 3.963 | 4.679 | 6.171 | 16.415 | 0.040 | 80.6 |
| head-my-w3-05-day2.haproxy-tcp.r35.7.rep1 | ok | 35.7 | 3.319 | 3.919 | 4.599 | 1789.951 | 0.012 | 77.5 |
| head-my-w3-05-day2.vericto-enforce.r356.6.rep1 | ok | 356.6 | 3.447 | 5.255 | 11.831 | 19.791 | 0.371 | 618.0 |
| head-my-w3-05-day2.direct.r356.6.rep1 | ok | 356.6 | 2.581 | 3.261 | 3.447 | 4.563 | - | 389.3 |
| head-my-w3-05-day2.haproxy-tcp.r356.6.rep1 | ok | 356.6 | 2.835 | 3.775 | 4.073 | 11.855 | 0.112 | 612.8 |
| h2-pg-w1-2x05.vericto-enforce.r50.rep0.netprobe | ok | 47.1 | 0.616 | 1.274 | 1.388 | 1.388 | 0.009 | 1.6 |
| h2-pg-w1-2x05.vericto-enforce.r5800.6.rep1 | ok | 5796.0 | 0.382 | 0.698 | 1.610 | 219.870 | 0.400 | 85.5 |
| h2-pg-w1-2x05.direct.r5800.6.rep1 | ok | 5795.4 | 0.302 | 0.396 | 0.492 | 280.573 | - | 120.2 |
| h2-pg-w1-2x05.direct.r8700.9.rep1 | ok | 8684.2 | 0.300 | 0.451 | 0.555 | 249.147 | - | 148.0 |
| h2-pg-w1-2x05.vericto-enforce.r8700.9.rep1 | ok | 8688.1 | 0.382 | 0.949 | 1.734 | 264.063 | 0.578 | 126.9 |
| h2-pg-w1-2x05.vericto-enforce.r2900.3.rep1 | ok | 2898.1 | 0.394 | 0.531 | 1.530 | 408.745 | 0.226 | 126.0 |
| h2-pg-w1-2x05.direct.r2900.3.rep1 | ok | 2896.3 | 0.309 | 0.364 | 0.448 | 274.278 | - | 105.6 |
| h2-pg-w1-2x05.direct.r11601.2.rep1 | ok | 11590.3 | 0.297 | 0.499 | 0.643 | 206.855 | - | 100.9 |
| h2-pg-w1-2x05.vericto-enforce.r11601.2.rep1 | ok | 11600.1 | 0.393 | 1.413 | 3.166 | 211.827 | 0.770 | 236.9 |
| h2-pg-w1-2x05.vericto-enforce.r14501.5.rep1 | ok | 14483.1 | 0.418 | 1.929 | 5.445 | 350.719 | 0.913 | 282.7 |
| h2-pg-w1-2x05.direct.r14501.5.rep1 | ok | 14491.5 | 0.302 | 0.594 | 0.817 | 191.633 | - | 125.8 |
| h2-pg-w1-2x05.direct.r17401.9.rep1 | ok | 17375.8 | 0.312 | 0.789 | 1.143 | 402.167 | - | 221.3 |
| h2-pg-w1-2x05.vericto-enforce.r17401.9.rep1 | ok | 17386.3 | 8.501 | 68.411 | 116.174 | 333.617 | 1.000 | 324.2 |
| h2-pg-w1-2x05.vericto-enforce.r19335.4.rep1 | saturated (achieved rate below 99% of offered) | 17761.6 | 22353.720 | 52105.850 | 53164.945 | 53340.874 | 1.000 | 265.1 |
| h2-pg-w1-2x05.direct.r19335.4.rep1 | ok | 19298.6 | 0.344 | 1.087 | 1.606 | 132.632 | - | 243.5 |
| h2-pg-w1-2x05.direct.r5800.6.rep2 | ok | 5793.9 | 0.303 | 0.398 | 0.496 | 239.169 | - | 122.6 |
| h2-pg-w1-2x05.vericto-enforce.r5800.6.rep2 | ok | 5792.7 | 0.385 | 0.691 | 1.609 | 223.142 | 0.410 | 84.9 |
| h2-pg-w1-2x05.vericto-enforce.r8700.9.rep2 | ok | 8690.7 | 0.382 | 0.956 | 1.721 | 218.829 | 0.575 | 194.3 |
| h2-pg-w1-2x05.direct.r8700.9.rep2 | ok | 8679.1 | 0.301 | 0.452 | 0.557 | 198.121 | - | 146.4 |
| h2-pg-w1-2x05.direct.r2900.3.rep2 | ok | 2895.4 | 0.309 | 0.365 | 0.453 | 297.405 | - | 29.8 |
| h2-pg-w1-2x05.vericto-enforce.r2900.3.rep2 | ok | 2900.2 | 0.393 | 0.536 | 1.554 | 418.627 | 0.223 | 125.7 |
| h2-pg-w1-2x05.vericto-enforce.r11601.2.rep2 | ok | 11578.0 | 0.392 | 1.308 | 2.887 | 198.602 | 0.764 | 241.7 |
| h2-pg-w1-2x05.direct.r11601.2.rep2 | ok | 11580.1 | 0.299 | 0.503 | 0.647 | 210.281 | - | 100.8 |
| h2-pg-w1-2x05.direct.r14501.5.rep2 | ok | 14486.0 | 0.301 | 0.594 | 0.819 | 390.482 | - | 202.4 |
| h2-pg-w1-2x05.vericto-enforce.r14501.5.rep2 | ok | 14481.5 | 0.417 | 2.012 | 6.484 | 132.635 | 0.918 | 281.0 |
| h2-pg-w1-2x05.vericto-enforce.r17401.9.rep2 | ok | 17369.3 | 0.667 | 26.202 | 37.994 | 149.488 | 1.000 | 251.4 |
| h2-pg-w1-2x05.direct.r17401.9.rep2 | ok | 17376.8 | 0.311 | 0.812 | 104.101 | 254.451 | - | 223.8 |
| h2-pg-w1-2x05.direct.r19335.4.rep2 | ok | 19290.5 | 0.343 | 1.070 | 1.599 | 178.288 | - | 242.7 |
| h2-pg-w1-2x05.vericto-enforce.r19335.4.rep2 | saturated (achieved rate below 99% of offered) | 18329.5 | 6806.677 | 58148.945 | 59603.527 | 59902.981 | 1.000 | 274.2 |
| h2-pg-w1-05.vericto-enforce.r50.rep0.netprobe | ok | 46.8 | 0.571 | 1.232 | 1.333 | 1.333 | 0.007 | 1.7 |
| h2-pg-w1-05.vericto-enforce.r8700.9.rep1 | saturated (achieved rate below 99% of offered) | 8350.1 | 10154.283 | 31497.056 | 32424.456 | 32540.449 | 0.500 | 205.5 |
| h2-pg-w1-05.direct.r8700.9.rep1 | ok | 8686.1 | 0.300 | 0.449 | 0.553 | 407.841 | - | 146.3 |
| h2-pg-w1-05.direct.r2900.3.rep1 | ok | 2892.1 | 0.312 | 0.367 | 0.446 | 414.222 | - | 29.4 |
| h2-pg-w1-05.vericto-enforce.r2900.3.rep1 | ok | 2895.2 | 0.395 | 0.649 | 1.656 | 232.439 | 0.207 | 116.8 |
| h2-pg-w1-05.vericto-enforce.r11601.2.rep1 | saturated (achieved rate below 99% of offered) | 6548.5 | 129162.577 | 199070.753 | 202918.771 | 203327.877 | 0.500 | 198.8 |
| h2-pg-w1-05.direct.r11601.2.rep1 | ok | 11576.3 | 0.299 | 0.502 | 0.654 | 206.473 | - | 101.2 |
| h2-pg-w1-05.direct.r8700.9.rep2 | ok | 8693.1 | 0.301 | 0.451 | 0.554 | 228.804 | - | 149.7 |
| h2-pg-w1-05.vericto-enforce.r8700.9.rep2 | saturated (achieved rate below 99% of offered) | 8467.2 | 5603.538 | 21971.542 | 22866.914 | 22991.731 | 0.500 | 206.2 |
| h2-pg-w1-05.vericto-enforce.r2900.3.rep2 | ok | 2898.6 | 0.397 | 0.648 | 1.662 | 404.936 | 0.216 | 48.8 |
| h2-pg-w1-05.direct.r2900.3.rep2 | ok | 2897.0 | 0.310 | 0.365 | 0.446 | 276.873 | - | 107.0 |
| h2-pg-w1-05.direct.r11601.2.rep2 | ok | 11583.4 | 0.299 | 0.504 | 0.655 | 400.589 | - | 170.5 |
| h2-pg-w1-05.vericto-enforce.r11601.2.rep2 | saturated (achieved rate below 99% of offered) | 6667.7 | 126434.258 | 195154.447 | 198758.979 | 199207.760 | 0.500 | 140.1 |

## Proxy CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S)

| Curve | Target | Size | n | vCPU per 1,000 QPS [95%] | intercept vCPU | USD/month per 1,000 QPS at 70% utilisation |
| --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | vericto-enforce | 0.5 | 16 | 0.0619 [0.0604, 0.0634] | 0.0059 | 2.09 |
| head-pg-w1-05 | vericto-enforce | 0.5 | 16 | 0.0632 [0.0614, 0.0649] | 0.0168 | 2.13 |

## Network traffic (caps: 400 Mbps per component, 800 Mbps aggregate)

Cells aborted by a cap: 0. Per-cell maxima are in traffic.csv; bytes/s per direction over each measured window in traffic_directions.csv.

Bytes per direction at vericto-enforce, highest offered rate of each open-loop curve (saturated cells included; Mbps, window mean):

| Curve | Rate/s | client to proxy | proxy to client | proxy to DB | DB to proxy | telemetry out | proxy total | result bytes per request |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| h2-pg-w1-05 | 11601 | 12.4 | 11.2 | 13.5 | 10.1 | 2.70 | 49.9 | 212 |
| h2-pg-w1-2x05 | 19335 | 27.1 | 22.4 | 27.3 | 22.1 | 5.85 | 104.8 | 155 |
| head-my-w3-05 | 357 | 5.9 | 115.9 | 5.4 | 115.9 | 2.28 | 245.4 | 40625 |
| head-pg-w1-05 | 9668 | 12.8 | 10.9 | 13.3 | 10.4 | 2.78 | 50.2 | 164 |

## Horizontal scaling (P-2tasks): 1 x 0.5, 1 x 1 and 2 x 0.5 vCPU at the same absolute rates

Saturated cells end a curve (never latency). With two tasks the client spreads its connections over both ports; task 1 / task 2 vCPU show whether the load split evenly.

| Engine | Proxy | Rate/s | cells (saturated) | achieved/s | added p50 ms | added p99 ms | task 1 vCPU | task 2 vCPU | task 1 throttled ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pg | 1x0.5 | 2900 | 2 (0) | 2897 | 0.085 | 0.283 | 0.212 | - | 0 |
| pg | 2x0.5 | 2900 | 2 (0) | 2899 | 0.085 | 0.169 | 0.097 | 0.127 | 0 |
| pg | 2x0.5 | 5801 | 2 (0) | 5794 | 0.081 | 0.297 | 0.229 | 0.176 | 0 |
| pg | 1x0.5 | 8701 | 2 (2) | 8409 | - | - | 0.500 | - | 145876 |
| pg | 2x0.5 | 8701 | 2 (0) | 8689 | 0.082 | 0.501 | 0.290 | 0.286 | 0 |
| pg | 1x0.5 | 11601 | 2 (2) | 6608 | - | - | 0.500 | - | 149236 |
| pg | 2x0.5 | 11601 | 2 (0) | 11589 | 0.095 | 0.860 | 0.368 | 0.399 | 113 |
| pg | 2x0.5 | 14502 | 2 (0) | 14482 | 0.116 | 1.377 | 0.452 | 0.464 | 441 |
| pg | 2x0.5 | 17402 | 2 (0) | 17378 | 4.272 | 46.506 | 0.500 | 0.500 | 69116 |
| pg | 2x0.5 | 19335 | 2 (2) | 18046 | - | - | 0.500 | 0.500 | 95757 |

## Generator validation

- validate-generator-pg.direct.r1000.rep1: 5 pauses of 1.0 s every 60.0 s; max 1063.9 ms, p99.9 997.4 ms, fraction above 500 ms 0.0096 (expected 0.0083): PASS
- validate-generator-pg.direct.r1000.rep2: 5 pauses of 1.0 s every 60.0 s; max 1063.9 ms, p99.9 999.4 ms, fraction above 500 ms 0.0097 (expected 0.0083): PASS

## Invalid repetitions (pre-registered rules; kept in the raw data)

- head-pg-w1-05.vericto-enforce.r8700.9.rep3: not steady: p50 drifts 69% from the first to the last third
- head-pg-w1-05.vericto-enforce.r8700.9.rep3.rerun: not steady: p50 drifts 190% from the first to the last third

## Charts

