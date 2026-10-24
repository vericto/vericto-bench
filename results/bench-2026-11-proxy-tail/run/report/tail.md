# Proxy tail latency near saturation

Cells used: 124; invalid: 4.

Added latency = target minus direct at the same rate in the same repetition, mean [95% interval] over the repetitions, in ms. CPU in vCPU-us per achieved transaction; throttled = CFS throttled periods per second (10 periods per second) and throttled ms per second (hostmon). Saturated cells (achieved below 99% of offered) are counted, not averaged.

## my-knee

| % of S | target | n (sat.) | added p50 | added p99 | added p99.9 | vCPU | CPU us/tx | throttled /s | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | 4.15.3, 0.5 | 3 (0) | 1.201 [1.177, 1.224] | 2.55 [2.50, 2.60] | 9.79 [8.42, 11.15] | 0.403 | 1410.9 | 0.06 | 0.4 |
| 80 | 4.15.3, 1 vCPU | 3 (0) | 1.193 [1.173, 1.213] | 2.54 [2.35, 2.73] | 6.81 [4.99, 8.64] | 0.400 | 1402.9 | 0.00 | 0.0 |
| 80 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 3 (0) | 1.485 [1.116, 1.854] | 15.93 [-9.98, 41.84] | 33.98 [11.87, 56.09] | 0.498 | 1746.5 | 7.62 | 115.5 |
| 80 | 4.16.1 candidate, 0.5 | 3 (0) | 1.199 [1.182, 1.217] | 2.50 [2.31, 2.70] | 11.33 [7.32, 15.33] | 0.418 | 1465.0 | 0.06 | 0.6 |
| 80 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 1.195 [1.168, 1.223] | 2.54 [2.34, 2.73] | 9.65 [6.81, 12.49] | 0.405 | 1419.2 | 0.05 | 0.4 |
| 80 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 1.153 [1.133, 1.173] | 1.79 [1.59, 1.98] | 2.18 [1.93, 2.44] | 0.357 | 1251.0 | 0.05 | 0.3 |
| 90 | 4.15.3, 0.5 | 3 (0) | 1.165 [1.112, 1.217] | 2.35 [2.16, 2.53] | 15.64 [13.00, 18.29] | 0.453 | 1411.5 | 0.11 | 1.1 |
| 90 | 4.15.3, 1 vCPU | 3 (0) | 1.193 [1.047, 1.340] | 2.27 [2.13, 2.40] | 7.81 [6.50, 9.11] | 0.459 | 1429.7 | 0.00 | 0.0 |
| 90 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 2 (0) | 14.777 [-16.086, 45.640] | 56.16 [29.66, 82.67] | 69.27 [43.47, 95.08] | 0.499 | 1555.5 | 10.00 | 522.1 |
| 90 | 4.16.1 candidate, 0.5 | 3 (0) | 1.217 [1.111, 1.323] | 2.44 [2.24, 2.64] | 15.63 [13.12, 18.14] | 0.462 | 1440.5 | 0.13 | 1.2 |
| 90 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 1.173 [1.088, 1.257] | 2.24 [2.08, 2.40] | 14.47 [12.30, 16.64] | 0.450 | 1401.9 | 0.12 | 1.0 |
| 90 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 0.879 [0.738, 1.021] | 1.28 [1.20, 1.35] | 3.80 [0.17, 7.43] | 0.396 | 1234.8 | 0.06 | 0.8 |

Scheduler (host/schedmon.py, 100-ms cgroup samples, threads every 5 s): share of CFS periods throttled; threads of the proxy (busy = at least 1% of a CPU); run-queue wait per transaction (all threads, includes the time throttled); for pgbench, the share of transactions over 10 ms and the share of those, and of all transactions, whose lifetime overlaps a throttled period.

| % of S | target | periods throttled | threads (busy) | run-queue us/tx | tx > 10 ms | of which overlap a throttle | all tx overlapping |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | 4.15.3, 0.5 | 0.006 | 8 (7) | 578.5 | - | - | - |
| 80 | 4.15.3, 1 vCPU | - | 7 (6) | 565.4 | - | - | - |
| 80 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 0.763 | 25 (14) | 954.5 | - | - | - |
| 80 | 4.16.1 candidate, 0.5 | 0.007 | 9 (8) | 593.9 | - | - | - |
| 80 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.005 | 6 (5) | 570.4 | - | - | - |
| 80 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.005 | 7 (6) | 24.3 | - | - | - |
| 90 | 4.15.3, 0.5 | 0.012 | 12 (10) | 596.3 | - | - | - |
| 90 | 4.15.3, 1 vCPU | - | 10 (9) | 602.1 | - | - | - |
| 90 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 1.000 | 72 (2) | 5160.3 | - | - | - |
| 90 | 4.16.1 candidate, 0.5 | 0.015 | 11 (10) | 624.3 | - | - | - |
| 90 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.013 | 6 (5) | 586.0 | - | - | - |
| 90 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.007 | 10 (8) | 19.7 | - | - | - |

## pg-knee

| % of S | target | n (sat.) | added p50 | added p99 | added p99.9 | vCPU | CPU us/tx | throttled /s | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 60 | 4.15.3, 0.5 | 3 (0) | 0.107 [0.100, 0.115] | 0.68 [0.67, 0.69] | 6.14 [2.50, 9.78] | 0.314 | 86.9 | 0.00 | 0.0 |
| 60 | 4.15.3, 1 vCPU | 3 (0) | 0.105 [0.097, 0.113] | 0.64 [0.62, 0.65] | 3.83 [0.75, 6.91] | 0.305 | 84.4 | 0.00 | 0.0 |
| 60 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 3 (0) | 0.114 [0.111, 0.118] | 0.26 [0.25, 0.28] | 0.75 [0.51, 0.99] | 0.383 | 105.8 | 0.05 | 0.6 |
| 60 | 4.16.1 candidate, 0.5 | 3 (0) | 0.110 [0.104, 0.115] | 0.68 [0.67, 0.70] | 4.72 [0.66, 8.78] | 0.319 | 88.4 | 0.00 | 0.0 |
| 60 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 0.109 [0.103, 0.114] | 0.62 [0.55, 0.69] | 4.89 [2.21, 7.57] | 0.316 | 87.4 | 0.00 | 0.0 |
| 60 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 0.095 [0.092, 0.098] | 0.29 [0.28, 0.30] | 0.54 [0.50, 0.57] | 0.297 | 82.1 | 0.00 | 0.0 |
| 70 | 4.15.3, 0.5 | 3 (0) | 0.109 [0.106, 0.113] | 0.84 [0.83, 0.86] | 6.49 [2.79, 10.18] | 0.362 | 85.9 | 0.01 | 0.1 |
| 70 | 4.15.3, 1 vCPU | 3 (0) | 0.111 [0.104, 0.118] | 0.83 [0.78, 0.88] | 6.72 [4.91, 8.53] | 0.368 | 87.1 | 0.00 | 0.0 |
| 70 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 3 (0) | 0.117 [0.111, 0.122] | 0.35 [0.32, 0.37] | 16.64 [7.45, 25.84] | 0.450 | 106.4 | 0.19 | 1.9 |
| 70 | 4.16.1 candidate, 0.5 | 3 (0) | 0.113 [0.106, 0.120] | 0.86 [0.83, 0.89] | 7.92 [4.95, 10.89] | 0.373 | 88.3 | 0.03 | 0.1 |
| 70 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 0.110 [0.103, 0.117] | 0.78 [0.73, 0.83] | 6.54 [2.25, 10.82] | 0.363 | 85.9 | 0.02 | 0.1 |
| 70 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 0.097 [0.094, 0.101] | 0.35 [0.33, 0.37] | 0.64 [0.58, 0.70] | 0.349 | 82.6 | 0.03 | 0.2 |
| 80 | 4.15.3, 0.5 | 3 (0) | 0.114 [0.108, 0.121] | 1.05 [0.97, 1.13] | 13.64 [11.83, 15.44] | 0.411 | 85.2 | 0.06 | 0.5 |
| 80 | 4.15.3, 1 vCPU | 3 (0) | 0.115 [0.112, 0.119] | 1.00 [0.94, 1.06] | 9.79 [7.84, 11.75] | 0.417 | 86.5 | 0.00 | 0.0 |
| 80 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 3 (0) | 0.122 [0.103, 0.140] | 39.13 [0.40, 77.85] | 82.87 [39.09, 126.65] | 0.498 | 103.1 | 8.72 | 127.8 |
| 80 | 4.16.1 candidate, 0.5 | 3 (0) | 0.114 [0.111, 0.117] | 1.02 [1.02, 1.03] | 12.18 [7.07, 17.29] | 0.414 | 85.8 | 0.07 | 0.5 |
| 80 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 0.115 [0.113, 0.117] | 0.97 [0.95, 0.98] | 12.34 [9.13, 15.56] | 0.410 | 85.1 | 0.06 | 0.5 |
| 80 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 0.097 [0.094, 0.101] | 0.40 [0.37, 0.43] | 1.97 [-1.82, 5.76] | 0.394 | 81.5 | 0.06 | 0.7 |
| 90 | 4.15.3, 0.5 | 3 (0) | 0.120 [0.117, 0.123] | 1.33 [1.14, 1.51] | 21.13 [16.91, 25.35] | 0.459 | 84.5 | 0.23 | 1.5 |
| 90 | 4.15.3, 1 vCPU | 3 (0) | 0.119 [0.112, 0.125] | 1.17 [1.12, 1.22] | 9.53 [7.27, 11.79] | 0.457 | 84.2 | 0.00 | 0.0 |
| 90 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 2 (0) | 79.885 [-112.008, 271.777] | 759.12 [-4831.43, 6349.66] | 957.85 [-4203.52, 6119.22] | 0.498 | 91.8 | 10.00 | 733.3 |
| 90 | 4.16.1 candidate, 0.5 | 3 (0) | 0.126 [0.116, 0.136] | 2.82 [-1.89, 7.54] | 31.00 [25.17, 36.83] | 0.475 | 87.4 | 1.10 | 4.9 |
| 90 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 3 (0) | 0.121 [0.112, 0.129] | 1.45 [0.47, 2.43] | 24.84 [9.90, 39.78] | 0.461 | 84.9 | 0.35 | 2.0 |
| 90 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 3 (0) | 0.099 [0.096, 0.102] | 0.49 [0.46, 0.51] | 17.40 [4.63, 30.18] | 0.438 | 80.7 | 0.12 | 1.5 |

Scheduler (host/schedmon.py, 100-ms cgroup samples, threads every 5 s): share of CFS periods throttled; threads of the proxy (busy = at least 1% of a CPU); run-queue wait per transaction (all threads, includes the time throttled); for pgbench, the share of transactions over 10 ms and the share of those, and of all transactions, whose lifetime overlaps a throttled period.

| % of S | target | periods throttled | threads (busy) | run-queue us/tx | tx > 10 ms | of which overlap a throttle | all tx overlapping |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 60 | 4.15.3, 0.5 | 0.000 | 9 (8) | 44.1 | 0.0008 | 0.000 | 0.000 |
| 60 | 4.15.3, 1 vCPU | - | 9 (8) | 42.3 | 0.0006 | 0.000 | 0.000 |
| 60 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 0.006 | 11 (10) | 11.3 | 0.0003 | 0.997 | 0.006 |
| 60 | 4.16.1 candidate, 0.5 | 0.000 | 10 (8) | 45.2 | 0.0007 | 0.000 | 0.000 |
| 60 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.000 | 6 (5) | 43.8 | 0.0007 | 0.000 | 0.000 |
| 60 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.000 | 10 (9) | 5.8 | 0.0000 | 0.000 | 0.000 |
| 70 | 4.15.3, 0.5 | 0.001 | 10 (9) | 44.1 | 0.0008 | 0.196 | 0.001 |
| 70 | 4.15.3, 1 vCPU | - | 10 (9) | 45.6 | 0.0008 | 0.000 | 0.000 |
| 70 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 0.020 | 12 (11) | 14.3 | 0.0014 | 1.000 | 0.020 |
| 70 | 4.16.1 candidate, 0.5 | 0.003 | 10 (9) | 46.5 | 0.0009 | 0.256 | 0.003 |
| 70 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.002 | 6 (5) | 44.9 | 0.0008 | 0.279 | 0.002 |
| 70 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.003 | 10 (9) | 6.6 | 0.0001 | 0.667 | 0.003 |
| 80 | 4.15.3, 0.5 | 0.006 | 12 (10) | 45.2 | 0.0015 | 0.692 | 0.007 |
| 80 | 4.15.3, 1 vCPU | - | 10 (9) | 46.1 | 0.0010 | 0.000 | 0.000 |
| 80 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 0.873 | 15 (13) | 84.9 | 0.1067 | 0.994 | 0.851 |
| 80 | 4.16.1 candidate, 0.5 | 0.007 | 10 (9) | 45.2 | 0.0012 | 0.820 | 0.007 |
| 80 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.007 | 6 (5) | 44.6 | 0.0013 | 0.424 | 0.004 |
| 80 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.007 | 11 (10) | 7.9 | 0.0005 | 0.998 | 0.007 |
| 90 | 4.15.3, 0.5 | 0.024 | 13 (12) | 46.3 | 0.0025 | 0.907 | 0.024 |
| 90 | 4.15.3, 1 vCPU | - | 12 (9) | 45.7 | 0.0010 | 0.000 | 0.000 |
| 90 | 4.15.3, 0.5 over two cores, 2 workers (as on Fargate) | 1.000 | 20 (18) | 428.4 | 0.8668 | 0.995 | 0.992 |
| 90 | 4.16.1 candidate, 0.5 | 0.111 | 15 (14) | 49.5 | 0.0048 | 0.968 | 0.116 |
| 90 | 4.16.1 candidate, 0.5, VERICTO_BLOCKING_THREADS=4 | 0.036 | 6 (5) | 46.0 | 0.0034 | 0.922 | 0.037 |
| 90 | 4.16.1 candidate, 0.5 over two cores (1 worker) | 0.013 | 12 (11) | 9.0 | 0.0015 | 0.991 | 0.014 |
