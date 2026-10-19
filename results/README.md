# results/

Runs write here locally (`compose/smoke.sh`, `terraform/aws/teardown.sh`); the
directory is ignored by git except for this file. Results of a campaign are
published as release assets of this repository: one tarball per run with its
`SHA256SUMS`, containing `manifest.json` (every digest, the hosts' provenance,
the suite, the order seed), `cells.jsonl`, every cell's raw data (interval
histograms, pgbench per-transaction logs, sysbench output, counter samples, the
proxy's and intermediaries' logs) and the report.
