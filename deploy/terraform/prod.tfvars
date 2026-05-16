# deploy/terraform/prod.tfvars
# Production environment overrides
# Usage: terraform apply -var-file=prod.tfvars

environment         = "prod"
aws_region          = "us-east-1"
app_name            = "pricing-engine"
acm_certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/YOUR-CERT-ID"

task_cpu    = 2048   # 2 vCPU
task_memory = 4096   # 4 GB (Prophet models are memory-hungry)
min_tasks   = 2
max_tasks   = 20

db_instance_class = "db.r6g.large"   # Memory-optimised for analytics workloads
redis_node_type   = "cache.r6g.large"
