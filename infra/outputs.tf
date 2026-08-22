output "aws_region" {
  description = "AWS region used by the lab"
  value       = var.aws_region
}

output "raw_data_bucket" {
  description = "S3 bucket containing raw data"
  value       = aws_s3_bucket.raw_data.bucket
}

output "raw_data_file" {
  description = "S3 URI of the sample sales file"
  value       = "s3://${aws_s3_bucket.raw_data.bucket}/${aws_s3_object.sample_sales.key}"
}

output "analysis_results_bucket" {
  description = "S3 bucket containing analysis results"
  value       = aws_s3_bucket.analysis_results.bucket
}

output "code_interpreter_id" {
  description = "AgentCore Code Interpreter identifier"
  value       = aws_bedrockagentcore_code_interpreter.data_analyst.code_interpreter_id
}

output "code_interpreter_arn" {
  description = "AgentCore Code Interpreter ARN"
  value       = aws_bedrockagentcore_code_interpreter.data_analyst.code_interpreter_arn
}

output "lambda_function_name" {
  description = "Lambda orchestrator function name"
  value       = aws_lambda_function.orchestrator.function_name
}

output "lambda_log_group" {
  description = "CloudWatch Log Group for the Lambda"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "lambda_error_alarm" {
  description = "CloudWatch alarm for Lambda errors"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}