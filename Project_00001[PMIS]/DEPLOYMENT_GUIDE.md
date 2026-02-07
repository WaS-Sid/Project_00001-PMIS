# Production Deployment Guide

This guide covers deploying the PMIS system to AWS ECS Fargate or Google Cloud Run with managed databases and robust infrastructure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [AWS ECS Fargate Deployment](#aws-ecs-fargate-deployment)
4. [GCP Cloud Run Deployment](#gcp-cloud-run-deployment)
5. [Database Migration Strategy](#database-migration-strategy)
6. [Secrets Management](#secrets-management)
7. [Monitoring & Logging](#monitoring--logging)
8. [Scaling & Performance](#scaling--performance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Tools Required

**For AWS ECS Fargate:**
```bash
# Install AWS CLI
brew install awscli  # macOS
# or visit https://aws.amazon.com/cli/

# Install ECS CLI (optional, but helpful)
curl -o /usr/local/bin/ecs-cli https://amazon-ecs-cli.s3.amazonaws.com/ecs-cli-linux-amd64-latest

# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format
```

**For GCP Cloud Run:**
```bash
# Install Google Cloud SDK
brew install --cask google-cloud-sdk  # macOS
# or visit https://cloud.google.com/sdk/docs/install

# Initialize gcloud
gcloud init
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Account Requirements

**AWS:**
- IAM user with policies: `AmazonEC2ContainerRegistryFullAccess`, `AmazonECS_FullAccess`, `AmazonRDSFullAccess`, `AmazonElastiCacheFullAccess`
- VPC with at least 2 public subnets
- ECR repository created for each service (api, worker, web)

**GCP:**
- Project with billing enabled
- Cloud Run, Cloud SQL, Memorystore APIs enabled
- Service account with appropriate roles

---

## Pre-Deployment Checklist

Before deploying to production, ensure:

- [ ] All tests pass: `pytest tests/` in api/
- [ ] No secrets in code or `.env` files committed
- [ ] Docker images build successfully: `docker-compose -f docker-compose.prod.yml build`
- [ ] docker-compose.prod.yml runs locally without errors
- [ ] Environment variables documented in `ENV_VARS.md`
- [ ] Database migration scripts created
- [ ] Monitoring/logging configured
- [ ] Load testing completed (k6, Apache JMeter)
- [ ] Security scanning passed (Snyk, Trivy)
- [ ] Disaster recovery plan documented

### Security Checks

```bash
# Check for hardcoded secrets
grep -r "password\|api_key\|secret" --include="*.py" --include="*.ts" apps/ | grep -v ".env.example"

# Scan dependencies for vulnerabilities
pip-audit  # Python
npm audit  # Node

# Check Docker image vulnerabilities
trivy image <image-name>
```

---

## AWS ECS Fargate Deployment

### Architecture

```
┌─────────────────────────────────────────────┐
│         Route 53 (DNS)                      │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│      Application Load Balancer              │
│  (port 80 → 8000, port 443 → 8000)         │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴───────┐
        │               │
┌───────▼─────┐  ┌─────▼────────┐
│  ECS Task   │  │  ECS Task    │
│  (API)      │  │  (API)       │
└─────────────┘  └──────────────┘
        │               │
        └───────┬───────┘
                │
        ┌───────┴────────────┐
        │                    │
   ┌────▼───┐          ┌────▼──────┐
   │ RDS    │          │ Elastica- │
   │Postgres│          │ che Redis  │
   └────────┘          └───────────┘
```

### Step 1: Create Infrastructure

#### Create RDS PostgreSQL
```bash
# Variables
CLUSTER_NAME="pmis-prod"
ENVIRONMENT="prod"
REGION="us-east-1"

# Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name pmis-rds-sg \
  --description "PMIS RDS Security Group" \
  --region $REGION \
  --query 'GroupId' \
  --output text)

# Allow inbound from ECS
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5432 \
  --cidr 10.0.0.0/16 \
  --region $REGION

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier pmis-postgres-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.3 \
  --master-username postgres \
  --master-user-password $(openssl rand -base64 32) \
  --allocated-storage 100 \
  --storage-type gp3 \
  --vpc-security-group-ids $SG_ID \
  --db-name pmis \
  --backup-retention-period 30 \
  --multi-az \
  --enable-cloudwatch-logs-exports postgresql \
  --region $REGION

# Create security group for Redis
REDIS_SG=$(aws ec2 create-security-group \
  --group-name pmis-redis-sg \
  --description "PMIS Redis Security Group" \
  --region $REGION \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $REDIS_SG \
  --protocol tcp \
  --port 6379 \
  --cidr 10.0.0.0/16 \
  --region $REGION

# Create ElastiCache for Redis
aws elasticache create-replication-group \
  --replication-group-description "PMIS Cache" \
  --replication-group-id pmis-redis-prod \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --auth-token $(openssl rand -base64 32) \
  --transit-encryption-enabled \
  --at-rest-encryption-enabled \
  --security-group-ids $REDIS_SG \
  --region $REGION
```

#### Get Connection Strings
```bash
# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier pmis-postgres-prod \
  --region $REGION \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

POSTGRES_PASSWORD=$(aws secretsmanager get-random-password \
  --query 'RandomPassword' --output text)

# Get Redis endpoint
REDIS_ENDPOINT=$(aws elasticache describe-replication-groups \
  --replication-group-id pmis-redis-prod \
  --region $REGION \
  --query 'ReplicationGroups[0].PrimaryEndpoint.Address' \
  --output text)

# Generate values for .env
echo "DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@${RDS_ENDPOINT}:5432/pmis"
echo "REDIS_URL=redis://:${REDIS_PASSWORD}@${REDIS_ENDPOINT}:6379/0"
```

### Step 2: Create ECR Repositories

```bash
# Create repositories for each service
for service in api worker web; do
  aws ecr create-repository \
    --repository-name pmis/$service \
    --region $REGION \
    --image-tag-mutability MUTABLE
done

# Get login token
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$REGION.amazonaws.com
```

### Step 3: Build and Push Docker Images

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Build images
docker-compose -f docker-compose.prod.yml build

# Tag and push
for service in api worker web; do
  docker tag pmis_$service:latest $REGISTRY/pmis/$service:latest
  docker tag pmis_$service:latest $REGISTRY/pmis/$service:$(git rev-parse --short HEAD)
  docker push $REGISTRY/pmis/$service:latest
  docker push $REGISTRY/pmis/$service:$(git rev-parse --short HEAD)
done
```

### Step 4: Create ECS Cluster

```bash
# Create cluster
aws ecs create-cluster \
  --cluster-name pmis-prod \
  --cluster-settings name=containerInsights,value=enabled \
  --region $REGION

# Create CloudWatch log group
aws logs create-log-group \
  --log-group-name /ecs/pmis \
  --region $REGION
```

### Step 5: Create Task Definitions

#### API Task Definition
```bash
# Create file: ecs-task-api.json
cat > ecs-task-api.json <<EOF
{
  "family": "pmis-api",
  "network-mode": "awsvpc",
  "requires-compatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "container-definitions": [
    {
      "name": "api",
      "image": "${REGISTRY}/pmis/api:latest",
      "port-mappings": [
        {
          "container-port": 8000,
          "host-port": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "LOG_LEVEL",
          "value": "info"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:pmis/database-url"
        },
        {
          "name": "AZURE_OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:pmis/azure-openai-key"
        }
      ],
      "log-configuration": {
        "log-driver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/pmis",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs/api"
        }
      }
    }
  ],
  "execution-role-arn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole"
}
EOF

# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-api.json \
  --region $REGION
```

#### Worker Task Definition
```bash
cat > ecs-task-worker.json <<EOF
{
  "family": "pmis-worker",
  "network-mode": "awsvpc",
  "requires-compatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "container-definitions": [
    {
      "name": "worker",
      "image": "${REGISTRY}/pmis/worker:latest",
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "LOG_LEVEL",
          "value": "info"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:pmis/database-url"
        },
        {
          "name": "CELERY_BROKER",
          "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:pmis/celery-broker"
        }
      ],
      "log-configuration": {
        "log-driver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/pmis",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs/worker"
        }
      }
    }
  ],
  "execution-role-arn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole"
}
EOF

aws ecs register-task-definition \
  --cli-input-json file://ecs-task-worker.json \
  --region $REGION
```

### Step 6: Create ECS Services

```bash
# Get subnet and security group IDs
SUBNET_ID=$(aws ec2 describe-subnets --region $REGION --query 'Subnets[0].SubnetId' --output text)
SG_ID=$(aws ec2 describe-security-groups --filter "Name=group-name,Values=pmis-rds-sg" --region $REGION --query 'SecurityGroups[0].GroupId' --output text)

# Create API Service
aws ecs create-service \
  --cluster pmis-prod \
  --service-name pmis-api \
  --task-definition pmis-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:${REGION}:${ACCOUNT_ID}:targetgroup/pmis-api/xxx,containerName=api,containerPort=8000 \
  --region $REGION

# Create Worker Service
aws ecs create-service \
  --cluster pmis-prod \
  --service-name pmis-worker \
  --task-definition pmis-worker:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region $REGION
```

---

## GCP Cloud Run Deployment

### Architecture

```
┌─────────────────────────────────────────────┐
│    Cloud Load Balancer / Cloud Armor       │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴────────────┐
        │                    │
┌───────▼─────┐       ┌─────▼────────┐
│  Cloud Run  │       │  Cloud Run   │
│   (API)     │       │   (API)      │
└─────────────┘       └──────────────┘
        │                    │
        └───────┬────────────┘
                │
        ┌───────┴────────────┐
        │                    │
   ┌────▼───┐          ┌────▼──────┐
   │Cloud SQL│         │MemoryStore│
   │Postgres │         │  Redis    │
   └────────┘          └───────────┘
```

### Step 1: Create Infrastructure

#### Create Cloud SQL Instance
```bash
PROJECT_ID="your-project-id"
REGION="us-central1"

# Create Cloud SQL instance
gcloud sql instances create pmis-postgres \
  --database-version=POSTGRES_15 \
  --region=$REGION \
  --tier=db-custom-1-3840 \
  --availability-type=REGIONAL \
  --backup-start-time=03:00 \
  --backup-location=$REGION \
  --retained-backups-count=30 \
  --point-in-time-recovery-enabled \
  --enable-bin-log \
  --database-flags=cloudsql_iam_authentication=on \
  --project=$PROJECT_ID

# Create database
gcloud sql databases create pmis \
  --instance=pmis-postgres \
  --project=$PROJECT_ID

# Create database user
POSTGRES_PASSWORD=$(gcloud sql users create postgres \
  --instance=pmis-postgres \
  --password \
  --project=$PROJECT_ID)

# Get connection string
CLOUD_SQL_CONNECTION=$(gcloud sql instances describe pmis-postgres \
  --format='value(connectionName)' \
  --project=$PROJECT_ID)

echo "CLOUD_SQL_CONNECTION_NAME=$CLOUD_SQL_CONNECTION"
```

#### Create Memorystore for Redis
```bash
# Create Redis instance
gcloud redis instances create pmis-redis \
  --size=2 \
  --region=$REGION \
  --redis-version=7.0 \
  --auth-enabled \
  --project=$PROJECT_ID

# Get connection details
REDIS_HOST=$(gcloud redis instances describe pmis-redis \
  --region=$REGION \
  --format='value(host)' \
  --project=$PROJECT_ID)

REDIS_PORT=$(gcloud redis instances describe pmis-redis \
  --region=$REGION \
  --format='value(port)' \
  --project=$PROJECT_ID)

REDIS_AUTH=$(gcloud redis instances describe pmis-redis \
  --region=$REGION \
  --format='value(authString)' \
  --project=$PROJECT_ID)

echo "REDIS_URL=redis://:${REDIS_AUTH}@${REDIS_HOST}:${REDIS_PORT}/0"
```

### Step 2: Push Docker Images to Artifact Registry

```bash
# Enable services
gcloud services enable artifactregistry.googleapis.com

# Create repository
gcloud artifacts repositories create pmis \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push images
docker-compose -f docker-compose.prod.yml build

for service in api worker web; do
  docker tag pmis_$service:latest \
    ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/${service}:latest
  docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/${service}:latest
done
```

### Step 3: Deploy API to Cloud Run

```bash
# Create service account
gcloud iam service-accounts create pmis-api \
  --project=$PROJECT_ID

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:pmis-api@${PROJECT_ID}.iam.gserviceaccount.com \
  --role=roles/cloudsql.client

# Create Cloud Run service
gcloud run deploy pmis-api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/api:latest \
  --platform managed \
  --region $REGION \
  --service-account pmis-api@${PROJECT_ID}.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 10 \
  --set-env-vars "ENVIRONMENT=production,LOG_LEVEL=info" \
  --set-cloudsql-instances $CLOUD_SQL_CONNECTION \
  --project=$PROJECT_ID

# Get service URL
API_URL=$(gcloud run services describe pmis-api \
  --region $REGION \
  --format='value(status.url)' \
  --project=$PROJECT_ID)

echo "API URL: $API_URL"
```

### Step 4: Deploy Web to Cloud Run

```bash
# Create service for web
gcloud run deploy pmis-web \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/web:latest \
  --platform managed \
  --region $REGION \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars "NEXT_PUBLIC_API_URL=${API_URL}/api" \
  --allow-unauthenticated \
  --project=$PROJECT_ID

# Get web URL
WEB_URL=$(gcloud run services describe pmis-web \
  --region $REGION \
  --format='value(status.url)' \
  --project=$PROJECT_ID)

echo "Web URL: $WEB_URL"
```

### Step 5: Deploy Worker to Cloud Run Jobs

```bash
# Create scheduled job for check_overdue_tasks
gcloud run jobs create pmis-check-overdue-tasks \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/worker:latest \
  --command celery,-A,worker.celery_app,beat \
  --region $REGION \
  --memory 512Mi \
  --cpu 1 \
  --set-cloudsql-instances $CLOUD_SQL_CONNECTION \
  --set-env-vars "DATABASE_URL=${DATABASE_URL},CELERY_BROKER=${CELERY_BROKER}" \
  --project=$PROJECT_ID

# Create scheduler to run daily
gcloud scheduler jobs create app-engine pmis-check-overdue-tasks-schedule \
  --schedule="0 0 * * *" \
  --timezone="UTC" \
  --http-method=POST \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/pmis-check-overdue-tasks:run" \
  --oidc-service-account-email=pmis-worker@${PROJECT_ID}.iam.gserviceaccount.com \
  --location=$REGION \
  --project=$PROJECT_ID
```

---

## Database Migration Strategy

### Using Alembic (Recommended)

#### 1. Initialize Alembic
```bash
cd apps/api
alembic init alembic
```

#### 2. Configure alembic.ini
```ini
# alembic.ini
sqlalchemy.url = postgresql://postgres:password@localhost/pmis

# Or use environment variable
sqlalchemy.url = driver://user:password@localhost/dbname
```

#### 3. Create Baseline Migration
```bash
alembic revision --autogenerate -m "Initial schema"
```

#### 4. Review and Update Migration Files
```python
# alembic/versions/xxxx_initial_schema.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create tables
    op.create_table(
        'packages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(50), unique=True),
        sa.Column('title', sa.String(255)),
        sa.Column('data', postgresql.JSON),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )

def downgrade():
    op.drop_table('packages')
```

#### 5. Apply Migrations on Deploy

**Docker Entrypoint Approach:**
```dockerfile
# Updated API Dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]
```

**ECS Task Init Container:**
```json
{
  "container-definitions": [
    {
      "name": "migration",
      "image": "${REGISTRY}/pmis/api:latest",
      "command": ["alembic", "upgrade", "head"],
      "essential": true
    },
    {
      "name": "api",
      "image": "${REGISTRY}/pmis/api:latest",
      "dependsOn": [
        {
          "containerName": "migration",
          "condition": "COMPLETE"
        }
      ]
    }
  ]
}
```

**GCP Cloud Run Init Container:**
```yaml
# Use gke-deploy or Cloud Tasks to run migrations before deploying
steps:
  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - run
      - -f=./k8s
      - -i=${_REGISTRY}/pmis/api
      - -o=.
  - name: 'gcr.io/cloud-builders/kubectl'
    args: ['apply', '-f', 'output']
```

#### 6. Rollback Strategy
```bash
# Check current version
alembic current

# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade a1b2c3d
```

### Health Check After Migration
```python
# apps/api/app/health.py
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Check database connectivity and migrations applied"""
    try:
        # Test database connection
        result = db.execute(text("SELECT 1")).scalar()
        
        # Check schema version
        result = db.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")).scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "migration_version": result
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503
```

---

## Secrets Management

### AWS Secrets Manager

```bash
# Create secret for database URL
aws secretsmanager create-secret \
  --name pmis/database-url \
  --description "PMIS PostgreSQL connection string" \
  --secret-string "postgresql://postgres:password@host:5432/pmis"

# Create secret for API keys
aws secretsmanager create-secret \
  --name pmis/azure-openai-key \
  --secret-string "sk-..."

# Reference in task definition
"secrets": [
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:pmis/database-url"
  }
]
```

### GCP Secret Manager

```bash
# Create secrets
echo -n "postgresql://postgres:password@host:5432/pmis" | \
  gcloud secrets create pmis-database-url \
  --data-file=- \
  --project=$PROJECT_ID

# Reference in Cloud Run
gcloud run deploy pmis-api \
  --set-env-vars DATABASE_URL=$(gcloud secrets versions access latest --secret=pmis-database-url)
```

---

## Monitoring & Logging

### AWS CloudWatch

```python
# apps/api/app/logging_config.py
import logging
import watchtower

# Create CloudWatch handler
cloudwatch = watchtower.CloudWatchLogHandler()
logger = logging.getLogger(__name__)
logger.addHandler(cloudwatch)

# Use in FastAPI
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response
```

### GCP Cloud Logging (via Python Logging)

```python
# apps/api/app/logging_config.py
from google.cloud import logging as cloud_logging

client = cloud_logging.Client()
client.setup_logging()

# Logs automatically sent to Cloud Logging
logger = logging.getLogger(__name__)
logger.info("Application started")
```

### Monitoring & Alerts

**AWS CloudWatch Dashboard:**
```bash
aws cloudwatch put-dashboard \
  --dashboard-name pmis-prod \
  --dashboard-body file://dashboard.json
```

**GCP Monitoring:**
```bash
gcloud monitoring dashboards create --config=file://dashboard.yaml
```

---

## Scaling & Performance

### Auto-Scaling

**AWS ECS Auto Scaling:**
```bash
# Create auto scaling target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/pmis-prod/pmis-api \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy (CPU)
aws application-autoscaling put-scaling-policy \
  --policy-name pmis-api-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/pmis-prod/pmis-api \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration "TargetValue=70,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization}"
```

**GCP Cloud Run Auto Scaling:**
```bash
gcloud run services update pmis-api \
  --region $REGION \
  --max-instances 100 \
  --min-instances 1
```

### Performance Tuning

**API Workers:**
```dockerfile
# For 4 CPU on ECS, run 9 workers (CPU_count * 2 + 1)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "9"]
```

**Database Connection Pooling:**
```python
# apps/api/app/database.py
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
)
```

---

## Troubleshooting

### Common Issues

#### Service Failed to Start
```bash
# AWS: Check CloudWatch logs
aws logs tail /ecs/pmis --follow

# GCP: Check logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Solution: Check environment variables and secrets
aws secretsmanager get-secret-value --secret-id pmis/database-url
```

#### Database Connection Timeout
```bash
# Check security groups/firewall rules
aws ec2 describe-security-groups --filter "Name=group-name,Values=pmis-rds-sg"

# Test connectivity
docker run --rm postgres:15 \
  psql -h $RDS_ENDPOINT -U postgres -d pmis -c "SELECT 1"
```

#### Memory Leaks in Worker
```bash
# Monitor worker memory
docker stats pmis-worker

# Check Celery task queue
celery -A worker.celery_app inspect active

# Restart worker
docker-compose restart worker
```

#### Cold Starts on Cloud Run
```bash
# Enable minimum instances
gcloud run services update pmis-api \
  --region $REGION \
  --min-instances 5
```

### Debug Mode

**Enable Debug Logging:**
```bash
# Update environment
docker-compose -f docker-compose.prod.yml up -e LOG_LEVEL=debug

# Or for ECS
aws ecs update-service \
  --cluster pmis-prod \
  --service pmis-api \
  --task-definition pmis-api:2
```

**Enable Sentry for Error Tracking:**
```bash
# Add to environment
SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0"

# Import Sentry in app
import sentry_sdk
sentry_sdk.init(os.getenv("SENTRY_DSN"))
```

---

## Production Checklist (Post-Deployment)

- [ ] All services healthy (200 responses on /health)
- [ ] Database migrations applied successfully
- [ ] Secrets rotated every 90 days
- [ ] Backups scheduled and tested
- [ ] Monitoring/alerts configured
- [ ] SSL/TLS certificates valid
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] WAF rules in place (AWS)
- [ ] Load balancer health checks passing
- [ ] Auto-scaling policies active
- [ ] Disaster recovery plan tested

---

## Support & Rollback

### Quick Rollback
```bash
# AWS: Revert to previous task definition
aws ecs update-service \
  --cluster pmis-prod \
  --service pmis-api \
  --task-definition pmis-api:$(($CURRENT_REVISION - 1))

# GCP: Deploy previous image
gcloud run deploy pmis-api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/pmis/api:PREVIOUS_TAG
```

### Support Contacts
- **AWS Support**: https://console.aws.amazon.com/support/
- **GCP Support**: https://cloud.google.com/support/
- **PostgreSQL**: https://www.postgresql.org/support/
- **Redis**: https://redis.io/support/

