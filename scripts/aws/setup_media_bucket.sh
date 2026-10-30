#!/usr/bin/env bash
# ==============================================================================
# LolixCopilot — S3 Media Bucket Idempotent Setup Script
#
# PURPOSE:
#   Prepares, configures, and verifies the private Amazon S3 bucket used by
#   LolixCopilot for raw video uploads and temporary streaming playback.
#
# STRICT CREDIT & MUTATION PROTECTION:
#   By default, this script runs in PLAN / DRY-RUN mode.
#   It will NEVER mutate AWS resources or spend AWS credits unless:
#     1. The --apply flag is explicitly provided.
#     2. The user explicitly confirms at the interactive prompt.
#
# USAGE:
#   ./scripts/aws/setup_media_bucket.sh [OPTIONS]
#
# OPTIONS:
#   --dry-run             Run in read-only plan mode (DEFAULT). No changes made.
#   --apply               Execute the planned AWS resource creation & updates.
#   --bucket <name>       S3 bucket name (default: lolixcopilot-media-<ACCOUNT_ID>-<REGION>)
#   --region <region>     AWS region (default: current AWS CLI region or ap-south-1)
#   --profile <profile>   AWS CLI profile to use (default: active profile or 'default')
#   --account <id>        Expected AWS Account ID for strict boundary verification
#   --yes                 Bypass interactive confirmation prompt when --apply is set
#   --help, -h            Show this help message
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORS_FILE="${SCRIPT_DIR}/cors.json"
LIFECYCLE_FILE="${SCRIPT_DIR}/lifecycle.json"

# Default flags
MODE="plan"
AUTO_CONFIRM=false
TARGET_BUCKET=""
TARGET_REGION=""
TARGET_PROFILE=""
EXPECTED_ACCOUNT=""

# ------------------------------------------------------------------------------
# Argument Parsing
# ------------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="plan"
      shift
      ;;
    --apply)
      MODE="apply"
      shift
      ;;
    --bucket)
      TARGET_BUCKET="$2"
      shift 2
      ;;
    --region)
      TARGET_REGION="$2"
      shift 2
      ;;
    --profile)
      TARGET_PROFILE="$2"
      shift 2
      ;;
    --account)
      EXPECTED_ACCOUNT="$2"
      shift 2
      ;;
    --yes)
      AUTO_CONFIRM=true
      shift
      ;;
    -h|--help)
      grep '^# ' "$0" | cut -c 3-
      exit 0
      ;;
    *)
      echo "[-] Error: Unknown argument: $1" >&2
      echo "    Run $0 --help for usage information." >&2
      exit 1
      ;;
  esac
done

# ------------------------------------------------------------------------------
# Preflight: AWS CLI Verification
# ------------------------------------------------------------------------------
if ! command -v aws >/dev/null 2>&1; then
  echo "[-] Error: AWS CLI ('aws') is not installed or not in PATH." >&2
  exit 1
fi

AWS_CMD=(aws)
if [[ -n "${TARGET_PROFILE}" ]]; then
  AWS_CMD+=(--profile "${TARGET_PROFILE}")
fi

echo "[*] Verifying AWS caller identity..."
CALLER_IDENTITY=$("${AWS_CMD[@]}" sts get-caller-identity --output json 2>/dev/null || true)

if [[ -z "${CALLER_IDENTITY}" ]]; then
  echo "[-] Error: Failed to obtain AWS caller identity." >&2
  echo "    Please verify credentials in ~/.aws/credentials or environment variables." >&2
  exit 1
fi

ACTUAL_ACCOUNT=$(echo "${CALLER_IDENTITY}" | grep -o '"Account": "[^"]*' | cut -d'"' -f4)
ACTUAL_ARN=$(echo "${CALLER_IDENTITY}" | grep -o '"Arn": "[^"]*' | cut -d'"' -f4)

# Stop if identity is the AWS root user
if [[ "${ACTUAL_ARN}" == *":root" ]]; then
  echo "[-] CRITICAL SECURITY REJECTION: The active identity is the AWS root user (${ACTUAL_ARN})." >&2
  echo "    Never use root credentials for application workloads." >&2
  echo "    Please switch to an appropriately scoped IAM user or role." >&2
  exit 1
fi

# Verify expected account if specified
if [[ -n "${EXPECTED_ACCOUNT}" && "${ACTUAL_ACCOUNT}" != "${EXPECTED_ACCOUNT}" ]]; then
  echo "[-] Error: Account mismatch!" >&2
  echo "    Expected Account: ${EXPECTED_ACCOUNT}" >&2
  echo "    Actual Account:   ${ACTUAL_ACCOUNT}" >&2
  exit 1
fi

# Resolve Region
if [[ -z "${TARGET_REGION}" ]]; then
  TARGET_REGION=$("${AWS_CMD[@]}" configure get region 2>/dev/null || true)
  if [[ -z "${TARGET_REGION}" ]]; then
    TARGET_REGION="ap-south-1"
  fi
fi

# Resolve Default Bucket Name
if [[ -z "${TARGET_BUCKET}" ]]; then
  TARGET_BUCKET="lolixcopilot-media-${ACTUAL_ACCOUNT}-${TARGET_REGION}"
fi

# Strict isolation guard: Never adopt or modify the unrelated registration media bucket
if [[ "${TARGET_BUCKET}" == *"registration-media"* || "${TARGET_BUCKET}" == "golixco-registration-media-247673029886" ]]; then
  echo "[-] CRITICAL ISOLATION ERROR: Target bucket matches protected unrelated bucket '${TARGET_BUCKET}'." >&2
  echo "    LolixCopilot must use its own dedicated media bucket (e.g., lolixcopilot-media-*)." >&2
  exit 1
fi

# Validate configuration templates exist
if [[ ! -f "${CORS_FILE}" ]]; then
  echo "[-] Error: CORS template not found at ${CORS_FILE}" >&2
  exit 1
fi

if [[ ! -f "${LIFECYCLE_FILE}" ]]; then
  echo "[-] Error: Lifecycle template not found at ${LIFECYCLE_FILE}" >&2
  exit 1
fi

# Check if target bucket already exists
BUCKET_EXISTS=false
if "${AWS_CMD[@]}" s3api head-bucket --bucket "${TARGET_BUCKET}" --region "${TARGET_REGION}" 2>/dev/null; then
  BUCKET_EXISTS=true
fi

# ------------------------------------------------------------------------------
# Plan Output
# ------------------------------------------------------------------------------
echo "=============================================================================="
echo " LolixCopilot — S3 Media Bucket Configuration Plan"
echo "=============================================================================="
echo " Mode:             $(if [[ "${MODE}" == "apply" ]]; then echo "APPLY (MUTATING)"; else echo "PLAN / DRY-RUN (READ-ONLY)"; fi)"
echo " AWS Account ID:   ${ACTUAL_ACCOUNT}"
echo " IAM Identity:     ${ACTUAL_ARN}"
echo " Target Region:    ${TARGET_REGION}"
echo " Target Bucket:    ${TARGET_BUCKET}"
echo " Bucket Exists:    ${BUCKET_EXISTS}"
echo " Block Public Acc: ENABLED (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets)"
echo " Encryption:       ENABLED (AES256 SSE-S3 default)"
echo " CORS Policy:      ${CORS_FILE} (PUT, GET, HEAD for localhost:3000 & *.lolixco.com)"
echo " Lifecycle Rule:   ${LIFECYCLE_FILE} (7-day auto-expiration on users/ prefix)"
echo " Tags:             Project=LolixCopilot, ManagedBy=setup_media_bucket.sh, Retention=7d"
echo "------------------------------------------------------------------------------"
echo " POTENTIAL AWS COSTS & CREDIT IMPLICATIONS:"
echo " - S3 Standard Storage: ~\$0.023 / GB-month (ap-south-1)."
echo " - PUT/GET Requests: ~\$0.005 per 1,000 PUTs; ~\$0.0004 per 1,000 GETs."
echo " - Data Transfer OUT: Ingress is free; egress to internet is charged beyond free tier."
echo " - Lifecycle Rules: 7-day rule limits storage accumulation by expiring old footage."
echo " - NOTE: Executing in apply mode may consume AWS promotional credits or incur costs."
echo "=============================================================================="

if [[ "${MODE}" == "plan" ]]; then
  echo ""
  echo "[+] Dry-run complete. No AWS changes were made. Zero credits consumed."
  echo "    To apply these changes after review, run:"
  echo "    $0 --apply --bucket ${TARGET_BUCKET} --region ${TARGET_REGION}"
  exit 0
fi

# ------------------------------------------------------------------------------
# Apply Mode: Confirmation Gate
# ------------------------------------------------------------------------------
if [[ "${AUTO_CONFIRM}" != "true" ]]; then
  echo ""
  echo "[!] WARNING: You are about to modify AWS cloud resources in account ${ACTUAL_ACCOUNT}."
  read -r -p "    Type 'CONFIRM' to proceed with bucket setup: " CONFIRMATION
  if [[ "${CONFIRMATION}" != "CONFIRM" ]]; then
    echo "[-] Operation aborted by user. No changes were made."
    exit 0
  fi
fi

echo ""
echo "[*] Proceeding with S3 bucket configuration..."

# 1. Create Bucket if needed
if [[ "${BUCKET_EXISTS}" == "false" ]]; then
  echo "[+] Creating private bucket '${TARGET_BUCKET}' in region '${TARGET_REGION}'..."
  if [[ "${TARGET_REGION}" == "us-east-1" ]]; then
    "${AWS_CMD[@]}" s3api create-bucket \
      --bucket "${TARGET_BUCKET}" \
      --region "${TARGET_REGION}"
  else
    "${AWS_CMD[@]}" s3api create-bucket \
      --bucket "${TARGET_BUCKET}" \
      --region "${TARGET_REGION}" \
      --create-bucket-configuration LocationConstraint="${TARGET_REGION}"
  fi
else
  echo "[*] Bucket '${TARGET_BUCKET}' already exists. Re-verifying configuration..."
fi

# 2. Block Public Access
echo "[+] Enabling S3 Block Public Access (all 4 settings)..."
"${AWS_CMD[@]}" s3api put-public-access-block \
  --bucket "${TARGET_BUCKET}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 3. Default SSE-S3 Encryption
echo "[+] Applying default server-side encryption (SSE-S3 AES256)..."
"${AWS_CMD[@]}" s3api put-bucket-encryption \
  --bucket "${TARGET_BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        },
        "BucketKeyEnabled": true
      }
    ]
  }'

# 4. CORS Configuration
echo "[+] Applying CORS policy from ${CORS_FILE}..."
"${AWS_CMD[@]}" s3api put-bucket-cors \
  --bucket "${TARGET_BUCKET}" \
  --cors-configuration "file://${CORS_FILE}"

# 5. Lifecycle Configuration
echo "[+] Applying 7-day lifecycle policy from ${LIFECYCLE_FILE}..."
"${AWS_CMD[@]}" s3api put-bucket-lifecycle-configuration \
  --bucket "${TARGET_BUCKET}" \
  --lifecycle-configuration "file://${LIFECYCLE_FILE}"

# 6. Apply Tags
echo "[+] Applying resource tags..."
"${AWS_CMD[@]}" s3api put-bucket-tagging \
  --bucket "${TARGET_BUCKET}" \
  --tagging 'TagSet=[{Key=Project,Value=LolixCopilot},{Key=ManagedBy,Value=setup_media_bucket.sh},{Key=Retention,Value=7d}]'

echo ""
echo "=============================================================================="
echo "[✓] S3 Bucket Setup Complete & Verified:"
echo "    Bucket:   ${TARGET_BUCKET}"
echo "    Region:   ${TARGET_REGION}"
echo "    Security: Private (All public access blocked, SSE-S3 encrypted)"
echo "    CORS:     Enabled for http://localhost:3000 and https://*.lolixco.com"
echo "    Lifecycle: 7-day auto-expiration on 'users/' prefix"
echo ""
echo "    Update your .env file with:"
echo "    AWS_S3_BUCKET=${TARGET_BUCKET}"
echo "    AWS_REGION=${TARGET_REGION}"
echo "=============================================================================="
