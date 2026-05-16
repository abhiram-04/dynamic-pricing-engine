#!/usr/bin/env bash
# deploy/scripts/deploy.sh
# One-time first deploy script. Run this ONCE to bootstrap AWS infrastructure.
# After this, GitHub Actions handles all future deployments automatically.
#
# Prerequisites:
#   - AWS CLI configured: aws configure
#   - Terraform >= 1.7 installed
#   - Docker running
#   - Domain name with SSL cert in ACM (or change HTTPS to HTTP for testing)
#
# Usage:
#   chmod +x deploy/scripts/deploy.sh
#   ./deploy/scripts/deploy.sh

set -euo pipefail

# ── Config — edit these ───────────────────────────────────────────────────────
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
APP_NAME="pricing-engine"
ENVIRONMENT="staging"   # Change to "prod" for production
ACM_CERT_ARN=""         # Paste your ACM certificate ARN here
TF_STATE_BUCKET="${APP_NAME}-tfstate-${AWS_ACCOUNT_ID}"

echo "========================================"
echo " Dynamic Pricing Engine — AWS Deploy"
echo " Account: ${AWS_ACCOUNT_ID}"
echo " Region:  ${AWS_REGION}"
echo " Env:     ${ENVIRONMENT}"
echo "========================================"

# ── Step 1: Create Terraform state bucket ────────────────────────────────────
echo ""
echo "[1/7] Creating Terraform state bucket..."
aws s3api create-bucket \
  --bucket "${TF_STATE_BUCKET}" \
  --region "${AWS_REGION}" 2>/dev/null || echo "  Bucket already exists, skipping."

aws s3api put-bucket-versioning \
  --bucket "${TF_STATE_BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${TF_STATE_BUCKET}" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name "${APP_NAME}-tflock" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${AWS_REGION}" 2>/dev/null || echo "  DynamoDB table already exists, skipping."

# ── Step 2: Terraform init + apply ───────────────────────────────────────────
echo ""
echo "[2/7] Initialising Terraform..."
cd deploy/terraform

# Update backend bucket name in main.tf
sed -i "s/my-pricing-engine-tfstate/${TF_STATE_BUCKET}/" main.tf

terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="region=${AWS_REGION}"

echo ""
echo "[3/7] Applying Terraform (this takes ~10 min)..."
terraform apply \
  -var="environment=${ENVIRONMENT}" \
  -var="aws_region=${AWS_REGION}" \
  -var="app_name=${APP_NAME}" \
  -var="acm_certificate_arn=${ACM_CERT_ARN:-arn:aws:acm:us-east-1:000000000000:certificate/placeholder}" \
  -auto-approve

# Capture outputs
ECR_API_URL=$(terraform output -raw ecr_api_url)
ECR_WORKER_URL=$(terraform output -raw ecr_worker_url)
S3_MODELS=$(terraform output -raw s3_models_bucket)
ALB_DNS=$(terraform output -raw alb_dns_name)
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)

cd ../..

# ── Step 3: Train models locally and upload to S3 ────────────────────────────
echo ""
echo "[4/7] Training models and uploading to S3..."
python scripts/train.py --products 50 --records 20000
aws s3 sync models/saved/ "s3://${S3_MODELS}/models/saved/" --delete
echo "  Models uploaded to s3://${S3_MODELS}/models/saved/"

# ── Step 4: Build and push Docker image ──────────────────────────────────────
echo ""
echo "[5/7] Building and pushing Docker image to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build \
  -f deploy/docker/Dockerfile \
  -t "${ECR_API_URL}:latest" \
  -t "${ECR_API_URL}:$(git rev-parse --short HEAD)" \
  .

docker push "${ECR_API_URL}:latest"
docker push "${ECR_API_URL}:$(git rev-parse --short HEAD)"
echo "  Image pushed: ${ECR_API_URL}:latest"

# ── Step 5: Force new ECS deployment ─────────────────────────────────────────
echo ""
echo "[6/7] Deploying to ECS..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${APP_NAME}-api" \
  --force-new-deployment \
  --region "${AWS_REGION}" > /dev/null

echo "  Waiting for ECS service to stabilise (up to 5 min)..."
aws ecs wait services-stable \
  --cluster "${ECS_CLUSTER}" \
  --services "${APP_NAME}-api" \
  --region "${AWS_REGION}"

# ── Step 6: Smoke test ───────────────────────────────────────────────────────
echo ""
echo "[7/7] Running smoke test..."
sleep 15   # give ALB health checks time to pass

HEALTH=$(curl -sf "http://${ALB_DNS}/api/v1/health" 2>/dev/null || echo "failed")
if echo "${HEALTH}" | grep -q '"status":"ok"'; then
  echo "  Health check: PASSED"
else
  echo "  Health check: FAILED — check ECS logs"
  echo "  ${HEALTH}"
  exit 1
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " Deploy complete!"
echo ""
echo " API endpoint:    http://${ALB_DNS}/api/v1"
echo " Swagger UI:      http://${ALB_DNS}/docs"
echo " ECS cluster:     ${ECS_CLUSTER}"
echo " Model store:     s3://${S3_MODELS}"
echo ""
echo " Next: point your domain at ${ALB_DNS}"
echo "       and add GitHub Secrets for CI/CD."
echo "========================================"
