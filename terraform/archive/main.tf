# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
#
# A long-lived bucket for a campaign's raw data. The run stack (terraform/aws)
# is destroyed after every run, bucket included; its results tarballs are copied
# here first when they are too big for git (the repository then commits the
# manifest and SHA256SUMS). Private, encrypted, TLS only, versioned, never
# force-destroyed. ExpiresOn says when its maintainers should decide to publish the
# data (release assets) or delete it.
#
#   cd terraform/archive && terraform init && terraform apply -var expires_on=2027-01-31
#   aws s3 cp results-<run_id>.tar.gz s3://$(terraform output -raw bucket)/<run_id>/

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "campaign" {
  type    = string
  default = "BENCH-2026-11"
}

variable "expires_on" {
  description = "ExpiresOn tag (YYYY-MM-DD): review date for the archived raw data."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.expires_on))
    error_message = "expires_on must be a date in the form YYYY-MM-DD."
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "vericto-bench"
      Campaign  = var.campaign
      Purpose   = "raw-data-archive"
      ExpiresOn = var.expires_on
      ManagedBy = "terraform"
    }
  }
}

resource "aws_s3_bucket" "archive" {
  bucket_prefix = "vericto-bench-archive-"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket                  = aws_s3_bucket.archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "archive" {
  bucket = aws_s3_bucket.archive.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyNonTLS"
    effect  = "Deny"
    actions = ["s3:*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    resources = [aws_s3_bucket.archive.arn, "${aws_s3_bucket.archive.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "archive" {
  bucket     = aws_s3_bucket.archive.id
  policy     = data.aws_iam_policy_document.tls_only.json
  depends_on = [aws_s3_bucket_public_access_block.archive]
}

output "bucket" {
  value = aws_s3_bucket.archive.id
}
