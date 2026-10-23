# Paired comparison: 4.15.0, VERICTO_POLICY_RULES=off against 4.14.3

Gate (cells below 70% of S; absolute-rate cells included): **FAIL**; failing: ab-my-w3-05@142.3, ab-my-w3-05@177.9

Added = target minus direct, paired per repetition. Diff = candidate minus baseline, paired per repetition. Means with Student t 95% intervals; ms.

| Curve | Rate (% of S) | n | pct | Added baseline [95%] | Added candidate [95%] | Diff [95%] | Overlap | 0 in diff | Gated | Pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ab-my-w3-05 | 142.3 (40%) | 8 | p50 | n/a n/a | n/a n/a | 0.067 [0.037, 0.098] | None | False | yes | NO |
| ab-my-w3-05 | 142.3 (40%) | 8 | p99 | n/a n/a | n/a n/a | 0.079 [0.011, 0.146] | None | False | yes | NO |
| ab-my-w3-05 | 142.3 (40%) | 8 | p999 | n/a n/a | n/a n/a | -0.046 [-0.760, 0.668] | None | True | yes | yes |
| ab-my-w3-05 | 177.9 (50%) | 8 | p50 | n/a n/a | n/a n/a | 0.040 [-0.002, 0.082] | None | True | yes | yes |
| ab-my-w3-05 | 177.9 (50%) | 8 | p99 | n/a n/a | n/a n/a | 0.076 [0.017, 0.135] | None | False | yes | NO |
| ab-my-w3-05 | 177.9 (50%) | 8 | p999 | n/a n/a | n/a n/a | 0.154 [-0.841, 1.149] | None | True | yes | yes |
| ab-my-w3-05 | 213.5 (60%) | 8 | p50 | n/a n/a | n/a n/a | 0.032 [-0.021, 0.086] | None | True | yes | yes |
| ab-my-w3-05 | 213.5 (60%) | 8 | p99 | n/a n/a | n/a n/a | 0.025 [-0.104, 0.154] | None | True | yes | yes |
| ab-my-w3-05 | 213.5 (60%) | 8 | p999 | n/a n/a | n/a n/a | 0.887 [-0.628, 2.402] | None | True | yes | yes |
| swap-my-w3-05 | 177.9 (50%) | 2 | p50 | n/a n/a | n/a n/a | -0.014 [-0.395, 0.367] | None | True | yes | yes |
| swap-my-w3-05 | 177.9 (50%) | 2 | p99 | n/a n/a | n/a n/a | 0.014 [-0.672, 0.700] | None | True | yes | yes |
| swap-my-w3-05 | 177.9 (50%) | 2 | p999 | n/a n/a | n/a n/a | -1.240 [-11.100, 8.620] | None | True | yes | yes |

## Proxy vCPU per 1,000 statements/s (per cell, mean over repetitions)

| Curve | Rate | Baseline [95%] | Candidate [95%] | Paired diff [95%] |
| --- | --- | --- | --- | --- |
| ab-my-w3-05 | 142.3 | 0.0982 [0.0970, 0.0993] | 0.1027 [0.1005, 0.1048] | 0.0045 [0.0024, 0.0065] |
| ab-my-w3-05 | 177.9 | 0.0975 [0.0965, 0.0986] | 0.1003 [0.0980, 0.1027] | 0.0028 [0.0005, 0.0052] |
| ab-my-w3-05 | 213.5 | 0.0986 [0.0972, 0.1001] | 0.1019 [0.0985, 0.1053] | 0.0033 [-0.0006, 0.0072] |
| swap-my-w3-05 | 177.9 | 0.0999 [0.0767, 0.1231] | 0.0996 [0.0931, 0.1061] | -0.0003 [-0.0300, 0.0295] |

## CPU fit (vCPU against achieved kQPS, open-loop cells below 80% of S)

| Curve | Target | n | vCPU per 1,000 QPS [95%] | Intercept vCPU |
| --- | --- | --- | --- | --- |
| ab-my-w3-05 | 4.14.3 | 24 | 0.0995 [0.0954, 0.1036] | -0.0040 |
| ab-my-w3-05 | 4.15.0, VERICTO_POLICY_RULES=off | 24 | 0.1005 [0.0914, 0.1096] | 0.0032 |

## Closed-loop maximum throughput (statements/s; 1 repetition)

| Curve | Target | Max |
| --- | --- | --- |
| sat-my-w3-05 | 4.14.3 | 5,695 |
| sat-my-w3-05 | 4.15.0, VERICTO_POLICY_RULES=off | 5,540 |
