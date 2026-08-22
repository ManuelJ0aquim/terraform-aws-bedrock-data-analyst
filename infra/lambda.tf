data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../src/index.py"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "orchestrator" {
  function_name = "${var.project_name}-orchestrator"

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  role = aws_iam_role.lambda.arn

  handler = "index.lambda_handler"
  runtime = var.lambda_runtime

  timeout     = 300
  memory_size = 512

  environment {
    variables = {
      RAW_BUCKET          = aws_s3_bucket.raw_data.id
      RESULTS_BUCKET      = aws_s3_bucket.analysis_results.id
      CODE_INTERPRETER_ID = aws_bedrockagentcore_code_interpreter.data_analyst.code_interpreter_id
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda
  ]
}