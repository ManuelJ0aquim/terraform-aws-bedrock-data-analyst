#!/usr/bin/env bash
set -euo pipefail

# ==========================================
#  AWS Bedrock Data Analyst - Test
# ==========================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/infra"
EVENT_FILE="${PROJECT_ROOT}/event.json"
RESPONSE_FILE="${PROJECT_ROOT}/response.json"

echo "=========================================="
echo " AWS Bedrock Data Analyst - Test"
echo "=========================================="
echo ""
echo "Project root:  ${PROJECT_ROOT}"
echo "Terraform dir: ${TERRAFORM_DIR}"
echo ""

# ------------------------------------------
# 1. Verify dependencies
# ------------------------------------------
if ! command -v terraform &> /dev/null; then
  echo "Error: Terraform is not installed or not in PATH."
  exit 1
fi

if ! command -v aws &> /dev/null; then
  echo "Error: AWS CLI is not installed or not in PATH."
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed or not in PATH."
  echo "Install it with: sudo apt-get install jq  (or) brew install jq"
  exit 1
fi

# ------------------------------------------
# 2. Verify AWS credentials
# ------------------------------------------
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
  echo "Error: AWS credentials are not configured or are invalid."
  echo "Run 'aws configure' and try again."
  exit 1
fi
aws sts get-caller-identity
echo ""

# ------------------------------------------
# 3. Read Lambda function name and region from Terraform outputs
# ------------------------------------------
echo "Reading Lambda function name from Terraform outputs..."
LAMBDA_FUNCTION_NAME=$(terraform -chdir="${TERRAFORM_DIR}" output -raw lambda_function_name 2>/dev/null || true)
AWS_REGION_OUT=$(terraform -chdir="${TERRAFORM_DIR}" output -raw aws_region 2>/dev/null || true)

if [ -z "${LAMBDA_FUNCTION_NAME}" ]; then
  echo "Error: Could not read 'lambda_function_name' from Terraform outputs."
  echo "Make sure the infrastructure has been deployed with ./scripts/deploy.sh"
  exit 1
fi

echo "Lambda function: ${LAMBDA_FUNCTION_NAME}"
[ -n "${AWS_REGION_OUT}" ] && echo "Region:          ${AWS_REGION_OUT}"
echo ""

# ------------------------------------------
# 4. Verify event.json exists
# ------------------------------------------
if [ ! -f "${EVENT_FILE}" ]; then
  echo "Error: event.json not found at ${EVENT_FILE}"
  exit 1
fi

echo "Using test event:"
cat "${EVENT_FILE}"
echo ""
echo ""

# ------------------------------------------
# 5. Invoke the Lambda function
# ------------------------------------------
echo "Invoking Lambda function..."
echo ""

INVOKE_ARGS=(
  lambda invoke
  --function-name "${LAMBDA_FUNCTION_NAME}"
  --cli-binary-format raw-in-base64-out
  --payload "fileb://${EVENT_FILE}"
  --log-type Tail
  "${RESPONSE_FILE}"
  --query 'StatusCode'
  --output text
)

if [ -n "${AWS_REGION_OUT}" ]; then
  INVOKE_ARGS=(--region "${AWS_REGION_OUT}" "${INVOKE_ARGS[@]}")
fi

HTTP_STATUS=$(aws "${INVOKE_ARGS[@]}")

echo "Lambda invocation HTTP status: ${HTTP_STATUS}"
echo ""

# ------------------------------------------
# 6. Display the response
# ------------------------------------------
if [ ! -f "${RESPONSE_FILE}" ]; then
  echo "Error: No response was saved to ${RESPONSE_FILE}"
  exit 1
fi

echo "=========================================="
echo " Lambda Response"
echo "=========================================="
if jq . "${RESPONSE_FILE}" &> /dev/null; then
  jq . "${RESPONSE_FILE}"
else
  cat "${RESPONSE_FILE}"
fi
echo ""

# ------------------------------------------
# 7. Basic result check
# ------------------------------------------
STATUS_CODE=$(jq -r '.statusCode // empty' "${RESPONSE_FILE}" 2>/dev/null || true)

if [ "${STATUS_CODE}" = "200" ]; then
  echo "=========================================="
  echo " Test completed successfully"
  echo "=========================================="
elif [ -n "${STATUS_CODE}" ]; then
  echo "=========================================="
  echo " Test completed with statusCode ${STATUS_CODE}"
  echo " Check response.json and CloudWatch logs for details"
  echo "=========================================="
else
  echo "=========================================="
  echo " Test completed - review response.json for details"
  echo "=========================================="
fi

echo ""
echo "Response saved to: ${RESPONSE_FILE}"
LOG_GROUP=$(terraform -chdir="${TERRAFORM_DIR}" output -raw lambda_log_group 2>/dev/null || true)
if [ -n "${LOG_GROUP}" ]; then
  echo "View logs with:    aws logs tail \"${LOG_GROUP}\" --follow"
fi