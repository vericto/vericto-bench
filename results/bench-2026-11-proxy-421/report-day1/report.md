**day 1.**

# vericto-bench report: pub421-day1-pg, pub421-day1-my

| Run | Profile | Topology | Proxy image | Harness commit | Started | Finished |
| --- | --- | --- | --- | --- | --- | --- |
| bench-2026-11-proxy-421-p | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `f041a49d177d` | 2026-10-31T13:42:43.715702+00:00 | 2026-10-31T21:20:58.052441+00:00 |
| bench-2026-11-proxy-421-m | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `f041a49d177d` | 2026-10-31T13:42:41.821712+00:00 | 2026-10-31T20:38:45.259058+00:00 |

Cells: 135 recorded, 131 used, 2 invalid (listed at the end, not used).

## Added latency (open loop, from intended send time; target minus direct, paired)

| Curve | Target | Rate/s | % of S | n | added p50 ms [95%] | added p99 ms [95%] | added p99.9 ms [95%] | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | haproxy-tcp | 36 | 10 | 3 | 0.537 [0.474, 0.601] | 0.555 [0.481, 0.628] | 0.649 [0.377, 0.920] |  |
| head-my-w3-05 | haproxy-tcp | 107 | 30 | 3 | 0.453 [0.402, 0.504] | 0.493 [0.451, 0.534] | 0.556 [0.255, 0.857] |  |
| head-my-w3-05 | haproxy-tcp | 178 | 50 | 3 | 0.463 [0.349, 0.576] | 0.471 [0.336, 0.605] | 0.551 [0.259, 0.843] |  |
| head-my-w3-05 | haproxy-tcp | 250 | 70 | 3 | 0.470 [0.455, 0.485] | 0.472 [0.441, 0.503] | 0.533 [0.430, 0.636] |  |
| head-my-w3-05 | haproxy-tcp | 285 | 80 | 3 | 0.474 [0.429, 0.519] | 0.519 [0.437, 0.601] | 0.565 [0.394, 0.735] |  |
| head-my-w3-05 | haproxy-tcp | 321 | 90 | 3 | 0.433 [0.409, 0.456] | 0.491 [0.427, 0.556] | 0.522 [0.271, 0.773] |  |
| head-my-w3-05 | haproxy-tcp | 357 | 100 | 3 | 0.295 [0.289, 0.300] | 0.515 [0.439, 0.591] | 0.617 [0.478, 0.756] |  |
| head-my-w3-05 | vericto-enforce | 36 | 10 | 3 | 1.205 [1.068, 1.341] | 1.325 [1.176, 1.475] | 2.253 [1.689, 2.816] |  |
| head-my-w3-05 | vericto-enforce | 107 | 30 | 3 | 1.093 [1.018, 1.169] | 1.544 [1.492, 1.596] | 2.700 [2.056, 3.344] |  |
| head-my-w3-05 | vericto-enforce | 178 | 50 | 3 | 1.112 [0.990, 1.234] | 1.870 [1.711, 2.029] | 3.030 [2.307, 3.753] |  |
| head-my-w3-05 | vericto-enforce | 250 | 70 | 3 | 1.082 [1.017, 1.147] | 2.008 [1.930, 2.086] | 4.363 [4.070, 4.656] |  |
| head-my-w3-05 | vericto-enforce | 285 | 80 | 3 | 1.027 [0.992, 1.062] | 2.143 [2.011, 2.275] | 4.456 [4.317, 4.595] |  |
| head-my-w3-05 | vericto-enforce | 321 | 90 | 3 | 0.667 [0.641, 0.692] | 1.647 [1.433, 1.861] | 4.827 [4.757, 4.896] |  |
| head-my-w3-05 | vericto-enforce | 357 | 100 | 3 | 0.842 [0.790, 0.894] | 1.891 [1.803, 1.978] | 7.169 [4.002, 10.337] |  |
| head-pg-w1-05 | haproxy-tcp | 967 | 10 | 3 | 0.035 [0.033, 0.037] | 0.042 [0.036, 0.049] | 0.079 [0.062, 0.096] |  |
| head-pg-w1-05 | haproxy-tcp | 2900 | 30 | 3 | 0.033 [0.026, 0.041] | 0.044 [0.031, 0.056] | 0.098 [0.087, 0.109] |  |
| head-pg-w1-05 | haproxy-tcp | 4834 | 50 | 3 | 0.032 [0.030, 0.034] | 0.082 [0.073, 0.092] | 0.122 [0.115, 0.130] |  |
| head-pg-w1-05 | haproxy-tcp | 6767 | 70 | 3 | 0.033 [0.026, 0.040] | 0.089 [0.079, 0.099] | 0.135 [0.127, 0.143] |  |
| head-pg-w1-05 | haproxy-tcp | 7734 | 80 | 3 | 0.030 [0.025, 0.036] | 0.085 [0.063, 0.107] | 0.142 [0.103, 0.181] |  |
| head-pg-w1-05 | haproxy-tcp | 8701 | 90 | 3 | 0.033 [0.028, 0.038] | 0.097 [0.078, 0.115] | 0.159 [0.136, 0.182] |  |
| head-pg-w1-05 | haproxy-tcp | 9668 | 100 | 3 | 0.035 [0.033, 0.036] | 0.109 [0.102, 0.116] | 0.175 [0.154, 0.195] |  |
| head-pg-w1-05 | vericto-enforce | 967 | 10 | 3 | 0.082 [0.080, 0.084] | 0.132 [0.114, 0.151] | 1.185 [1.074, 1.296] |  |
| head-pg-w1-05 | vericto-enforce | 2900 | 30 | 3 | 0.080 [0.065, 0.095] | 0.276 [0.216, 0.336] | 1.176 [1.132, 1.220] |  |
| head-pg-w1-05 | vericto-enforce | 4834 | 50 | 3 | 0.081 [0.075, 0.086] | 0.595 [0.573, 0.617] | 1.300 [1.224, 1.375] |  |
| head-pg-w1-05 | vericto-enforce | 6767 | 70 | 3 | 0.086 [0.083, 0.090] | 1.225 [1.190, 1.261] | 11.415 [6.216, 16.613] |  |
| head-pg-w1-05 | vericto-enforce | 7734 | 80 | 3 | 0.088 [0.078, 0.098] | 5.827 [-6.034, 17.687] | 28.650 [15.711, 41.589] | not distinguishable from the direct path |

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

## Proxy CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S)

| Curve | Target | Size | n | vCPU per 1,000 QPS [95%] | intercept vCPU | USD/month per 1,000 QPS at 70% utilisation |
| --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | vericto-enforce | 0.5 | 12 | 0.0619 [0.0599, 0.0638] | 0.0057 | 2.09 |
| head-pg-w1-05 | vericto-enforce | 0.5 | 12 | 0.0622 [0.0609, 0.0635] | 0.0186 | 2.10 |

## Network traffic (caps: 400 Mbps per component, 800 Mbps aggregate)

Cells aborted by a cap: 0. Per-cell maxima are in traffic.csv; bytes/s per direction over each measured window in traffic_directions.csv.

Bytes per direction at vericto-enforce, highest offered rate of each open-loop curve (saturated cells included; Mbps, window mean):

| Curve | Rate/s | client to proxy | proxy to client | proxy to DB | DB to proxy | telemetry out | proxy total | result bytes per request |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | 357 | 5.9 | 115.9 | 5.4 | 115.9 | 2.28 | 245.4 | 40625 |
| head-pg-w1-05 | 9668 | 12.8 | 10.9 | 13.3 | 10.4 | 2.78 | 50.2 | 165 |

## Generator validation

- validate-generator-pg.direct.r1000.rep1: 5 pauses of 1.0 s every 60.0 s; max 1063.9 ms, p99.9 997.4 ms, fraction above 500 ms 0.0096 (expected 0.0083): PASS
- validate-generator-pg.direct.r1000.rep2: 5 pauses of 1.0 s every 60.0 s; max 1063.9 ms, p99.9 999.4 ms, fraction above 500 ms 0.0097 (expected 0.0083): PASS

## Invalid repetitions (pre-registered rules; kept in the raw data)

- head-pg-w1-05.vericto-enforce.r8700.9.rep3: not steady: p50 drifts 69% from the first to the last third
- head-pg-w1-05.vericto-enforce.r8700.9.rep3.rerun: not steady: p50 drifts 190% from the first to the last third

## Charts

