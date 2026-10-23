# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# One run of vericto-bench in the reader's own account: an isolated VPC, a
# private subnet with egress through a NAT gateway, no inbound access from
# outside the VPC, SSM Session Manager for access, and an S3 bucket for results.
# The hosts run the suite from user-data, upload the results and stop.
#
# Or, with existing_vpc_id, in an existing VPC whose private subnets already
# route out through a NAT (gateway or instance): then no VPC, subnet, internet
# gateway, NAT, route or S3 endpoint is created, only the run's own security
# groups, placement group, bucket, roles and instances.

locals {
  two_host     = var.topology == "two-host"
  name         = "vericto-bench-${var.run_id}"
  repo_root    = abspath("${path.module}/../..")
  auto_hours   = { quick = 3, "m2-quick" = 9, "m2-mysql-ab" = 5, "m2-fix-ab" = 5, c7i = 14, day2 = 24, published = 132 }
  max_hours    = var.max_hours > 0 ? var.max_hours : lookup(local.auto_hours, var.suite, 30)
  max_minutes  = local.max_hours * 60
  day          = var.day > 0 ? var.day : (var.suite == "day2" ? 2 : 1)
  harness_key  = "${var.run_id}/harness/harness.zip"
  ssh_key_name = "/vericto-bench/${var.run_id}/sut-ssh-key"

  # Every instance type in play, to pick an AZ that offers all of them.
  instance_types = distinct(local.two_host ? [var.sut_instance_type, var.loadgen_instance_type] : [var.sut_instance_type])

  offered       = data.aws_ec2_instance_type_offerings.az.locations
  offered_types = data.aws_ec2_instance_type_offerings.az.instance_types
  az_candidates = sort([
    for az in distinct(local.offered) : az
    if alltrue([
      for t in local.instance_types : contains([
        for i, l in local.offered : local.offered_types[i] if l == az
      ], t)
    ])
  ])
  own_network = var.existing_vpc_id == ""

  # Existing network: the hosts go to existing_placement_subnet_id, or else to the
  # first of existing_subnet_ids whose AZ offers every instance type. A cluster
  # placement group is one AZ, so both hosts share that one subnet.
  existing_subnet_az = { for id, sn in data.aws_subnet.existing : id => sn.availability_zone }
  existing_placement = var.existing_placement_subnet_id != "" ? var.existing_placement_subnet_id : try(
    [for id in var.existing_subnet_ids : id if contains(local.az_candidates, local.existing_subnet_az[id])][0], ""
  )

  az = (local.own_network
    ? (var.availability_zone != "" ? var.availability_zone : local.az_candidates[0])
    : try(local.existing_subnet_az[local.existing_placement], data.aws_subnet.placement[0].availability_zone)
  )
  vpc_id         = local.own_network ? one(aws_vpc.bench[*].id) : var.existing_vpc_id
  host_subnet_id = local.own_network ? one(aws_subnet.private[*].id) : local.existing_placement

  # Bench ports the SUT accepts from the load generator (two-host only).
  # 5432/3306 databases (direct), 6432-6433/6306-6307 vericto-proxy (1st, 2nd task),
  # 7432/7306 HAProxy, 8432 PgBouncer, 8306 ProxySQL. 22 = docker over SSH and
  # the hostmon stream.
  sut_ports = [
    { from = 22, to = 22 },
    { from = 5432, to = 5432 },
    { from = 3306, to = 3306 },
    { from = 6432, to = 6433 },
    { from = 6306, to = 6307 },
    { from = 7432, to = 7432 },
    { from = 7306, to = 7306 },
    { from = 8432, to = 8432 },
    { from = 8306, to = 8306 },
  ]
}

# ---------------------------------------------------------------- lookups

data "aws_ec2_instance_type_offerings" "az" {
  location_type = "availability-zone"

  filter {
    name   = "instance-type"
    values = local.instance_types
  }
}

data "aws_ec2_instance_type" "sut" {
  instance_type = var.sut_instance_type
}

data "aws_ec2_instance_type" "loadgen" {
  instance_type = var.loadgen_instance_type
}

locals {
  sut_arch     = contains(data.aws_ec2_instance_type.sut.supported_architectures, "arm64") ? "arm64" : "x86_64"
  loadgen_arch = contains(data.aws_ec2_instance_type.loadgen.supported_architectures, "arm64") ? "arm64" : "x86_64"
}

# Amazon Linux 2023, latest, per architecture (public SSM parameters).
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

data "aws_ssm_parameter" "al2023_x86_64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  ami = {
    arm64  = nonsensitive(data.aws_ssm_parameter.al2023_arm64.value)
    x86_64 = nonsensitive(data.aws_ssm_parameter.al2023_x86_64.value)
  }
}

data "aws_partition" "current" {}

data "aws_subnet" "existing" {
  for_each = local.own_network ? toset([]) : toset(var.existing_subnet_ids)
  id       = each.value
}

data "aws_subnet" "placement" {
  count = !local.own_network && var.existing_placement_subnet_id != "" && !contains(var.existing_subnet_ids, var.existing_placement_subnet_id) ? 1 : 0
  id    = var.existing_placement_subnet_id
}

# ---------------------------------------------------------------- network

resource "aws_vpc" "bench" {
  count = local.own_network ? 1 : 0

  cidr_block           = "10.81.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = local.name }
}

resource "aws_internet_gateway" "bench" {
  count = local.own_network ? 1 : 0

  vpc_id = aws_vpc.bench[0].id
  tags   = { Name = local.name }
}

# Public subnet: holds only the NAT gateway. No instance has a public IP.
resource "aws_subnet" "public" {
  count = local.own_network ? 1 : 0

  vpc_id                  = aws_vpc.bench[0].id
  cidr_block              = "10.81.0.0/24"
  availability_zone       = local.az
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-nat" }
}

resource "aws_subnet" "private" {
  count = local.own_network ? 1 : 0

  vpc_id                  = aws_vpc.bench[0].id
  cidr_block              = "10.81.1.0/24"
  availability_zone       = local.az
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-private" }
}

resource "aws_eip" "nat" {
  count = local.own_network ? 1 : 0

  domain = "vpc"
  tags   = { Name = "${local.name}-nat" }
}

resource "aws_nat_gateway" "bench" {
  count = local.own_network ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = local.name }

  depends_on = [aws_internet_gateway.bench]
}

resource "aws_route_table" "public" {
  count = local.own_network ? 1 : 0

  vpc_id = aws_vpc.bench[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.bench[0].id
  }

  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  count = local.own_network ? 1 : 0

  subnet_id      = aws_subnet.public[0].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table" "private" {
  count = local.own_network ? 1 : 0

  vpc_id = aws_vpc.bench[0].id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.bench[0].id
  }

  tags = { Name = "${local.name}-private" }
}

resource "aws_route_table_association" "private" {
  count = local.own_network ? 1 : 0

  subnet_id      = aws_subnet.private[0].id
  route_table_id = aws_route_table.private[0].id
}

# S3 traffic (harness download, results upload) stays off the NAT gateway.
resource "aws_vpc_endpoint" "s3" {
  count = local.own_network ? 1 : 0

  vpc_id            = aws_vpc.bench[0].id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private[0].id]
  tags              = { Name = "${local.name}-s3" }
}

# The load generator: zero inbound rules.
resource "aws_security_group" "loadgen" {
  name        = "${local.name}-loadgen"
  description = "vericto-bench load generator: no inbound access"
  vpc_id      = local.vpc_id

  egress {
    description = "Image pulls, SSM, S3, the SUT"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-loadgen" }
}

# The system under test: inbound only from the load generator's security group,
# only on SSH and the bench ports. In the single topology it has no inbound rule.
resource "aws_security_group" "sut" {
  name        = "${local.name}-sut"
  description = "vericto-bench SUT: inbound only from the load generator SG"
  vpc_id      = local.vpc_id

  dynamic "ingress" {
    for_each = local.two_host ? local.sut_ports : []
    content {
      description     = "From the load generator"
      from_port       = ingress.value.from
      to_port         = ingress.value.to
      protocol        = "tcp"
      security_groups = [aws_security_group.loadgen.id]
    }
  }

  egress {
    description = "Image pulls, SSM, S3"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-sut" }
}

resource "aws_placement_group" "bench" {
  name     = local.name
  strategy = "cluster"
}

# ---------------------------------------------------------------- results bucket

resource "aws_s3_bucket" "results" {
  bucket_prefix = "vericto-bench-"
  # The README flow syncs the results before `terraform destroy`; teardown.sh
  # refuses to destroy if that sync failed.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    id     = "expire-30-days"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

data "aws_iam_policy_document" "bucket_tls_only" {
  statement {
    sid     = "DenyNonTLS"
    effect  = "Deny"
    actions = ["s3:*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    resources = [aws_s3_bucket.results.arn, "${aws_s3_bucket.results.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "results" {
  bucket     = aws_s3_bucket.results.id
  policy     = data.aws_iam_policy_document.bucket_tls_only.json
  depends_on = [aws_s3_bucket_public_access_block.results]
}

# The harness itself, built from this checkout (no git clone on the hosts, so a
# private fork works too).
data "archive_file" "harness" {
  type        = "zip"
  source_dir  = local.repo_root
  output_path = "${path.module}/.build/harness-${var.run_id}.zip"
  excludes = [
    ".git",
    ".github",
    "results",
    "compose/data",
    "terraform/aws/.terraform",
    "terraform/aws/.build",
    "terraform/aws/terraform.tfstate",
    "terraform/aws/terraform.tfstate.backup",
    "terraform/aws/results",
    "terraform/aws/run.tfplan",
    "terraform/aws/.terraform.tfstate.lock.info",
    "terraform/archive/.terraform",
    "terraform/archive/archive.tfplan",
    "terraform/archive/terraform.tfstate",
    "terraform/archive/terraform.tfstate.backup",
  ]
}

resource "aws_s3_object" "harness" {
  bucket      = aws_s3_bucket.results.id
  key         = local.harness_key
  source      = data.archive_file.harness.output_path
  source_hash = data.archive_file.harness.output_base64sha256
}

# ---------------------------------------------------------------- SSH key (two-host)

# Lets the load generator drive Docker on the SUT over SSH. Ephemeral: it is in
# the Terraform state and in one SecureString parameter, both destroyed with
# the stack.
resource "tls_private_key" "sut" {
  count     = local.two_host ? 1 : 0
  algorithm = "ED25519"
}

resource "aws_ssm_parameter" "sut_ssh_key" {
  count       = local.two_host ? 1 : 0
  name        = local.ssh_key_name
  description = "vericto-bench ${var.run_id}: private key the load generator uses to reach the SUT"
  type        = "SecureString"
  value       = tls_private_key.sut[0].private_key_openssh
}

# ---------------------------------------------------------------- IAM

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sut" {
  name_prefix        = "vbench-sut-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role" "loadgen" {
  count              = local.two_host ? 1 : 0
  name_prefix        = "vbench-loadgen-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "sut_ssm" {
  role       = aws_iam_role.sut.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "loadgen_ssm" {
  count      = local.two_host ? 1 : 0
  role       = aws_iam_role.loadgen[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# SUT: reads the harness. In the single topology it is also the runner, so it
# writes the results.
data "aws_iam_policy_document" "sut" {
  statement {
    sid       = "ReadHarness"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.results.arn}/${local.harness_key}"]
  }

  dynamic "statement" {
    for_each = local.two_host ? [] : [1]
    content {
      sid       = "WriteResults"
      actions   = ["s3:PutObject", "s3:GetObject"]
      resources = ["${aws_s3_bucket.results.arn}/${var.run_id}/*"]
    }
  }

  dynamic "statement" {
    for_each = local.two_host ? [] : [1]
    content {
      sid       = "ListResults"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.results.arn]
    }
  }
}

resource "aws_iam_role_policy" "sut" {
  name   = "vericto-bench"
  role   = aws_iam_role.sut.id
  policy = data.aws_iam_policy_document.sut.json
}

data "aws_iam_policy_document" "loadgen" {
  count = local.two_host ? 1 : 0

  statement {
    sid       = "ReadWriteRun"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.results.arn}/${var.run_id}/*"]
  }

  statement {
    sid       = "ListResults"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.results.arn]
  }

  statement {
    sid       = "ReadSutKey"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.sut_ssh_key[0].arn]
  }
}

resource "aws_iam_role_policy" "loadgen" {
  count  = local.two_host ? 1 : 0
  name   = "vericto-bench"
  role   = aws_iam_role.loadgen[0].id
  policy = data.aws_iam_policy_document.loadgen[0].json
}

# proxy_image_override in a private Amazon ECR repository (an unreleased
# candidate, pushed to a bench-only repository): both hosts may pull exactly
# that repository (host/pull-images.sh logs in with the host role).
locals {
  override_ecr = regex("^(?:([0-9]{12})\\.dkr\\.ecr\\.([a-z0-9-]+)\\.amazonaws\\.com/([^@:]+))?", var.proxy_image_override)
  override_ecr_repository_arn = local.override_ecr[0] == null ? "" : format(
    "arn:%s:ecr:%s:%s:repository/%s",
    data.aws_partition.current.partition, local.override_ecr[1], local.override_ecr[0], local.override_ecr[2]
  )
  hosts_pull_ecr = local.override_ecr_repository_arn != ""
}

data "aws_iam_policy_document" "ecr_pull" {
  count = local.hosts_pull_ecr ? 1 : 0

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "PullOverride"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = [local.override_ecr_repository_arn]
  }
}

resource "aws_iam_role_policy" "sut_ecr_pull" {
  count  = local.hosts_pull_ecr ? 1 : 0
  name   = "vericto-bench-ecr-pull"
  role   = aws_iam_role.sut.id
  policy = data.aws_iam_policy_document.ecr_pull[0].json
}

resource "aws_iam_role_policy" "loadgen_ecr_pull" {
  count  = local.hosts_pull_ecr && local.two_host ? 1 : 0
  name   = "vericto-bench-ecr-pull"
  role   = aws_iam_role.loadgen[0].id
  policy = data.aws_iam_policy_document.ecr_pull[0].json
}

resource "aws_iam_instance_profile" "sut" {
  name_prefix = "vbench-sut-"
  role        = aws_iam_role.sut.name
}

resource "aws_iam_instance_profile" "loadgen" {
  count       = local.two_host ? 1 : 0
  name_prefix = "vbench-loadgen-"
  role        = aws_iam_role.loadgen[0].name
}

# ---------------------------------------------------------------- instances

locals {
  common_vars = {
    run_id               = var.run_id
    suite                = var.suite
    topology             = var.topology
    bucket               = aws_s3_bucket.results.id
    harness_key          = local.harness_key
    region               = var.region
    max_minutes          = local.max_minutes
    auto_shutdown        = var.auto_shutdown ? "1" : "0"
    proxy_image_override = var.proxy_image_override
    harness_commit       = var.harness_commit
    day                  = local.day
  }
}

resource "aws_instance" "sut" {
  ami                                  = local.ami[local.sut_arch]
  instance_type                        = var.sut_instance_type
  subnet_id                            = local.host_subnet_id
  vpc_security_group_ids               = [aws_security_group.sut.id]
  iam_instance_profile                 = aws_iam_instance_profile.sut.name
  placement_group                      = aws_placement_group.bench.id
  associate_public_ip_address          = false
  instance_initiated_shutdown_behavior = "stop"
  monitoring                           = false
  ebs_optimized                        = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gib
    iops                  = 3000
    throughput            = 250
    encrypted             = true
    delete_on_termination = true
  }

  # Two-host: the SUT only prepares itself. Single: it is also the runner.
  user_data = local.two_host ? templatefile("${path.module}/../../host/userdata-sut.sh.tftpl", merge(local.common_vars, {
    sut_authorized_key = trimspace(tls_private_key.sut[0].public_key_openssh)
    })) : templatefile("${path.module}/../../host/userdata-loadgen.sh.tftpl", merge(local.common_vars, {
    role           = "single"
    sut_ip         = ""
    ssh_param_name = ""
  }))
  user_data_replace_on_change = true

  tags = { Name = local.two_host ? "${local.name}-sut" : "${local.name}-single" }

  lifecycle {
    precondition {
      condition     = local.own_network || (local.host_subnet_id != "" && contains(local.az_candidates, local.az))
      error_message = "existing_vpc_id: no subnet among existing_subnet_ids / existing_placement_subnet_id is in an AZ that offers every instance type of this run."
    }
  }

  depends_on = [
    aws_route_table_association.private,
    aws_nat_gateway.bench,
    aws_vpc_endpoint.s3,
    aws_s3_object.harness,
    aws_iam_role_policy.sut,
    aws_iam_role_policy.sut_ecr_pull,
  ]
}

resource "aws_instance" "loadgen" {
  count = local.two_host ? 1 : 0

  ami                                  = local.ami[local.loadgen_arch]
  instance_type                        = var.loadgen_instance_type
  subnet_id                            = local.host_subnet_id
  vpc_security_group_ids               = [aws_security_group.loadgen.id]
  iam_instance_profile                 = aws_iam_instance_profile.loadgen[0].name
  placement_group                      = aws_placement_group.bench.id
  associate_public_ip_address          = false
  instance_initiated_shutdown_behavior = "stop"
  monitoring                           = false
  ebs_optimized                        = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 40
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/../../host/userdata-loadgen.sh.tftpl", merge(local.common_vars, {
    role           = "loadgen"
    sut_ip         = aws_instance.sut.private_ip
    ssh_param_name = aws_ssm_parameter.sut_ssh_key[0].name
  }))
  user_data_replace_on_change = true

  tags = { Name = "${local.name}-loadgen" }

  depends_on = [aws_iam_role_policy.loadgen, aws_iam_role_policy.loadgen_ecr_pull]
}

# Before existing_vpc_id, the network resources had no count. A state from that
# version moves to index 0 instead of being destroyed and recreated.
moved {
  from = aws_vpc.bench
  to   = aws_vpc.bench[0]
}
moved {
  from = aws_internet_gateway.bench
  to   = aws_internet_gateway.bench[0]
}
moved {
  from = aws_subnet.public
  to   = aws_subnet.public[0]
}
moved {
  from = aws_subnet.private
  to   = aws_subnet.private[0]
}
moved {
  from = aws_eip.nat
  to   = aws_eip.nat[0]
}
moved {
  from = aws_nat_gateway.bench
  to   = aws_nat_gateway.bench[0]
}
moved {
  from = aws_route_table.public
  to   = aws_route_table.public[0]
}
moved {
  from = aws_route_table_association.public
  to   = aws_route_table_association.public[0]
}
moved {
  from = aws_route_table.private
  to   = aws_route_table.private[0]
}
moved {
  from = aws_route_table_association.private
  to   = aws_route_table_association.private[0]
}
moved {
  from = aws_vpc_endpoint.s3
  to   = aws_vpc_endpoint.s3[0]
}
