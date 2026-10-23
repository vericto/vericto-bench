# terraform/aws: one benchmark run in your own AWS account

Creates everything a Tier P run needs, runs the suite unattended from user-data,
uploads the results to an S3 bucket in the same stack and stops the instances.
`teardown.sh` downloads the results and destroys the stack.

## What it creates

| Resource | Notes |
| --- | --- |
| VPC `10.81.0.0/16` | Its own; no peering. One **private** subnet for the instances, one public subnet that holds only a NAT gateway (image pulls, SSM). S3 gateway endpoint. None of this with `existing_vpc_id` (see "In an existing VPC") |
| Instances | `two-host` (default, the published topology): SUT `c7g.2xlarge` + load generator `c7g.xlarge` in a cluster placement group, same AZ. `single`: one `c7g.2xlarge` over loopback (cheaper; flagged in the manifest, not the published topology). Amazon Linux 2023, architecture from the instance type. No public IP, IMDSv2 only, encrypted gp3 root (SUT 100 GiB, 3,000 IOPS, 250 MB/s; load generator 40 GiB), shutdown behaviour `stop` |
| Security groups | Load generator: **no inbound rule**. SUT: inbound only from the load generator's security group, on tcp 22 (Docker over SSH, the hostmon stream) and the bench ports 5432, 3306, 6432-6433, 6306-6307, 7432, 7306, 8432, 8306. In `single` the SUT has no inbound rule |
| Access | SSM Session Manager (`AmazonSSMManagedInstanceCore`). No SSH from outside the VPC, no key pair |
| S3 bucket | Results and the harness archive. Public access blocked, SSE-S3, TLS-only bucket policy, objects expire after 30 days, `force_destroy` (download before destroying: `teardown.sh` does) |
| IAM | One role per host. S3 limited to this run's prefix in this bucket; the load generator may read exactly one SecureString parameter |
| SSH key (two-host) | `tls_private_key` (ed25519): the private key is in the Terraform state and in the SecureString `/vericto-bench/<run_id>/sut-ssh-key`, the public key in the SUT's user-data. Ephemeral: destroyed with the stack |

Every resource is tagged `Project=vericto-bench`, `Campaign`, `RunId`, `ExpiresOn`, `ManagedBy=terraform`.

**Runtime guard:** each host schedules `shutdown -h` at boot, `max_hours` later
(automatic: `quick` 3 h, `c7i` 14 h, `day2` 24 h, `published` 132 h, otherwise 30 h), so a stuck run cannot bill for days.
A stopped instance still bills its EBS volume until `teardown.sh`.

## In an existing VPC

`existing_vpc_id` (with `existing_subnet_ids`, and optionally `existing_placement_subnet_id`)
runs the bench in a VPC you already have instead of creating one. Then the stack
creates no VPC, subnet, internet gateway, NAT gateway, route or S3 endpoint; everything
else (security groups, placement group, bucket, roles, instances) is the same, and so
are the runtime guard and the hostmon network caps, which run on the hosts.

The subnets must be private (no public IPs) with a default route to a NAT, a gateway or
a NAT instance. Add an S3 gateway endpoint on their route table to keep the harness and
results off the NAT. Both hosts go into one subnet: `existing_placement_subnet_id`, or else
the first of `existing_subnet_ids` whose AZ offers every instance type of the run, because a
cluster placement group spans one AZ. The VPC's security groups and NACLs must allow
the hosts' egress (image pulls, SSM, S3).

```bash
terraform apply -var run_id=... -var expires_on=... \
  -var existing_vpc_id=vpc-... \
  -var 'existing_subnet_ids=["subnet-...","subnet-..."]' \
  -var existing_placement_subnet_id=subnet-...
```

`terraform destroy` (and `teardown.sh`) then removes only the run's resources; the VPC
and its NAT stay.

## Run

```bash
cd terraform/aws
terraform init
terraform apply -var run_id=bench-2026-11-quick-1 -var expires_on=$(date -u -v+3d +%F 2>/dev/null || date -u -d '+3 days' +%F) \
  -var suite=quick                       # published, day2, c7i, ...; -var topology=single for one host
terraform output ssm_start_session       # progress: /var/log/vericto-bench/*.log on each host
aws s3 ls s3://$(terraform output -raw results_bucket)/$(terraform output -raw run_id)/   # DONE or FAILED appears at the end
./teardown.sh -var run_id=... -var expires_on=...   # same -var values as apply: sync, verify SHA256SUMS, destroy
```

The c7i cross-check: `-var sut_instance_type=c7i.2xlarge -var suite=c7i`. On c7i
a vCPU is a hyperthread; `host/setup.sh` gives the proxy one thread of its own
core with the sibling idle (see `host/setup.sh`).

## Cost (us-east-1 list prices, per hour)

| Item | USD/h |
| --- | --- |
| c7g.2xlarge (SUT) | 0.29 |
| c7g.xlarge (load generator) | 0.145 |
| c7i.2xlarge (cross-check SUT) | 0.357 |
| NAT gateway | 0.045 + 0.045 per GB processed (image pulls, a few GB) |
| gp3 140 GiB + 125 MB/s above baseline | about 0.02 |
| S3 | cents per run |

A `quick` run (about 1 h) costs about USD 1; the published campaign is in the
repository README.
