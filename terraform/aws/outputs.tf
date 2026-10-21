# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Vericto S.A.S.

output "run_id" {
  value = var.run_id
}

output "topology" {
  value = var.topology
}

output "availability_zone" {
  value = local.az
}

output "results_bucket" {
  value = aws_s3_bucket.results.id
}

output "sut_instance_id" {
  value = aws_instance.sut.id
}

output "loadgen_instance_id" {
  description = "Empty in the single topology (the SUT runs the suite)."
  value       = local.two_host ? aws_instance.loadgen[0].id : ""
}

output "ssm_start_session" {
  description = "Open a shell on each host (needs the Session Manager plugin). Progress: /var/log/vericto-bench/."
  value = compact([
    "aws ssm start-session --region ${var.region} --target ${aws_instance.sut.id}",
    local.two_host ? "aws ssm start-session --region ${var.region} --target ${aws_instance.loadgen[0].id}" : "",
  ])
}

output "results_sync_command" {
  value = "aws s3 sync --region ${var.region} s3://${aws_s3_bucket.results.id}/${var.run_id}/ ./results/${var.run_id}/ --exclude 'harness/*'"
}

output "max_hours" {
  description = "Every host shuts itself down after this many hours, whatever happens."
  value       = local.max_hours
}

output "region" {
  value = var.region
}

output "day" {
  description = "Campaign day recorded in the run's cells."
  value       = local.day
}
