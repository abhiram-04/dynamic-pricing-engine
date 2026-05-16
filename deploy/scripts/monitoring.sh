#!/usr/bin/env bash
# deploy/scripts/monitoring.sh
# Sets up CloudWatch alarms for the pricing engine.
# Run after deploy.sh.
#
# Usage:
#   ./deploy/scripts/monitoring.sh

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
APP_NAME="${APP_NAME:-pricing-engine}"
ECS_CLUSTER="${ECS_CLUSTER:-pricing-engine-cluster}"
ALERT_EMAIL="${ALERT_EMAIL:-your-email@company.com}"   # ← change this

echo "Setting up CloudWatch monitoring for ${APP_NAME}..."

# ── SNS topic for alerts ──────────────────────────────────────────────────────
TOPIC_ARN=$(aws sns create-topic \
  --name "${APP_NAME}-alerts" \
  --query TopicArn \
  --output text)

aws sns subscribe \
  --topic-arn "${TOPIC_ARN}" \
  --protocol email \
  --notification-endpoint "${ALERT_EMAIL}"

echo "  SNS topic created: ${TOPIC_ARN}"
echo "  Confirm subscription in your email inbox."

# ── Alarm: API error rate > 5% ───────────────────────────────────────────────
aws cloudwatch put-metric-alarm \
  --alarm-name "${APP_NAME}-high-error-rate" \
  --alarm-description "API 5xx error rate above 5% for 5 minutes" \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions "${TOPIC_ARN}" \
  --ok-actions "${TOPIC_ARN}"

# ── Alarm: API latency p99 > 500ms ───────────────────────────────────────────
aws cloudwatch put-metric-alarm \
  --alarm-name "${APP_NAME}-high-latency" \
  --alarm-description "API p99 latency above 500ms for 5 minutes" \
  --metric-name TargetResponseTime \
  --namespace AWS/ApplicationELB \
  --extended-statistic p99 \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.5 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions "${TOPIC_ARN}"

# ── Alarm: ECS CPU > 80% ─────────────────────────────────────────────────────
aws cloudwatch put-metric-alarm \
  --alarm-name "${APP_NAME}-high-cpu" \
  --alarm-description "ECS CPU above 80% for 5 minutes — may need more tasks" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --dimensions Name=ClusterName,Value="${ECS_CLUSTER}" Name=ServiceName,Value="${APP_NAME}-api" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions "${TOPIC_ARN}"

# ── Alarm: ECS desired vs running task count mismatch ─────────────────────────
aws cloudwatch put-metric-alarm \
  --alarm-name "${APP_NAME}-task-count-low" \
  --alarm-description "Running ECS tasks below desired count" \
  --metric-name RunningTaskCount \
  --namespace AWS/ECS \
  --dimensions Name=ClusterName,Value="${ECS_CLUSTER}" Name=ServiceName,Value="${APP_NAME}-api" \
  --statistic Minimum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 2 \
  --comparison-operator LessThanThreshold \
  --alarm-actions "${TOPIC_ARN}"

# ── Alarm: Redis memory > 70% ─────────────────────────────────────────────────
aws cloudwatch put-metric-alarm \
  --alarm-name "${APP_NAME}-redis-memory" \
  --alarm-description "ElastiCache memory above 70%" \
  --metric-name DatabaseMemoryUsagePercentage \
  --namespace AWS/ElastiCache \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 70 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions "${TOPIC_ARN}"

echo ""
echo "CloudWatch alarms created:"
aws cloudwatch describe-alarms \
  --alarm-name-prefix "${APP_NAME}" \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' \
  --output table
