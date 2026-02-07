# Production Deployment Quick Reference

Fast reference for deploying PMIS to production using docker-compose.prod.yml or cloud providers.

## Local Testing (docker-compose.prod.yml)

### Prerequisites
- Docker and Docker Compose installed
- `.env.prod` file with production values set

### Quick Start
```bash
# From project root
cd infra

# Create .env.prod with production secrets
cp ../.env.example .env.prod
# Edit .env.prod - change all passwords and secrets

# Start the entire stack
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs api    # API logs
docker-compose -f docker-compose.prod.yml logs worker # Worker logs
docker-compose -f docker-compose.prod.yml logs web    # Web logs

# Stop everything
docker-compose -f docker-compose.prod.yml down
```

### Verify All Services
```bash
# Check health endpoints
curl http://localhost:8000/docs         # API (Swagger docs)
curl http://localhost:3000              # Web UI
curl http://localhost:8000/health       # Health check

# Check Redis
redis-cli -p 6379 ping
# Output: PONG

# Check PostgreSQL
psql postgresql://postgres:password@localhost/pmis -c "SELECT 1"
# Output: 1

# Check Celery Worker
curl http://localhost:8000/api/docs -s | grep -i "worker"
```

---

## AWS ECS Fargate Deployment

### Prerequisites
```bash
aws configure  # Set AWS credentials
aws ecr describe-repositories  # Verify ECR access
```

### Quick Deploy
```bash
# 1. Build and push images
docker-compose -f docker-compose.prod.yml build
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $REGISTRY
docker push $REGISTRY/pmis/api:latest
docker push $REGISTRY/pmis/worker:latest
docker push $REGISTRY/pmis/web:latest

# 2. Update ECS services
aws ecs update-service --cluster pmis-prod --service pmis-api --force-new-deployment
aws ecs update-service --cluster pmis-prod --service pmis-worker --force-new-deployment
aws ecs update-service --cluster pmis-prod --service pmis-web --force-new-deployment

# 3. Check status
aws ecs describe-services --cluster pmis-prod --services pmis-api pmis-worker pmis-web --query 'services[].{Service:serviceName,Status:status,Running:runningCount,Desired:desiredCount}'
```

### Monitor
```bash
# Watch CloudWatch logs
aws logs tail /ecs/pmis --follow

# Check container status
aws ecs describe-tasks --cluster pmis-prod --tasks $(aws ecs list-tasks --cluster pmis-prod --query 'taskArns' --output text) --query 'tasks[].{Task:taskArn,Status:lastStatus,ExitCode:containers[0].exitCode}'
```

---

## GCP Cloud Run Deployment

### Prerequisites
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

### Quick Deploy
```bash
# 1. Push images
docker-compose -f docker-compose.prod.yml build
gcloud auth configure-docker us-central1-docker.pkg.dev
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/pmis/api:latest
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/pmis/worker:latest
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/pmis/web:latest

# 2. Deploy services
gcloud run deploy pmis-api \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/pmis/api:latest \
  --platform managed \
  --region us-central1

gcloud run deploy pmis-web \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/pmis/web:latest \
  --platform managed \
  --region us-central1

# 3. Get URLs
gcloud run services describe pmis-api --region us-central1 --format='value(status.url)'
gcloud run services describe pmis-web --region us-central1 --format='value(status.url)'
```

### Monitor
```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Check service status
gcloud run services describe pmis-api --region us-central1
```

---

## Environment Variables Checklist

### Required (Must Change in Production)
- [ ] `POSTGRES_PASSWORD` - Set to strong random password
- [ ] `REDIS_PASSWORD` - Set to strong random password
- [ ] `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY` - LLM API key
- [ ] `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] `NEXT_PUBLIC_API_URL` - Change to production domain

### Recommended (For Production)
- [ ] `ENVIRONMENT=production` - Set environment
- [ ] `LOG_LEVEL=info` - Reduce log verbosity
- [ ] `CORS_ORIGINS` - Restrict to your domain
- [ ] `SENTRY_DSN` - Configure error tracking

### Generate Secure Values
```bash
# Generate random password
openssl rand -base64 32

# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
openssl rand -hex 32
```

---

## Database Migration

### Run Migrations
```bash
# Using container
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Or one-time container
docker run --rm \
  --env-file .env.prod \
  -v $(pwd)/apps/api/alembic:/app/alembic \
  pmis_api alembic upgrade head
```

### Verify Migration
```bash
docker-compose -f docker-compose.prod.yml exec postgres psql -U postgres -d pmis -c "SELECT * FROM alembic_version;"
```

### Rollback Migration
```bash
docker-compose -f docker-compose.prod.yml exec api alembic downgrade -1
```

---

## Health Checks

### API Health
```bash
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "migration_version": "abc123"
# }
```

### All Services
```bash
#!/bin/bash
SERVICES=(
  "http://localhost:8000/docs"          # API
  "http://localhost:3000"               # Web
  "redis://localhost:6379"              # Redis
  "postgresql://postgres@localhost/pmis" # PostgreSQL
)

for service in "${SERVICES[@]}"; do
  echo "Checking $service..."
  # Add health check logic here
done
```

---

## Scaling

### Local (docker-compose)
```bash
# Increase API replicas using compose scale
# Note: docker-compose up doesn't support --scale, use original docker-compose
docker-compose -f docker-compose.yml up -d --scale api=3
```

### AWS ECS
```bash
# Scale API service to 5 tasks
aws ecs update-service \
  --cluster pmis-prod \
  --service pmis-api \
  --desired-count 5
```

### GCP Cloud Run
```bash
# Set max instances to 100
gcloud run services update pmis-api \
  --max-instances 100 \
  --region us-central1
```

---

## Troubleshooting

### Service Won't Start
```bash
# Check environment variables
docker-compose -f docker-compose.prod.yml config

# Check logs
docker-compose -f docker-compose.prod.yml logs [service]

# Check dependencies
docker-compose -f docker-compose.prod.yml exec api curl http://postgres:5432 -v
docker-compose -f docker-compose.prod.yml exec api redis-cli -h redis ping
```

### Database Connection Failed
```bash
# Check PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -d pmis -c "SELECT 1"

# Check connection string
echo $DATABASE_URL

# Verify credentials
psql postgresql://user:password@localhost/pmis -c "SELECT 1"
```

### Out of Memory
```bash
# Check resource limits
docker stats

# Increase memory in docker-compose.prod.yml
# docker-compose.prod.yml: 
#   api:
#     deploy:
#       resources:
#         limits:
#           memory: 4G
```

### Celery Worker Not Processing Tasks
```bash
# Check worker logs
docker-compose -f docker-compose.prod.yml logs worker

# Inspect active tasks
docker-compose -f docker-compose.prod.yml exec api \
  celery -A worker.celery_app inspect active

# Purge failed tasks
docker-compose -f docker-compose.prod.yml exec api \
  celery -A worker.celery_app purge
```

---

## Backup & Restore

### PostgreSQL Backup
```bash
# Backup
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres pmis > backup.sql

# Restore
docker-compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres pmis < backup.sql
```

### Redis Backup
```bash
# Backup (RDB snapshot)
docker-compose -f docker-compose.prod.yml exec redis \
  redis-cli BGSAVE

# Check snapshot
docker-compose -f docker-compose.prod.yml exec redis \
  redis-cli LASTSAVE
```

---

## Production Checklist

Before going live:
- [ ] All services pass health checks
- [ ] Database migrations applied
- [ ] Environment secrets configured (no defaults)
- [ ] CORS_ORIGINS restricted to your domain
- [ ] SSL/TLS certificates configured in load balancer
- [ ] Backups scheduled and tested
- [ ] Monitoring/alerts enabled
- [ ] Auto-scaling configured
- [ ] Rate limiting enabled
- [ ] Load testing completed (k6, JMeter)
- [ ] Security scanning passed (Snyk, Trivy)
- [ ] Team trained on runbooks
- [ ] Rollback procedure documented and tested

---

## Links

- [Full Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Environment Variables Reference](./ENV_VARS.md)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [GCP Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Database Migration (Alembic)](https://alembic.sqlalchemy.org/)
- [Celery Task Queue](https://docs.celeryproject.io/)
