#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"

echo "=========================================="
echo " AWS Bedrock Data Analyst - Destroy"
echo "=========================================="
echo

command -v terraform >/dev/null 2>&1 || {
    echo "ERROR: Terraform is not installed or not in PATH."
    exit 1
}

command -v aws >/dev/null 2>&1 || {
    echo "ERROR: AWS CLI is not installed or not in PATH."
    exit 1
}

cd "$INFRA_DIR"

echo "Current AWS identity:"
aws sts get-caller-identity

echo
echo "WARNING: This will destroy the Terraform-managed infrastructure."
echo
read -r -p "Type 'destroy' to continue: " confirmation

if [[ "$confirmation" != "destroy" ]]; then
    echo "Destroy cancelled."
    exit 0
fi

echo
echo "Running Terraform destroy..."
terraform destroy

echo
echo "=========================================="
echo " Infrastructure destroyed"
echo "=========================================="