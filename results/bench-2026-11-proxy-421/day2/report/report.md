**day2.**

# vericto-bench report: pub421-day2

| Run | Profile | Topology | Proxy image | Harness commit | Started | Finished |
| --- | --- | --- | --- | --- | --- | --- |
| bench-2026-11-proxy-421-d2 | published | two-host | `<bench-account>.dkr.ecr.us-east-1.amazonaws.com/vericto-bench/proxy-421:4.21.0@sha256:7cca34697f61cf2baadb85a963520813ef108f10ad379906ffffb60b860c3bfd` | `30131ce74266` | 2026-10-31T14:14:31.272904+00:00 | 2026-10-31T18:57:40.836082+00:00 |

Cells: 44 recorded, 42 used, 0 invalid (listed at the end, not used).

## Added latency (open loop, from intended send time; target minus direct, paired)

| Curve | Target | Rate/s | % of S | n | added p50 ms [95%] | added p99 ms [95%] | added p99.9 ms [95%] | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | haproxy-tcp | 36 | 10 | 1 | 0.514 | 0.540 | 1.102 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 107 | 30 | 1 | 0.392 | 0.466 | 0.720 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 178 | 50 | 1 | 0.480 | 0.494 | 0.554 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 250 | 70 | 1 | 0.482 | 0.480 | 0.304 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 285 | 80 | 1 | 0.472 | 0.544 | 1.148 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 321 | 90 | 1 | 0.418 | 0.456 | 0.522 | n=1, no interval |
| head-my-w3-05 | haproxy-tcp | 357 | 100 | 1 | 0.254 | 0.514 | 0.626 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 36 | 10 | 1 | 1.158 | 1.300 | 2.674 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 107 | 30 | 1 | 1.098 | 1.642 | 2.824 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 178 | 50 | 1 | 1.138 | 1.952 | 2.604 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 250 | 70 | 1 | 1.080 | 2.022 | 3.978 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 285 | 80 | 1 | 0.980 | 2.182 | 4.204 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 321 | 90 | 1 | 0.746 | 1.632 | 5.068 | n=1, no interval |
| head-my-w3-05 | vericto-enforce | 357 | 100 | 1 | 0.866 | 1.994 | 8.384 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 967 | 10 | 1 | 0.036 | 0.044 | 0.090 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 2900 | 30 | 1 | 0.034 | 0.048 | 0.105 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 4834 | 50 | 1 | 0.033 | 0.086 | 0.127 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 6767 | 70 | 1 | 0.034 | 0.092 | 0.142 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 7734 | 80 | 1 | 0.033 | 0.096 | 0.152 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 8701 | 90 | 1 | 0.033 | 0.099 | 0.167 | n=1, no interval |
| head-pg-w1-05 | haproxy-tcp | 9668 | 100 | 1 | 0.034 | 0.112 | 0.172 | n=1, no interval |
| head-pg-w1-05 | vericto-enforce | 967 | 10 | 1 | 0.090 | 0.142 | 1.183 | n=1, no interval |
| head-pg-w1-05 | vericto-enforce | 2900 | 30 | 1 | 0.080 | 0.288 | 1.234 | n=1, no interval |
| head-pg-w1-05 | vericto-enforce | 4834 | 50 | 1 | 0.080 | 0.596 | 1.339 | n=1, no interval |
| head-pg-w1-05 | vericto-enforce | 6767 | 70 | 1 | 0.093 | 1.407 | 21.131 | n=1, no interval |
| head-pg-w1-05 | vericto-enforce | 7734 | 80 | 1 | 0.096 | 14.264 | 40.976 | n=1, no interval |

## Every cell

| Cell | Status | Achieved/s | p50 ms | p99 ms | p99.9 ms | max ms | proxy vCPU | max aggregate Mbps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
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

## Proxy CPU per 1,000 QPS (linear fit, open-loop cells below 80% of S)

| Curve | Target | Size | n | vCPU per 1,000 QPS [95%] | intercept vCPU | USD/month per 1,000 QPS at 70% utilisation |
| --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | vericto-enforce | 0.5 | 4 | 0.0620 [0.0573, 0.0667] | 0.0068 | 2.09 |
| head-pg-w1-05 | vericto-enforce | 0.5 | 4 | 0.0660 [0.0583, 0.0737] | 0.0113 | 2.23 |

## Network traffic (caps: 400 Mbps per component, 800 Mbps aggregate)

Cells aborted by a cap: 0. Per-cell maxima are in traffic.csv; bytes/s per direction over each measured window in traffic_directions.csv.

Bytes per direction at vericto-enforce, highest offered rate of each open-loop curve (saturated cells included; Mbps, window mean):

| Curve | Rate/s | client to proxy | proxy to client | proxy to DB | DB to proxy | telemetry out | proxy total | result bytes per request |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| head-my-w3-05 | 357 | 5.9 | 115.9 | 5.4 | 115.9 | 2.28 | 245.4 | 40625 |
| head-pg-w1-05 | 9668 | 12.8 | 10.9 | 13.3 | 10.4 | 2.77 | 50.1 | 162 |

## Charts

