#!/usr/bin/env bash
# Deploy script for LolixCopilot AWS Lambda Media Processor
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
FUNCTION_NAME="${AWS_LAMBDA_MEDIA_FUNCTION:-lolixcopilot-media-processor}"
ROLE_NAME="LolixCopilotLambdaExecutionRole"
BUCKET_NAME="${AWS_S3_BUCKET:-lolixcopilot-media-247673029886-ap-south-1}"
PACKAGE_TMP_DIR="/tmp/lambda_media_processor_pkg"
ZIP_OUTPUT="/tmp/media_processor.zip"

echo "=== LolixCopilot Lambda Deployment ==="
echo "Region:        ${REGION}"
echo "Function Name: ${FUNCTION_NAME}"
echo "S3 Bucket:     ${BUCKET_NAME}"

# 1. Ensure static ffmpeg binary is present
STATIC_FFMPEG_SRC=""
for candidate in \
  ".venv/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2" \
  "/usr/bin/ffmpeg" \
  "$(which ffmpeg 2>/dev/null || true)"; do
  if [ -n "${candidate}" ] && [ -f "${candidate}" ] && [ -x "${candidate}" ]; then
    STATIC_FFMPEG_SRC="${candidate}"
    break
  fi
done

if [ -z "${STATIC_FFMPEG_SRC}" ]; then
  echo "ERROR: Static Linux FFmpeg binary not found." >&2
  exit 1
fi
echo "Using FFmpeg source: ${STATIC_FFMPEG_SRC}"

# 2. Package Lambda zip
rm -rf "${PACKAGE_TMP_DIR}" "${ZIP_OUTPUT}"
mkdir -p "${PACKAGE_TMP_DIR}"
cp workers/lambda_media_processor/handler.py "${PACKAGE_TMP_DIR}/handler.py"
cp "${STATIC_FFMPEG_SRC}" "${PACKAGE_TMP_DIR}/ffmpeg"
chmod +x "${PACKAGE_TMP_DIR}/ffmpeg"

echo "Compressing deployment package..."
(cd "${PACKAGE_TMP_DIR}" && zip -9 -q "${ZIP_OUTPUT}" handler.py ffmpeg)
PACKAGE_SIZE=$(du -h "${ZIP_OUTPUT}" | cut -f1)
echo "Package created at ${ZIP_OUTPUT} (${PACKAGE_SIZE})"

# 3. Upload to S3
echo "Uploading package to s3://${BUCKET_NAME}/lambda/media_processor.zip..."
aws s3 cp "${ZIP_OUTPUT}" "s3://${BUCKET_NAME}/lambda/media_processor.zip" --region "${REGION}"

# 4. Check / Update / Create Lambda function
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query "Role.Arn" --output text 2>/dev/null || true)
if [ -z "${ROLE_ARN}" ]; then
  echo "Creating IAM role ${ROLE_NAME}..."
  ROLE_ARN=$(aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --query "Role.Arn" --output text)
  aws iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name LolixCopilotS3Access \
    --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:HeadObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::${BUCKET_NAME}\",\"arn:aws:s3:::${BUCKET_NAME}/*\"]}]}"
  sleep 5
fi

if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo "Updating existing Lambda function code..."
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --s3-bucket "${BUCKET_NAME}" \
    --s3-key "lambda/media_processor.zip" \
    --region "${REGION}" >/dev/null
  echo "Lambda function updated successfully."
else
  echo "Creating new Lambda function..."
  aws lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --runtime python3.12 \
    --role "${ROLE_ARN}" \
    --handler handler.lambda_handler \
    --code "S3Bucket=${BUCKET_NAME},S3Key=lambda/media_processor.zip" \
    --timeout 300 \
    --memory-size 2048 \
    --ephemeral-storage '{"Size": 2048}' \
    --region "${REGION}" \
    --description "LolixCopilot Serverless Media Processing Worker" >/dev/null
  echo "Lambda function created successfully."
fi

echo "=== Deployment Complete ==="
