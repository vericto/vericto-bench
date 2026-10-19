# Security Policy

vericto-bench provisions cloud resources and runs databases and proxies with
generated credentials. We take vulnerabilities in it seriously and appreciate
responsible disclosure.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report it privately, by either channel:

- Email **security@vericto.com**.
- Open a private report on GitHub:
  [Report a vulnerability](https://github.com/vericto/vericto-bench/security/advisories/new)
  (Security tab → "Report a vulnerability"). Only the maintainers can see it.

Include a description and its impact, steps to reproduce, the affected commit,
and any suggested remediation. You will receive an acknowledgement within
**48 hours** and a status update within **5 business days**.

## Scope

High-priority issues for this repository include:

- **Provisioning** (`terraform/aws`, `host/`): anything that exposes the
  instances or the results bucket beyond the stack (an inbound rule from outside
  the VPC, a public bucket or object, an IAM grant beyond the run's own bucket
  prefix and parameter), or resources that outlive `teardown.sh` and the
  `ExpiresOn` tag.
- **Secrets**: the per-run database passwords, TLS key or SSH key reaching a
  log, a result file, the manifest or a command line on a shared host.
- **Traffic caps**: any way a suite can exceed 400 Mbps per component or
  800 Mbps in aggregate without the guard aborting it.

Vulnerabilities in vericto-proxy itself go to
[vericto-proxy](https://github.com/vericto/vericto-proxy/security); we route
reports to the right repository.

## Disclosure process

1. Report received and acknowledged (within 48h).
2. We confirm and assess severity.
3. We develop and test a fix.
4. We release the fix and credit you (unless you prefer to remain anonymous).
5. Public disclosure after users have had reasonable time to update.

Thank you for helping keep Vericto and its users safe.
