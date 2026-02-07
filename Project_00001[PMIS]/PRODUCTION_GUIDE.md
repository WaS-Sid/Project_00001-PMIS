# PMIS Production Deployment Documentation

Complete guide for running PMIS in production environments.

## ⚡ Quick Start

### Local Testing with docker-compose.prod.yml

```bash
# 1. Create production environment file
cp .env.example .env.prod

# 2. Update critical values in .env.prod
# - POSTGRES_PASSWORD
# - REDIS_PASSWORD  
# - AZURE_OPENAI_API_KEY or OPENAI_API_KEY
# - SECRET_KEY (generate one: python -c "import secrets; print(secrets.token_urlsafe(32))")

# 3. Start the full stack
docker-compose -f infra/docker-compose.prod.yml up -d

# 4. Verify all services healthy
docker-compose -f infra/docker-compose.prod.yml ps

# 5. Check endpoints
curl http://localhost:8000/health     # API
curl http://localhost:3000            # Web UI
```

### Run Test Script (Automated)

```bash
chmod +x test-prod-compose.sh
./test-prod-compose.sh

# Script checks:
# - docker-compose.prod.yml syntax
# - Docker installation
# - Build all images
# - Start all services
# - Test health endpoints
# - Database connectivity
# - Resource usage
```

---

## 📦 Components

### API (FastAPI + Uvicorn)
- **Port**: 8000
- **Health Check**: `/health`
- **Workers**: 4 (configurable)
- **Resource Limits**: 2 CPU, 2GB memory
- **Startup Time**: ~5 seconds

### Web (Next.js)
- **Port**: 3000
- **Type**: Static + Server-Side Rendering
- **Resource Limits**: 1 CPU, 1GB memory
- **Startup Time**: ~10 seconds

### Worker (Celery)
- **Broker**: Redis
- **Tasks**: 
  - `check_overdue_tasks` - Daily at 00:00 UTC
  - `ingest_email` - On-demand
- **Retries**: 3 with exponential backoff
- **Resource Limits**: 1 CPU, 1GB memory

### Database (PostgreSQL)
- **Port**: 5432
- **Version**: 15-alpine
- **Storage**: Local volume `postgres-data-prod`
- **Backups**: Via pgDump

### Cache (Redis)
- **Port**: 6379
- **Version**: 7-alpine
- **Type**: Session + Message Broker
- **Persistence**: RDB + AOF

---

## 🔐 Environment Configuration

### Required Variables (MUST change from defaults)

```bash
# Database
POSTGRES_PASSWORD=your_secure_password_32_chars

# Cache
REDIS_PASSWORD=your_redis_password_32_chars

# Security
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# LLM Provider (choose one)
AZURE_OPENAI_API_KEY=your_azure_key
# OR
OPENAI_API_KEY=your_openai_key
# OR
ANTHROPIC_API_KEY=your_anthropic_key

# Front-end API URL
NEXT_PUBLIC_API_URL=http://localhost:8000/api  # Change for production
```

### Optional Variables

```bash
# Logging
ENVIRONMENT=production
LOG_LEVEL=info

# CORS
CORS_ORIGINS=https://yourdomain.com

# Email integration
SMTP_SERVER=smtp.your-host.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-smtp-password

# Error tracking
SENTRY_DSN=https://...

# S3/Cloud storage
S3_BUCKET_NAME=pmis-storage
S3_ACCESS_KEY_ID=your_aws_key
S3_SECRET_ACCESS_KEY=your_aws_secret
```

See [ENV_VARS.md](./ENV_VARS.md) for complete reference.

---

## 🚀 Deployment Targets

### AWS ECS Fargate

**Benefits**:
- Fully managed Fargate compute
- Auto-scaling
- Multi-AZ support
- CloudWatch integration
- Load balancer

**Architecture**:
```
┌─ Routes 53/CloudFront -┐
│  ALB (Multi-AZ)       │
└─ ECS Tasks (Fargate)  │
│  RDS PostgreSQL       │
│  ElastiCache Redis    │
```

**Quick Deploy**:
```bash
# See DEPLOYMENT_GUIDE.md section "AWS ECS Fargate Deployment"
# ~15 minutes setup time
```

### GCP Cloud Run

**Benefits**:
- Serverless, pay-per-request
- Auto-scaling to zero
- Built-in CDN
- Cloud Logging integration
- Simpler networking

**Architecture**:
```
┌─ Cloud CDN  ──────────┐
│  Cloud Run Service   │
│  Cloud SQL Postgres  │
│  Memorystore Redis   │
```

**Quick Deploy**:
```bash
# See DEPLOYMENT_GUIDE.md section "GCP Cloud Run Deployment"
# ~20 minutes setup time
```

### Self-Hosted (Docker Swarm / Kubernetes)

For on-premise or custom infrastructure, use docker-compose.prod.yml as base and adapt to your platform.

---

## 📊 Resource Requirements

### Minimum (Development-like)
```
API:      256 CPU, 512 MB memory
Worker:   256 CPU, 512 MB memory
Web:      256 CPU, 512 MB memory
Database: 1    CPU, 1 GB    memory + 20GB storage
Cache:    128 CPU, 256 MB memory
```

### Recommended (Small Production)
```
API:      500 CPU, 1 GB memory (2 replicas)
Worker:   512 CPU, 1 GB memory
Web:      512 CPU, 1 GB memory (2 replicas)
Database: 2 CPU, 2 GB memory + 100GB storage
Cache:    512 CPU, 512 MB memory
```

### Recommended (Medium Production)
```
API:      2000 CPU, 2 GB memory (5 replicas)
Worker:   1000 CPU, 2 GB memory (2 replicas)
Web:      1000 CPU, 1 GB memory (3 replicas)
Database: 4 CPU, 4 GB memory + 500GB storage (High Availability)
Cache:    1000 CPU, 1 GB memory (Replication)
```

---

## 🔄 Database Migrations

### Before Deployment

```bash
# Create migration
cd apps/api
alembic revision --autogenerate -m "Describe your changes"

# Review generated migration in alembic/versions/

# Test locally
docker-compose -f ../../infra/docker-compose.prod.yml exec api alembic upgrade head
```

### During Deployment

**Option 1: Automatic (Recommended)**
```dockerfile
# In Dockerfile, update CMD:
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

**Option 2: Manual Pre-deployment**
```bash
# Before updating service
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
```

**Option 3: Kubernetes Init Container**
```yaml
initContainers:
  - name: migrate
    image: pmis/api:latest
    command: ["alembic", "upgrade", "head"]
```

### Rollback

```bash
# Check current version
docker-compose -f docker-compose.prod.yml exec api alembic current

# Rollback one migration
docker-compose -f docker-compose.prod.yml exec api alembic downgrade -1

# Rollback to specific revision
docker-compose -f docker-compose.prod.yml exec api alembic downgrade abc123def456
```

---

## 🔒 Secrets Management

### Local Development
```bash
# Use .env.prod with weak values (acceptable for local testing)
POSTGRES_PASSWORD=dev_password
REDIS_PASSWORD=dev_password
AZURE_OPENAI_API_KEY=test_key_xyz
```

### AWS Production
```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pmis/database-url \
  --secret-string "postgresql://..."

# Reference in ECS task definition
"secrets": [
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:region:account:secret:pmis/database-url"
  }
]
```

### GCP Production
```bash
# Store in Secret Manager
echo -n "database_url_value" | gcloud secrets create pmis-database-url --data-file=-

# Reference in Cloud Run
gcloud run deploy pmis-api \
  --set-env-vars DATABASE_URL=$(gcloud secrets versions access latest --secret=pmis-database-url)
```

### Best Practices
- ✅ Rotate secrets every 90 days
- ✅ Use service accounts / IAM roles instead of API keys when possible
- ✅ Store in encrypted secrets manager, never in code
- ✅ Use different secrets per environment
- ✅ Enable audit logging for secret access
- ❌ Don't put secrets in .env files in production
- ❌ Don't commit .env files to git
- ❌ Don't hardcode secrets in Docker images

---

## 📈 Scaling

### Horizontal Scaling (Add Replicas)

**API Service**:
```bash
# AWS ECS
aws ecs update-service --cluster pmis-prod --service pmis-api --desired-count 5

# GCP Cloud Run
gcloud run services update pmis-api --max-instances 100

# Docker Compose
docker-compose -f docker-compose.prod.yml up -d --scale api=3
```

**Why Scale API?**
- Handles more concurrent requests
- Distributes load across instances
- Improves availability

### Vertical Scaling (Increase Resources)

```bash
# AWS ECS - Update task definition with more memory/CPU
aws ecs register-task-definition --cli-input-json file://new-task-definition.json

# GCP Cloud Run
gcloud run services update pmis-api --memory 2Gi --cpu 2
```

### Auto-Scaling

**AWS ECS Auto Scaling**:
```bash
# Create auto-scaling target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/pmis-prod/pmis-api \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 --max-capacity 10

# Add CPU-based scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name pmis-api-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/pmis-prod/pmis-api \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration "TargetValue=70,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization}"
```

**GCP Cloud Run Auto-Scaling** (Built-in):
- Automatically scales 0 to max-instances based on load
- No additional configuration needed

---

## 📊 Monitoring & Logging

### Local Monitoring

```bash
# View logs from specific service
docker-compose -f infra/docker-compose.prod.yml logs -f api

# Follow all logs
docker-compose -f infra/docker-compose.prod.yml logs -f

# View container stats
docker stats pmis-api-prod
```

### AWS CloudWatch

```bash
# View logs in CloudWatch Logs
aws logs tail /ecs/pmis --follow

# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name pmis-prod \
  --dashboard-body file://dashboard.json

# Set up alarms
aws cloudwatch put-metric-alarm \
  --alarm-name pmis-api-high-cpu \
  --alarm-description "Alert when API CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### GCP Cloud Logging

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50

# Create log sink for external monitoring
gcloud logging sinks create pmis-sink \
  bigquery.googleapis.com/projects/YOUR_PROJECT/datasets/pmis_logs
```

### Application Monitoring

**Sentry (Error Tracking)**:
```bash
# Add to .env.prod
SENTRY_DSN=https://public@sentry.io/project-id

# Application will automatically send errors to Sentry
```

**Key Metrics to Monitor**:
- API response time (p50, p95, p99)
- Error rate (5xx responses)
- Database connection pool usage
- Redis memory usage
- Worker task processing time
- Queue depth (pending tasks)
- CPU/Memory utilization

---

## 🔧 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f infra/docker-compose.prod.yml logs api

# Common causes:
# 1. Missing environment variables
#    → Check .env.prod, must have DATABASE_URL, AZURE_OPENAI_API_KEY
# 2. Port already in use
#    → docker ps to find what's using port 8000
# 3. Database not ready
#    → Check postgres service is healthy
```

### Database Connection Refused

```bash
# Test database connection
docker-compose -f infra/docker-compose.prod.yml exec postgres \
  psql -U postgres -d pmis -c "SELECT 1"

# Check DATABASE_URL format
# Should be: postgresql://user:password@host:5432/dbname

# Verify credentials in .env.prod
grep POSTGRES_ .env.prod
```

### High Memory Usage

```bash
# Check which container
docker stats

# Increase memory limit in docker-compose.prod.yml
# Or reduce concurrent requests/tasks
```

### Worker Not Processing Tasks

```bash
# Check worker logs
docker-compose -f infra/docker-compose.prod.yml logs worker

# Verify Redis connectivity
docker-compose -f infra/docker-compose.prod.yml exec worker \
  redis-cli -h redis ping

# Inspect active tasks
docker-compose -f infra/docker-compose.prod.yml exec api \
  celery -A worker.celery_app inspect active
```

### Slow API Responses

```bash
# Check database performance
docker-compose -f infra/docker-compose.prod.yml exec postgres \
  pg_stat_statements

# Check slow queries
docker-compose -f infra/docker-compose.prod.yml logs api | grep "duration:"

# Solutions:
# 1. Add database indexes
# 2. Increase number of API workers
# 3. Enable Redis caching
# 4. Scale horizontally (add replicas)
```

---

## 🔄 Backup & Disaster Recovery

### Database Backup

```bash
# One-time backup
docker-compose -f infra/docker-compose.prod.yml exec postgres \
  pg_dump -U postgres pmis > backup-$(date +%Y%m%d-%H%M%S).sql

# Automated daily backup (cron)
30 2 * * * docker-compose -f /path/to/docker-compose.prod.yml exec postgres pg_dump -U postgres pmis > /backups/pmis-$(date +\%Y\%m\%d).sql

# Backup to AWS S3
aws s3 cp backup.sql s3://pmis-backups/$(date +%Y%m%d-backup.sql)
```

### Database Restore

```bash
# From backup file
docker-compose -f infra/docker-compose.prod.yml exec postgres \
  psql -U postgres pmis < backup.sql

# Verify restore
docker-compose -f infra/docker-compose.prod.yml exec postgres \
  psql -U postgres pmis -c "SELECT COUNT(*) FROM packages;"
```

### Redis Backup

```bash
# Redis automatically creates RDB dump in persistent volume
# Check dump location
docker-compose -f infra/docker-compose.prod.yml exec redis ls -lah /data/

# To restore, just restart Redis - it auto-loads from dump.rdb
```

### Disaster Recovery Plan

1. **Detection**: Monitor CloudWatch/GCP alerts
2. **Communication**: Alert on-call team
3. **Assessment**: Check service status, logs, error rate
4. **Mitigation**:
   - Scale up API replicas
   - Check database health
   - Restart workers if stuck
5. **Recovery**:
   - Restore from backup if data corrupted
   - Replay transactions from logs
   - Deploy fixed version
6. **Post-Incident**:
   - Root cause analysis
   - Update runbooks
   - Prevent prevention

---

## ✅ Production Checklist

Before going live, verify:

- [ ] **Configuration**
  - [ ] All environment variables set (no defaults)
  - [ ] Secrets stored in secrets manager
  - [ ] DATABASE_URL verified
  - [ ] LLM API key tested
  - [ ] NEXT_PUBLIC_API_URL is production domain

- [ ] **Database**
  - [ ] Migrations applied (alembic current)
  - [ ] Backup strategy in place
  - [ ] Connection pooling configured
  - [ ] Indexes created for queries

- [ ] **Security**
  - [ ] HTTPS/TLS enabled
  - [ ] CORS_ORIGINS restricted
  - [ ] Secrets not in code/images
  - [ ] WAF rules configured (AWS)
  - [ ] Security scanning passed (Snyk, Trivy)

- [ ] **Testing**
  - [ ] All tests pass (pytest)
  - [ ] Load testing completed (k6, JMeter)
  - [ ] Backup restore tested
  - [ ] Failover tested
  - [ ] Rollback procedure tested

- [ ] **Monitoring**
  - [ ] CloudWatch/Cloud Logging configured
  - [ ] Alerts set up for:
    - [ ] High error rate (>5%)
    - [ ] High CPU (>80%)
    - [ ] High memory (>90%)
    - [ ] Database connection issues
  - [ ] Sentry configured for errors
  - [ ] Team trained on runbooks

- [ ] **Documentation**
  - [ ] Deployment guide updated
  - [ ] Runbooks created for common issues
  - [ ] Rollback procedure documented
  - [ ] Team trained on procedures

---

## 📚 Additional Resources

- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [DEPLOYMENT_QUICK_REFERENCE.md](./DEPLOYMENT_QUICK_REFERENCE.md) - Quick commands
- [ENV_VARS.md](./ENV_VARS.md) - Environment variables reference
- [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) - Testing the system
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [GCP Cloud Run Documentation](https://cloud.google.com/run/docs)
- [PostgreSQL Backup & Restore](https://www.postgresql.org/docs/current/backup.html)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/compose-file-v3/)

---

## 🆘 Getting Help

### Community Support
- GitHub Issues: Report bugs and feature requests
- Discussions: Ask questions and share ideas

### Commercial Support
- Enterprise support plans available
- Contact: support@pmis.example.com

### Emergency Contact
- On-call hotline: +1-XXX-YYY-ZZZZ
- Slack: #pmis-incidents
- Email: incidents@pmis.example.com

---

**Last Updated**: February 2026  
**Maintained By**: DevOps Team  
**Version**: 1.0.0
