variable "aws_region" {
  description = "AWS region where the lab will be deployed"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name used to identify the lab resources"
  type        = string
  default     = "bedrock-data-analyst"
}

variable "lambda_runtime" {
  description = "Runtime used by the Lambda orchestrator"
  type        = string
  default     = "python3.12"
}

variable "environment" {
  description = "Ambiente onde o lab será deployado."
  type        = string
  default     = "dev"
}