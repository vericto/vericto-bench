# Third-party components

vericto-bench's own code is Apache-2.0. It runs, but does not include in this
repository, the components below. Images are pinned by digest and archives by
SHA-256 in [versions.lock](versions.lock).

| Component | Version | License | How it is used |
| --- | --- | --- | --- |
| vericto-proxy | 4.14.3 (4.14.1 until 4.14.3 is published) | FSL-1.1-ALv2 | the system under test, pulled as an image by digest; running it to benchmark it is a permitted purpose |
| vericto-engine | v4.3.0 | FSL-1.1-ALv2 | a git dependency of `engine-eval`, pinned by tag. **A built `engine-eval` binary, and the `vericto-bench/tools` image that contains it, include FSL code; the FSL's terms apply to that part** |
| PostgreSQL, pgbench | 17.6 (official image) | PostgreSQL License | database and load generator |
| MySQL Community Server | 8.4.11 (official image) | GPL-2.0 with the Universal FOSS Exception | database |
| HAProxy | 3.0.30 (official image) | GPL-2.0 / LGPL-2.1 | baseline |
| PgBouncer | 1.24.1 (built from the release tarball) | ISC | baseline |
| ProxySQL | 2.7.3 (upstream release .deb) | GPL-3.0 | baseline |
| sysbench | 1.0.20 (Ubuntu 24.04 package) | GPL-2.0 | load generator |
| Go modules: pgx v5.7.1, go-sql-driver/mysql v1.8.1, HdrHistogram/hdrhistogram-go v1.1.2 | see go.mod | MIT, MPL-2.0, MIT | linked into vbench |
| Rust crates (engine-eval) | see engine-eval/Cargo.lock | MIT/Apache-2.0 and others | linked into engine-eval |
| matplotlib | 3.6.3 (Ubuntu 24.04 package) | PSF-based (matplotlib license) | charts |
| Alpine Linux, Ubuntu, Debian base images | see versions.lock | various | container bases |
