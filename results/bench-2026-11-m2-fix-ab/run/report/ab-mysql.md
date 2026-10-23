# A/B: candidate, VERICTO_POLICY_RULES=off minus 4.14.3

Paired per repetition; means with Student t 95% intervals. Latency per transaction in ms; CPU in vCPU-µs per achieved transaction; throttled = the proxy's CFS throttled ms per second.

## Paired differences

| Rate (% of S) | n | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- |
| 144.4 (40%) | 8 | -0.022 [-0.069, +0.026] | -1.709 [-1.794, -1.624] | -1.055 [-1.706, -0.404] | -69.1 [-108.5, -29.7] | +0.00 [+0.00, +0.00] |
| 180.5 (50%) | 8 | -0.057 [-0.078, -0.037] | -1.787 [-1.837, -1.737] | -1.527 [-2.291, -0.763] | -121.9 [-140.5, -103.4] | +0.00 [+0.00, +0.00] |
| 216.6 (60%) | 8 | -0.096 [-0.119, -0.073] | -1.807 [-1.872, -1.742] | -0.693 [-1.694, +0.307] | -82.5 [-112.0, -53.0] | +0.00 [+0.00, +0.00] |

## Levels (mean over repetitions)

| Rate | Release | p50 | p99 | p99.9 | CPU µs/tx | throttled ms/s |
| --- | --- | --- | --- | --- | --- | --- |
| 144.4 | 4.14.3 | 4.141 | 6.965 | 7.947 | 1509.830 | 0.000 |
| 144.4 | candidate, VERICTO_POLICY_RULES=off | 4.119 | 5.256 | 6.893 | 1440.767 | 0.000 |
| 180.5 | 4.14.3 | 4.103 | 7.098 | 8.761 | 1510.603 | 0.000 |
| 180.5 | candidate, VERICTO_POLICY_RULES=off | 4.046 | 5.311 | 7.234 | 1388.662 | 0.000 |
| 216.6 | 4.14.3 | 4.127 | 7.229 | 9.197 | 1494.009 | 0.000 |
| 216.6 | candidate, VERICTO_POLICY_RULES=off | 4.031 | 5.422 | 8.504 | 1411.510 | 0.000 |

## Paired difference by which release ran first

| Rate | First | n | p50 | p99 | CPU µs/tx |
| --- | --- | --- | --- | --- | --- |
| 144.4 | 4.14.3 | 4 | -0.043 [-0.096, +0.010] | -1.737 [-1.897, -1.577] | -87.7 [-124.7, -50.7] |
| 144.4 | candidate, VERICTO_POLICY_RULES=off | 4 | -0.001 [-0.115, +0.114] | -1.681 [-1.854, -1.508] | -50.5 [-147.5, +46.6] |
| 180.5 | 4.14.3 | 4 | -0.054 [-0.085, -0.024] | -1.769 [-1.834, -1.704] | -120.1 [-156.2, -84.1] |
| 180.5 | candidate, VERICTO_POLICY_RULES=off | 4 | -0.060 [-0.111, -0.009] | -1.805 [-1.926, -1.684] | -123.7 [-163.5, -84.0] |
| 216.6 | 4.14.3 | 4 | -0.100 [-0.122, -0.077] | -1.770 [-1.866, -1.674] | -74.7 [-128.0, -21.3] |
| 216.6 | candidate, VERICTO_POLICY_RULES=off | 4 | -0.093 [-0.155, -0.031] | -1.844 [-1.973, -1.715] | -90.3 [-154.2, -26.4] |

## Per repetition (diff, ms)

| Rate | Rep | First | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- | --- | --- |
| 144.4 | 1 | 4.14.3 | -0.050 | -1.636 | -1.468 | -97.3 |
| 144.4 | 2 | candidate, VERICTO_POLICY_RULES=off | +0.068 | -1.648 | +0.180 | +8.2 |
| 144.4 | 3 | 4.14.3 | -0.052 | -1.788 | -0.944 | -97.5 |
| 144.4 | 4 | candidate, VERICTO_POLICY_RULES=off | -0.102 | -1.840 | -2.400 | -136.2 |
| 144.4 | 5 | 4.14.3 | -0.074 | -1.852 | -0.292 | -102.8 |
| 144.4 | 6 | candidate, VERICTO_POLICY_RULES=off | +0.020 | -1.644 | -1.432 | -37.2 |
| 144.4 | 7 | 4.14.3 | +0.004 | -1.672 | -0.992 | -53.0 |
| 144.4 | 8 | candidate, VERICTO_POLICY_RULES=off | +0.012 | -1.592 | -1.092 | -36.7 |
| 180.5 | 1 | 4.14.3 | -0.048 | -1.748 | -1.792 | -114.5 |
| 180.5 | 2 | candidate, VERICTO_POLICY_RULES=off | -0.084 | -1.908 | -2.500 | -159.7 |
| 180.5 | 3 | 4.14.3 | -0.038 | -1.828 | -0.752 | -96.3 |
| 180.5 | 4 | candidate, VERICTO_POLICY_RULES=off | -0.056 | -1.724 | -1.204 | -107.2 |
| 180.5 | 5 | 4.14.3 | -0.050 | -1.736 | -2.624 | -118.9 |
| 180.5 | 6 | candidate, VERICTO_POLICY_RULES=off | -0.016 | -1.788 | +0.148 | -106.2 |
| 180.5 | 7 | 4.14.3 | -0.082 | -1.764 | -1.648 | -150.8 |
| 180.5 | 8 | candidate, VERICTO_POLICY_RULES=off | -0.084 | -1.800 | -1.844 | -121.8 |
| 216.6 | 1 | 4.14.3 | -0.120 | -1.848 | -1.264 | -120.5 |
| 216.6 | 2 | candidate, VERICTO_POLICY_RULES=off | -0.068 | -1.812 | -1.632 | -83.8 |
| 216.6 | 3 | 4.14.3 | -0.092 | -1.768 | -0.556 | -74.8 |
| 216.6 | 4 | candidate, VERICTO_POLICY_RULES=off | -0.150 | -1.960 | +1.852 | -146.9 |
| 216.6 | 5 | 4.14.3 | -0.088 | -1.700 | +0.024 | -41.2 |
| 216.6 | 6 | candidate, VERICTO_POLICY_RULES=off | -0.066 | -1.832 | -1.096 | -78.4 |
| 216.6 | 7 | 4.14.3 | -0.098 | -1.764 | -0.924 | -62.3 |
| 216.6 | 8 | candidate, VERICTO_POLICY_RULES=off | -0.088 | -1.772 | -1.952 | -52.1 |

## Back-to-back control (each release twice in a row, then the mirror order)

| Measure | p50 | p99 | p99.9 | CPU µs/tx |
| --- | --- | --- | --- | --- |
| Release diff (candidate minus baseline), per block mean | +nan (n=0) | +nan (n=0) | +nan (n=0) | +nan (n=0) |
| Position diff (second run minus first, same release) | +nan (n=0) | +nan (n=0) | +nan (n=0) | +nan (n=0) |
