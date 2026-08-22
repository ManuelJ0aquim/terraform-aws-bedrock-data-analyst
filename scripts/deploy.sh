#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"

echo "=========================================="
echo " AWS Bedrock Data Analyst - Deploy"
echo "=========================================="
echo
echo "Project root: $PROJECT_ROOT"
echo "Terraform dir: $INFRA_DIR"
echo

command -v terraform >/dev/null 2>&1 || {
    echo "ERROR: Terraform is not installed or not in PATH."
    exit 1
}

command -v aws >/dev/null 2>&1 || {
    echo "ERROR: AWS CLI is not installed or not in PATH."
    exit 1
}

echo "Checking AWS credentials..."
aws sts get-caller-identity

echo
echo "Initializing Terraform..."
cd "$INFRA_DIR"
terraform init

echo
echo "Validating Terraform configuration..."
terraform validate

echo
echo "Creating deployment plan..."
terraform plan -out=tfplan

echo
echo "Applying Terraform configuration..."
terraform apply tfplan

rm -f tfplan

echo
echo "=========================================="
echo " Deployment completed successfully"
echo "=========================================="