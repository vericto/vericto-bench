**0.25 vCPU.**

# vericto-bench report: pub421-025-pg, pub421-025-my

| Run | Profile | Topology | Proxy image | Harness commit | Started | Finished |
| --- | --- | --- | --- | --- | --- | --- |
| bench-2026-11-proxy-421-025-q | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421-025:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `0f90258` | 2026-10-31T23:27:07.808777+00:00 | 2026-11-01T04:34:32.673456+00:00 |
| bench-2026-11-proxy-421-025-r | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421-025:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `0f90258` | 2026-10-31T23:28:54.268232+00:00 | 2026-11-01T01:30:08.115511+00:00 |

Cells: 67 recorded, 60 used, 5 invalid (listed at the end, not used).

## Added latency (open loop, from intended send time; target minus direct, paired)

| Curve | Target | Rate/s | % of S | n | added p50 ms [95%] | added p99 ms [95%] | added p99.9 ms [95%] | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-025 | vericto-enforce | 36 | 10 | 3 | 1.176 [1.140, 1.212] | 1.280 [1.263, 1.297] | 2.274 [2.202, 2.346] |  |
| head-my-w3-025 | vericto-enforce | 107 | 30 | 3 | 1.165 [1.015, 1.314] | 1.710 [1.515, 1.905] | 8.817 [6.555, 11.079] |  |
| head-my-w3-025 | vericto-enforce | 178 | 50 | 3 | 1.152 [1.110, 1.194] | 2.145 [2.026, 2.265] | 41.300 [39.044, 43.556] |  |
| head-pg-w1-025 | vericto-enforce | 424 | 10 | 3 | 0.096 [0.093, 0.099] | 0.142 [0.130, 0.155] | 1.240 [1.054, 1.426] |  |
| head-pg-w1-025 | vericto-enforce | 1271 | 30 | 3 | 0.086 [0.080, 0.091] | 0.144 [0.131, 0.157] | 1.257 [1.075, 1.440] |  |
| head-pg-w1-025 | vericto-enforce | 2119 | 50 | 3 | 0.083 [0.079, 0.086] | 0.273 [0.249, 0.297] | 21.617 [15.570, 27.665] |  |
| head-pg-w1-025 | vericto-enforce | 2966 | 70 | 3 | 0.083 [0.079, 0.087] | 0.944 [0.600, 1.288] | 47.137 [42.723, 51.551] |  |
| head-pg-w1-025 | vericto-enforce | 3390 | 80 | 3 | 0.084 [0.080, 0.088] | 13.727 [-2.570, 30.023] | 63.869 [52.198, 75.540] | not distinguishable from the direct path |
| head-pg-w1-025 | vericto-enforce | 3813 | 90 | 3 | 0.121 [0.103, 0.140] | 72.231 [59.866, 84.596] | 117.013 [100.219, 133.806] |  |

## Every cell

| Cell | Status | Achieved/s | p50 ms | p99 ms | p99.9 ms | max ms | proxy vCPU | max aggregate Mbps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sat-pg-w1-025.vericto-enforce.c1.rep1 | ok | 4137.2 | 0.167 | 0.333 | 28.719 | 66.681 | 0.250 | 60.8 |
| sat-pg-w1-025.vericto-enforce.c2.rep1 | ok | 4237.1 | 0.169 | 0.596 | 62.254 | 74.676 | 0.250 | 62.3 |
| head-pg-w1-025.vericto-enforce.r50.rep0.netprobe | ok | 49.0 | 0.542 | 0.720 | 0.846 | 0.846 | 0.007 | 1.4 |
| head-pg-w1-025.direct.r2118.6.rep1 | ok | 2117.2 | 0.301 | 0.346 | 0.397 | 163.472 | - | 78.6 |
| head-pg-w1-025.vericto-enforce.r2118.6.rep1 | ok | 2114.5 | 0.382 | 0.614 | 19.449 | 142.932 | 0.151 | 94.9 |
| head-pg-w1-025.vericto-enforce.r1271.1.rep1 | ok | 1269.4 | 0.394 | 0.495 | 1.577 | 120.208 | 0.098 | 22.4 |
| head-pg-w1-025.direct.r1271.1.rep1 | ok | 1271.0 | 0.310 | 0.354 | 0.400 | 122.274 | - | 75.8 |
| head-pg-w1-025.direct.r2966.rep1 | ok | 2961.2 | 0.300 | 0.348 | 0.414 | 139.765 | - | 26.6 |
| head-pg-w1-025.vericto-enforce.r2966.rep1 | ok | 2966.8 | 0.385 | 1.450 | 49.583 | 141.765 | 0.223 | 44.7 |
| head-pg-w1-025.vericto-enforce.r3389.7.rep1 | ok | 3386.7 | 0.383 | 20.433 | 68.958 | 118.627 | 0.243 | 118.3 |
| head-pg-w1-025.direct.r3389.7.rep1 | ok | 3383.3 | 0.297 | 0.349 | 0.421 | 107.407 | - | 30.2 |
| head-pg-w1-025.direct.r423.7.rep1 | ok | 424.1 | 0.331 | 0.387 | 0.451 | 20.964 | - | 4.9 |
| head-pg-w1-025.vericto-enforce.r423.7.rep1 | ok | 422.2 | 0.428 | 0.528 | 1.759 | 34.038 | 0.038 | 40.7 |
| head-pg-w1-025.vericto-enforce.r3813.4.rep1 | ok | 3805.1 | 0.418 | 68.736 | 111.678 | 214.029 | 0.250 | 59.9 |
| head-pg-w1-025.direct.r3813.4.rep1 | ok | 3810.0 | 0.297 | 0.352 | 0.431 | 142.602 | - | 33.7 |
| head-pg-w1-025.direct.r4237.1.rep1 | ok | 4235.4 | 0.296 | 0.354 | 0.436 | 151.806 | - | 110.7 |
| head-pg-w1-025.vericto-enforce.r4237.1.rep1 | saturated (achieved rate below 99% of offered) | 4104.4 | 8127.165 | 22159.896 | 22941.143 | 23126.583 | 0.250 | 65.2 |
| head-pg-w1-025.vericto-enforce.r3389.7.rep2 | ok | 3390.4 | 0.381 | 14.465 | 64.350 | 138.853 | 0.241 | 117.7 |
| head-pg-w1-025.direct.r3389.7.rep2 | ok | 3387.7 | 0.298 | 0.351 | 0.422 | 156.845 | - | 101.2 |
| head-pg-w1-025.direct.r2118.6.rep2 | ok | 2116.5 | 0.303 | 0.347 | 0.397 | 139.517 | - | 19.1 |
| head-pg-w1-025.vericto-enforce.r2118.6.rep2 | ok | 2119.5 | 0.387 | 0.631 | 24.292 | 118.048 | 0.159 | 99.0 |
| head-pg-w1-025.vericto-enforce.r423.7.rep2 | ok | 421.8 | 0.427 | 0.533 | 1.617 | 15.662 | 0.038 | 69.4 |
| head-pg-w1-025.direct.r423.7.rep2 | ok | 423.8 | 0.330 | 0.385 | 0.457 | 31.063 | - | 4.9 |
| head-pg-w1-025.direct.r3813.4.rep2 | ok | 3812.0 | 0.297 | 0.352 | 0.429 | 157.114 | - | 92.9 |
| head-pg-w1-025.vericto-enforce.r3813.4.rep2 | ok | 3814.7 | 0.411 | 70.808 | 115.768 | 163.112 | 0.250 | 126.0 |
| head-pg-w1-025.vericto-enforce.r1271.1.rep2 | ok | 1270.5 | 0.394 | 0.496 | 1.678 | 122.941 | 0.098 | 22.4 |
| head-pg-w1-025.direct.r1271.1.rep2 | ok | 1265.2 | 0.309 | 0.355 | 0.404 | 137.332 | - | 80.0 |
| head-pg-w1-025.direct.r2966.rep2 | ok | 2960.0 | 0.299 | 0.348 | 0.412 | 107.563 | - | 96.9 |
| head-pg-w1-025.vericto-enforce.r2966.rep2 | ok | 2968.0 | 0.381 | 1.232 | 46.781 | 140.522 | 0.212 | 44.7 |
| head-pg-w1-025.vericto-enforce.r4237.1.rep2 | ok | 4232.1 | 52.944 | 315.499 | 458.484 | 574.604 | 0.250 | 134.8 |
| head-pg-w1-025.direct.r4237.1.rep2 | ok | 4238.4 | 0.297 | 0.355 | 0.437 | 118.887 | - | 108.4 |
| head-pg-w1-025.direct.r3813.4.rep3 | ok | 3815.5 | 0.297 | 0.351 | 0.429 | 132.359 | - | 33.7 |
| head-pg-w1-025.vericto-enforce.r3813.4.rep3 | ok | 3816.2 | 5.510 | 91.199 | 137.963 | 222.771 | 0.250 | 127.5 |
| head-pg-w1-025.vericto-enforce.r2118.6.rep3 | ok | 2112.9 | 0.385 | 0.613 | 22.302 | 128.562 | 0.157 | 103.6 |
| head-pg-w1-025.direct.r2118.6.rep3 | ok | 2121.4 | 0.302 | 0.346 | 0.397 | 128.520 | - | 19.1 |
| head-pg-w1-025.direct.r1271.1.rep3 | ok | 1270.0 | 0.309 | 0.355 | 0.402 | 136.864 | - | 74.3 |
| head-pg-w1-025.vericto-enforce.r1271.1.rep3 | ok | 1276.7 | 0.397 | 0.505 | 1.723 | 131.868 | 0.103 | 87.0 |
| head-pg-w1-025.vericto-enforce.r2966.rep3 | ok | 2959.2 | 0.380 | 1.192 | 46.286 | 136.438 | 0.210 | 44.0 |
| head-pg-w1-025.direct.r2966.rep3 | ok | 2965.9 | 0.298 | 0.347 | 0.412 | 139.487 | - | 101.1 |
| head-pg-w1-025.direct.r423.7.rep3 | ok | 425.5 | 0.329 | 0.385 | 0.452 | 23.449 | - | 67.5 |
| head-pg-w1-025.vericto-enforce.r423.7.rep3 | ok | 423.2 | 0.424 | 0.523 | 1.704 | 33.125 | 0.038 | 8.0 |
| head-pg-w1-025.vericto-enforce.r3389.7.rep3 | ok | 3385.3 | 0.380 | 7.330 | 59.562 | 140.697 | 0.237 | 114.6 |
| head-pg-w1-025.direct.r3389.7.rep3 | ok | 3385.1 | 0.297 | 0.348 | 0.420 | 140.484 | - | 100.1 |
| head-pg-w1-025.direct.r4237.1.rep3 | ok | 4238.9 | 0.295 | 0.353 | 0.435 | 126.576 | - | 37.5 |
| head-pg-w1-025.vericto-enforce.r4237.1.rep3 | ok | 4236.5 | 53.947 | 241.206 | 317.336 | 390.914 | 0.250 | 134.2 |
| head-pg-w1-025.vericto-enforce.r4237.1.rep2.rerun | ok | 4222.2 | 99.692 | 1633.100 | 1776.842 | 1844.757 | 0.250 | 144.2 |
| head-pg-w1-025.vericto-enforce.r3813.4.rep3.rerun | ok | 3813.9 | 0.426 | 78.203 | 124.881 | 185.335 | 0.250 | 59.5 |
| head-pg-w1-025.vericto-enforce.r4237.1.rep3.rerun | ok | 4209.4 | 114.287 | 4552.726 | 4709.329 | 4811.130 | 0.250 | 130.8 |
| head-my-w3-025.vericto-enforce.r35.7.rep0.netprobe | ok | 35.7 | 3.907 | 4.515 | 5.647 | 5.647 | 0.039 | 62.4 |
| head-my-w3-025.direct.r178.3.rep1 | ok | 178.3 | 2.635 | 3.203 | 3.297 | 3.441 | - | 185.5 |
| head-my-w3-025.vericto-enforce.r178.3.rep1 | ok | 178.3 | 3.789 | 5.343 | 45.503 | 68.671 | 0.190 | 325.1 |
| head-my-w3-025.vericto-enforce.r107.rep1 | ok | 107.0 | 3.851 | 4.987 | 13.239 | 41.311 | 0.118 | 195.9 |
| head-my-w3-025.direct.r107.rep1 | ok | 107 | 2.625 | 3.189 | 3.371 | 4.455 | - | 111.4 |
| head-my-w3-025.direct.r35.7.rep1 | ok | 35.7 | 2.727 | 3.307 | 3.417 | 3.585 | - | 51.4 |
| head-my-w3-025.vericto-enforce.r35.7.rep1 | ok | 35.7 | 3.919 | 4.583 | 5.683 | 14.407 | 0.041 | 72.6 |
| head-my-w3-025.vericto-enforce.r178.3.rep2 | ok | 178.3 | 3.757 | 5.287 | 43.679 | 73.279 | 0.182 | 308.2 |
| head-my-w3-025.direct.r178.3.rep2 | ok | 178.3 | 2.623 | 3.187 | 3.289 | 7.239 | - | 199.9 |
| head-my-w3-025.direct.r35.7.rep2 | ok | 35.7 | 2.703 | 3.271 | 3.385 | 3.517 | - | 48.3 |
| head-my-w3-025.vericto-enforce.r35.7.rep2 | ok | 35.7 | 3.875 | 4.559 | 5.691 | 11.151 | 0.040 | 62.5 |
| head-my-w3-025.vericto-enforce.r107.rep2 | ok | 107 | 3.817 | 4.915 | 11.647 | 35.039 | 0.113 | 198.9 |
| head-my-w3-025.direct.r107.rep2 | ok | 107 | 2.711 | 3.267 | 3.359 | 4.727 | - | 123.5 |
| head-my-w3-025.direct.r35.7.rep3 | ok | 35.7 | 2.727 | 3.307 | 3.457 | 4.299 | - | 37.6 |
| head-my-w3-025.vericto-enforce.r35.7.rep3 | ok | 35.7 | 3.891 | 4.583 | 5.707 | 13.519 | 0.040 | 77.7 |
| head-my-w3-025.vericto-enforce.r107.rep3 | ok | 107 | 3.845 | 4.931 | 11.647 | 39.007 | 0.117 | 197.3 |
| head-my-w3-025.direct.r107.rep3 | ok | 107 | 2.683 | 3.247 | 3.353 | 3.557 | - | 111.6 |
| head-my-w3-025.direct.r178.3.rep3 | ok | 178.3 | 2.631 | 3.211 | 3.303 | 4.527 | - | 200.6 |
| head-my-w3-025.vericto-enforce.r178.3.rep3 | ok | 178.3 | 3.799 | 5.407 | 44.607 | 66.303 | 0.190 | 330.4 |

## Proxy CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S)

| Curve | Target | Size | n | vCPU per 1,000 QPS [95%] | intercept vCPU | USD/month per 1,000 QPS at 70% utilisation |
| --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-025 | vericto-enforce | 0.25 | 9 | 0.0644 [0.0618, 0.0669] | 0.0044 | 2.17 |
| head-pg-w1-025 | vericto-enforce | 0.25 | 12 | 0.0693 [0.0668, 0.0718] | 0.0098 | 2.34 |

## Network traffic (caps: 400 Mbps per component, 800 Mbps aggregate)

Cells aborted by a cap: 0. Per-cell maxima are in traffic.csv; bytes/s per direction over each measured window in traffic_directions.csv.

## Invalid repetitions (pre-registered rules; kept in the raw data)

- head-pg-w1-025.vericto-enforce.r4237.1.rep2: not steady: p50 drifts 27% from the first to the last third
- head-pg-w1-025.vericto-enforce.r3813.4.rep3: not steady: p50 drifts 26% from the first to the last third
- head-pg-w1-025.vericto-enforce.r4237.1.rep3: not steady: p50 drifts 13% from the first to the last third
- head-pg-w1-025.vericto-enforce.r4237.1.rep2.rerun: not steady: rate varies 2.3% across parts
- head-pg-w1-025.vericto-enforce.r4237.1.rep3.rerun: not steady: rate varies 5.1% across parts

## Charts

