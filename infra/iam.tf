# --- IAM Role & Policy: Lambda Orchestrator ---

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadRawData"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*"
        ]
      },
      {
        Sid    = "WriteAnalysisResults"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.analysis_results.arn}/*"
        ]
      },
      {
        Sid    = "BedrockInvokeModel"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        # Permitido em todas as regiões para que consiga ir buscar o Claude 3 Haiku a us-west-2
        Resource = "*"
      },
      {
        Sid    = "BedrockMarketplace"
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      },
      {
        Sid    = "BedrockCodeInterpreter"
        Effect = "Allow"
        # Atualizado para bater certo com os novos métodos do SDK bedrock-agent-runtime
        Action = [
          "bedrock:StartSession",
          "bedrock:OptimizeAndExecuteCode",
          "bedrock:EndSession"
        ]
        # Mapeamento global necessário para as interações dinâmicas da sandbox
        Resource = "*"
      }
    ]
  })
}

# --- IAM Role & Policy: Code Interpreter ---

resource "aws_iam_role" "code_interpreter" {
  name = "${var.project_name}-code-interpreter-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          # CORREÇÃO: Removida a string inválida e mantidos apenas os principais oficiais suportados pelo Bedrock AgentCore
          Service = [
            "bedrock.amazonaws.com",
            "bedrock-agentcore.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}



resource "aws_iam_role_policy" "code_interpreter" {
  name = "${var.project_name}-code-interpreter-policy"
  role = aws_iam_role.code_interpreter.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadRawData"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw_data.arn,
          "${aws_s3_bucket.raw_data.arn}/*"
        ]
      },
      {
        Sid    = "WriteAnalysisResults"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.analysis_results.arn}/*"
      }
    ]
  })
}
