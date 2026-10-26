# Proxy tail latency near saturation

Cells used: 27; invalid: 0.

Added latency = target minus direct at the same rate in the same repetition, mean [95% interval] over the repetitions, in ms. CPU in vCPU-us per achieved transaction; throttled = CFS throttled periods per second (10 periods per second) and throttled ms per second (hostmon). Saturated cells (achieved below 99% of offered) are counted, not averaged.

## pg-knee-control

| % of S | target | n (sat.) | added p50 | added p99 | added p99.9 | vCPU | CPU us/tx | throttled /s | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 70 | vericto-enforce | 3 (0) | 0.124 [0.106, 0.142] | 3.29 [3.04, 3.53] | 14.36 [8.42, 20.31] | 0.400 | 94.7 | 0.06 | 0.5 |
| 70 | 4.15.3, 0.5 | 3 (0) | 0.114 [0.105, 0.123] | 0.93 [0.90, 0.95] | 10.25 [8.18, 12.32] | 0.369 | 87.2 | 0.03 | 0.2 |
| 80 | vericto-enforce | 3 (0) | 0.130 [0.123, 0.136] | 4.60 [4.16, 5.04] | 24.09 [18.90, 29.29] | 0.455 | 94.2 | 0.32 | 2.1 |
| 80 | 4.15.3, 0.5 | 3 (0) | 0.117 [0.109, 0.126] | 1.08 [0.98, 1.18] | 15.09 [7.09, 23.09] | 0.418 | 86.5 | 0.07 | 0.6 |
| 90 | vericto-enforce | 3 (0) | 0.143 [0.126, 0.161] | 29.76 [-0.84, 60.37] | 55.49 [28.50, 82.48] | 0.493 | 91.0 | 5.78 | 46.2 |
| 90 | 4.15.3, 0.5 | 3 (0) | 0.126 [0.119, 0.134] | 2.58 [-1.28, 6.44] | 32.29 [17.81, 46.77] | 0.470 | 86.5 | 0.80 | 4.0 |
