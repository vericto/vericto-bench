# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.

variable "region" {
  description = "AWS region. The published campaign uses us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "availability_zone" {
  description = "AZ for both hosts. Empty = the first AZ (sorted) that offers every instance type used."
  type        = string
  default     = ""
}

variable "run_id" {
  description = "Identifier of this run, used in names, tags and the results prefix (e.g. bench-2026-11-p2-day1). Required: a timestamp default would change on every plan."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,40}$", var.run_id))
    error_message = "run_id must be 3-41 characters of lowercase letters, digits and dashes, starting with a letter or digit."
  }
}

variable "expires_on" {
  description = "ExpiresOn tag (YYYY-MM-DD) on every resource. Suggested: today + 3 days. Anything past it may be deleted by anyone in the account."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.expires_on))
    error_message = "expires_on must be a date in the form YYYY-MM-DD."
  }
}

variable "campaign" {
  description = "Campaign tag."
  type        = string
  default     = "BENCH-2026-11"
}

variable "suite" {
  description = "Suite to run: the name of a file suites/<suite>.toml (quick, published, day2, c7i, ...)."
  type        = string
  default     = "quick"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.suite))
    error_message = "suite must match ^[a-z0-9-]+$ (a file name under suites/ without .toml)."
  }
}

variable "topology" {
  description = "two-host (published: load generator on its own instance) or single (everything on one instance over loopback; cheaper reproduction, flagged in the manifest as not the published topology)."
  type        = string
  default     = "two-host"

  validation {
    condition     = contains(["two-host", "single"], var.topology)
    error_message = "topology must be two-host or single."
  }
}

variable "sut_instance_type" {
  description = "System under test: proxy, baselines, databases. c7g.2xlarge is the reference; c7i.2xlarge is the x86 cross-check. The AMI follows the instance type's architecture."
  type        = string
  default     = "c7g.2xlarge"
}

variable "loadgen_instance_type" {
  description = "Load generator (two-host topology only)."
  type        = string
  default     = "c7g.xlarge"
}

variable "root_volume_gib" {
  description = "Encrypted gp3 root volume size (databases live on it)."
  type        = number
  default     = 100
}

variable "proxy_image_override" {
  description = "Optional vericto-proxy image by digest (repo@sha256:...) instead of the one in versions.lock. Recorded in the manifest."
  type        = string
  default     = ""

  validation {
    condition     = var.proxy_image_override == "" || can(regex("@sha256:[0-9a-f]{64}$", var.proxy_image_override))
    error_message = "proxy_image_override must be pinned by digest (...@sha256:<64 hex>)."
  }
}

variable "auto_shutdown" {
  description = "Stop both instances when the suite ends (results are uploaded first)."
  type        = bool
  default     = true
}

variable "max_hours" {
  description = "Hard runtime guard: every host schedules `shutdown -h` this many hours after boot. 0 = automatic: quick 3, m2-quick 9, c7i 14, day2 24, published 132 (the planner's upper bound of 118 h plus setup), otherwise 30."
  type        = number
  default     = 0

  validation {
    condition     = var.max_hours >= 0 && var.max_hours <= 144
    error_message = "max_hours must be between 0 (automatic) and 144."
  }
}

variable "harness_commit" {
  description = "Commit of this checkout (git rev-parse HEAD), recorded in the run's manifest; the archive sent to the hosts carries no .git. Empty = \"unknown\"."
  type        = string
  default     = ""

  validation {
    condition     = var.harness_commit == "" || can(regex("^[0-9a-f]{7,40}$", var.harness_commit))
    error_message = "harness_commit must be a git commit id (hex)."
  }
}

variable "day" {
  description = "Campaign day recorded in every cell (runner --day). 0 = automatic: 2 for suite=day2, otherwise 1."
  type        = number
  default     = 0

  validation {
    condition     = var.day >= 0 && var.day <= 9
    error_message = "day must be between 0 (automatic) and 9."
  }
}
