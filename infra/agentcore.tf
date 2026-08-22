resource "aws_bedrockagentcore_code_interpreter" "data_analyst" {
  name        = "DataAnalystCodeInterpreter"
  description = "Code Interpreter for the AWS Data Analyst lab"

  execution_role_arn = aws_iam_role.code_interpreter.arn

  network_configuration {
    network_mode = "SANDBOX"
  }
}