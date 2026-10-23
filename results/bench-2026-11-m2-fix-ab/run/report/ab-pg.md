# A/B: candidate, VERICTO_POLICY_RULES=off minus 4.14.3

Paired per repetition; means with Student t 95% intervals. Latency per transaction in ms; CPU in vCPU-µs per achieved transaction; throttled = the proxy's CFS throttled ms per second.

## Paired differences

| Rate (% of S) | n | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- |
| 1791.7 (30%) | 8 | -0.002 [-0.005, +0.000] | -0.824 [-0.938, -0.709] | -1.875 [-3.388, -0.362] | -4.1 [-6.0, -2.3] | +0.00 [+0.00, +0.00] |
| 2986.2 (50%) | 8 | -0.002 [-0.004, -0.001] | -1.914 [-1.947, -1.880] | -1.948 [-3.308, -0.588] | -4.1 [-5.2, -3.1] | +0.00 [+0.00, +0.00] |

## Levels (mean over repetitions)

| Rate | Release | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- |
| 1791.7 | 4.14.3 | 0.368 | 1.385 | 4.285 | 93.555 | 0.000 |
| 1791.7 | candidate, VERICTO_POLICY_RULES=off | 0.366 | 0.561 | 2.409 | 89.412 | 0.000 |
| 2986.2 | 4.14.3 | 0.365 | 2.727 | 5.852 | 91.490 | 0.000 |
| 2986.2 | candidate, VERICTO_POLICY_RULES=off | 0.363 | 0.813 | 3.904 | 87.341 | 0.000 |

## Paired difference by which release ran first

| Rate | First | n | p50 | p99 | CPU µs/tx |
| --- | --- | --- | --- | --- | --- |
| 1791.7 | 4.14.3 | 4 | -0.001 [-0.005, +0.003] | -0.816 [-1.053, -0.578] | -4.5 [-8.7, -0.2] |
| 1791.7 | candidate, VERICTO_POLICY_RULES=off | 4 | -0.004 [-0.008, +0.001] | -0.831 [-1.063, -0.600] | -3.8 [-7.0, -0.6] |
| 2986.2 | 4.14.3 | 4 | -0.004 [-0.004, -0.003] | -1.907 [-1.995, -1.819] | -4.5 [-5.6, -3.3] |
| 2986.2 | candidate, VERICTO_POLICY_RULES=off | 4 | -0.001 [-0.003, +0.001] | -1.920 [-1.959, -1.882] | -3.8 [-6.5, -1.2] |

## Per repetition (diff, ms)

| Rate | Rep | First | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- | --- | --- |
| 1791.7 | 1 | 4.14.3 | -0.004 | -0.652 | +2.133 | -6.8 |
| 1791.7 | 2 | candidate, VERICTO_POLICY_RULES=off | -0.008 | -1.049 | -3.272 | -6.2 |
| 1791.7 | 3 | 4.14.3 | -0.001 | -0.817 | -1.617 | -5.1 |
| 1791.7 | 4 | candidate, VERICTO_POLICY_RULES=off | -0.002 | -0.755 | -3.546 | -1.7 |
| 1791.7 | 5 | 4.14.3 | +0.001 | -0.781 | -2.687 | -5.3 |
| 1791.7 | 6 | candidate, VERICTO_POLICY_RULES=off | -0.002 | -0.772 | -2.166 | -4.7 |
| 1791.7 | 7 | 4.14.3 | +0.001 | -1.013 | -2.727 | -0.6 |
| 1791.7 | 8 | candidate, VERICTO_POLICY_RULES=off | -0.002 | -0.750 | -1.120 | -2.7 |
| 2986.2 | 1 | 4.14.3 | -0.004 | -1.918 | +1.468 | -5.3 |
| 2986.2 | 2 | candidate, VERICTO_POLICY_RULES=off | -0.001 | -1.893 | -2.341 | -3.0 |
| 2986.2 | 3 | 4.14.3 | -0.003 | -1.961 | -2.702 | -4.2 |
| 2986.2 | 4 | candidate, VERICTO_POLICY_RULES=off | +0.001 | -1.908 | -0.969 | -1.9 |
| 2986.2 | 5 | 4.14.3 | -0.004 | -1.920 | -1.439 | -4.8 |
| 2986.2 | 6 | candidate, VERICTO_POLICY_RULES=off | -0.002 | -1.947 | -3.508 | -5.2 |
| 2986.2 | 7 | 4.14.3 | -0.003 | -1.830 | -3.218 | -3.6 |
| 2986.2 | 8 | candidate, VERICTO_POLICY_RULES=off | -0.002 | -1.933 | -2.873 | -5.2 |

## Back-to-back control (each release twice in a row, then the mirror order)

| Measure | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- |
| Release diff (candidate minus baseline), per block mean | +nan (n=0) | +nan (n=0) | +nan (n=0) | +nan (n=0) |
| Position diff (second run minus first, same release) | +nan (n=0) | +nan (n=0) | +nan (n=0) | +nan (n=0) |
