# Production Deployment Visual Reference

Quick visual guide for PMIS production deployment architecture and workflows.

## 📦 System Architecture

### Local Development (docker-compose.yml)
```
┌─ PostgreSQL (dev) ────────────────┐
├─ Redis (dev) ─────────────────────┤
├─ API (dev, 1 worker) ────────────┤  All services
├─ Worker (dev) ────────────────────┤  accessible
├─ Web (dev) ───────────────────────┤  on localhost
└─ MinIO (optional) ────────────────┘
```

### Production Local (docker-compose.prod.yml)
```
┌──────────────────────────────────────────────────┐
│  Production Docker Compose                       │
├──────────┬────────────┬─────────┬────────────────┤
│ postgres │   redis    │   api   │  worker  │ web │
│    15    │     7      │  uvicorn│ celery   │next │
│          │  (512MB)   │(4 workers)(4 workers)    │
└──────────┴────────────┴─────────┴────────────────┘
     ↓           ↓           ↓        ↓         ↓
[postgres]    [redis]      [8000]   [celery] [3000]
   data        data         api      broker   web
```

### AWS ECS Fargate Architecture
```
                    Internet
                       │
                       ↓
            ┌──────────────────────┐
            │  Route 53 DNS        │
            │  yourdomain.com      │
            └──────────┬───────────┘
                       ↓
           ┌───────────────────────────┐
           │ CloudFront / AWS Shield   │ (DDoS protection)
           └───────────┬───────────────┘
                       ↓
        ┌──────────────────────────────────┐
        │ Application Load Balancer        │
        │ (Distributes traffic)            │
        ├────────────────┬─────────────────┤
        │ Port 80 → 8000 │ Port 443 → 8000 │
        └────────────────┴─────────────────┘
              ↓                  ↓
        ┌──────────────┬──────────────┬──────────────┐
        │              │              │              │
    ┌───▼──┐       ┌───▼──┐      ┌───▼──┐      ┌───▼──┐
    │ API  │       │ API  │      │Web   │      │Web   │
    │Task1 │       │Task2 │      │Task1 │      │Task2 │
    │(200  │       │(200  │      │(128  │      │(128  │
    │ CPU) │       │ CPU) │      │ CPU) │      │ CPU) │
    └──────┘       └──────┘      └──────┘      └──────┘
        │              │              │            │
        └──────────────┼──────────────┼────────────┘
                       │              │
           ┌───────────▼──────────────▼────────┐
           │  RDS PostgreSQL (Multi-AZ)        │
           │  - Primary in AZ-1                │
           │  - Standby in AZ-2                │
           │  - Automated backups              │
           │  - Read replicas option           │
           └───────────────────────────────────┘

           ┌───────────────────────────────────┐
           │ ElastiCache Redis (Cluster mode)  │
           │  - Primary shard in AZ-1          │
           │  - Replica shard in AZ-2          │
           │  - Automatic failover             │
           │  - Persistence (RDB + AOF)        │
           └───────────────────────────────────┘

        ┌──────────────────────────────────────┐
        │ ECS Service: Worker                  │
        │  Task 1               Task 2          │
        │ (512 CPU, 1G mem)                    │
        │  Celery Beat + Worker                │
        │  Scheduled tasks + on-demand         │
        └──────────────────────────────────────┘
           ↓                    ↓
        [PostgreSQL] ←─────→ [Redis]
```

### GCP Cloud Run Architecture
```
                    Internet
                       │
                       ↓
            ┌──────────────────────┐
            │  Cloud DNS (Route 53)│
            │  yourdomain.com      │
            └──────────┬───────────┘
                       ↓
          ┌────────────────────────────┐
          │  Cloud Armor + CDN         │
          │  (DDoS + caching)          │
          └──────────┬─────────────────┘
                     ↓
        ┌────────────────────────────────┐
        │  Cloud Load Balancer           │
        │  (HTTPS & traffic distribution)│
        └────────────┬───────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │     Cloud Run Services                 │
    ├──────────────────────────────────────┬─┤
    │                                      │ │
    │ ┌─────────────────────────────────┐ │ │
    │ │ API Service                     │ │ │
    │ │ - Auto-scales 5 to 100 instances│ │ │
    │ │ - uvicorn 4 workers             │ │ │
    │ │ - Memory: 1 GB                  │ │ │
    │ │ - CPU: 1                        │ │ │
    │ └─────────────────────────────────┘ │ │
    │                                      │ │
    │ ┌─────────────────────────────────┐ │ │
    │ │ Web Service                     │ │ │
    │ │ - Auto-scales 1 to 50 instances │ │ │
    │ │ - Next.js server                │ │ │
    │ │ - Memory: 512 MB                │ │ │
    │ │ - CPU: 1                        │ │ │
    │ └─────────────────────────────────┘ │ │
    │                                      │ │
    └──────────────────────────────────────┘ │
     Cloud SQL                               │
     PostgreSQL 15                           │
     - Managed backup                        │
     - Automatic failover                    │
     - Read replicas                         │
     - Point-in-time recovery                │
                                            │
     Memorystore                             │
     Redis Cluster Mode                      │
     - Replication across zones              │
     - Automatic failover                    │
     - Cluster as cache                      │
     - AOF persistence                       │
└────────────────────────────────────────────┘

        ┌────────────────────────────────────┐
        │ Cloud Run Jobs                     │
        │ check_overdue_tasks (daily cron)   │
        │ Cloud Scheduler trigger -> Job     │
        └────────────────────────────────────┘
           ↓                    ↓
        [Cloud SQL] ←─────→ [Memorystore]
```

---

## 🔄 Deployment Workflow

### Local Testing
```
1. Create .env.prod
   ↓
2. docker-compose -f docker-compose.prod.yml build
   ↓
3. docker-compose -f docker-compose.prod.yml up -d
   ↓
4. curl http://localhost:8000/health (verify)
   ↓
5. docker-compose -f docker-compose.prod.yml down (cleanup)
```

### AWS ECS Fargate
```
Step 1: Infrastructure Setup
  ├─ Create IAM roles & policies
  ├─ Create VPC & subnets
  ├─ Create security groups
  ├─ Create RDS PostgreSQL
  └─ Create ElastiCache Redis
     ↓
Step 2: Container Registry
  ├─ Create ECR repositories
  ├─ Push Docker images
  └─ Tag with version numbers
     ↓
Step 3: ECS Cluster
  ├─ Create ECS cluster
  ├─ Register task definitions (API, Worker, Web)
  ├─ Create services with load balancer
  └─ Configure auto-scaling
     ↓
Step 4: DNS & CDN
  ├─ Add Route 53 records
  ├─ Create CloudFront distribution
  ├─ Configure SSL/TLS certificate
  └─ Set up health checks
     ↓
Step 5: Monitoring
  ├─ Create CloudWatch dashboards
  ├─ Set up alarms
  ├─ Configure log retention
  └─ Enable CloudTrail for audit
     ↓
✅ Production Ready
```

### GCP Cloud Run
```
Step 1: Infrastructure Setup
  ├─ Create Cloud SQL PostgreSQL
  ├─ Create Memorystore Redis
  └─ Create service accounts
     ↓
Step 2: Container Registry
  ├─ Create Artifact Registry
  ├─ Push Docker images
  └─ Tag with version numbers
     ↓
Step 3: Cloud Run Services
  ├─ Deploy API service
  ├─ Deploy Web service
  └─ Set environment variables
     ↓
Step 4: Async Tasks
  ├─ Create Cloud Run Job
  ├─ Create Cloud Scheduler
  └─ Set daily cron schedule
     ↓
Step 5: DNS & Security
  ├─ Add Cloud DNS records
  ├─ Configure Cloud Armor
  ├─ Set up SSL/TLS certificate
  └─ Enable audit logging
     ↓
Step 6: Monitoring
  ├─ Create Cloud Logging queries
  ├─ Set up notification channels
  ├─ Create uptime checks
  └─ Configure error reporting
     ↓
✅ Production Ready
```

---

## 🔄 Request Flow (Happy Path)

### Chat Interface
```
User types message in React UI
        ↓
[Web] http://localhost:3000
        ↓
API Client (lib/api.ts) sends POST /api/chat + headers
        ↓
[API] http://localhost:8000/api/chat
        ↓
FastAPI endpoint receives request with:
  - query: user message
  - X-User-Id: user ID
  - X-User-Role: user role
        ↓
Create UserContext from headers
        ↓
Call LangGraph with user_query + db_session
        ↓
Graph determines action:  ┌─ Read packages ──┐
                          ├─ Create approval┤
                          ├─ Write event ───┤
                          └─ Send response ─┘
        ↓
Database queries/writes via SQLAlchemy
        ↓
Return response to API
        ↓
[Web] Receive and display response
        ↓
User sees result + audit trail updated
```

### Background Task (Worker)
```
Daily at 00:00 UTC
        ↓
Celery Beat triggers check_overdue_tasks
        ↓
Task sent to Redis broker (CELERY_BROKER)
        ↓
Worker process (3 idle workers) picks up task
        ↓
Connects to PostgreSQL database
        ↓
Query: SELECT * FROM tasks WHERE due_date < NOW()
        ↓
For each overdue task:
  └─ Create escalation event
  └─ Check idempotency (idempotency_key: escalate-task-{id})
  └─ Write to database
        ↓
Result written to Redis (CELERY_RESULT_BACKEND)
        ↓
If error: Retry up to 3 times with exponential backoff
        ↓
If all retries fail: Write to dead-letter queue
        ↓
Next day, repeat
```

### Approval Workflow
```
User proposes change via chat
        ↓
API creates Approval record (status=pending)
        ↓
Audit event APPROVAL_CREATED written
        ↓
Event visible in GET /api/audit
        ↓
Admin sees approval in /approvals page
        ↓
Admin clicks "Approve" button
        ↓
POST /api/approvals/{id}/approve
  with decision="approve"
        ↓
API calls approve_proposal() tool
        ↓
Tool applies patch to package
        ↓
Tool writes APPROVAL_DECIDED event
        ↓
Approval record updated (status=approved)
        ↓
UI refreshes and shows new status
        ↓
Approval workflow complete ✅
```

---

## 📊 Data Flow Diagram

```
                    ┌─────────────────┐
                    │ Next.js Browser │
                    │ React Components│
                    └────────┬────────┘
                             │
                             ↓
                 ┌───────────────────────┐
                 │ API Client (fetch)    │
                 │ - setUserHeaders()    │
                 │ - /api/chat           │
                 │ - /api/packages       │
                 │ - /api/approvals      │
                 └────────────┬──────────┘
                              │
                              ↓
                 ┌────────────────────────────┐
                 │ FastAPI Routes             │
                 │ + Authentication (headers) │
                 │ + Role checks             │
                 └─────────────┬──────────────┘
                               │
                   ┌─────────────────────────┐
                   │                         │
                   ↓                         ↓
            ┌────────────────┐    ┌────────────────┐
            │ LangGraph      │    │ Write Tools    │
            │ - Agent logic  │    │ - append_event │
            │ - Tool calls   │    │ - create task  │
            │ - Reasoning    │    │ - set approval │
            └────────┬───────┘    └────────┬───────┘
                     │                     │
                     └─────────────┬───────┘
                                   ↓
                    ┌──────────────────────────┐
                    │ SQLAlchemy ORM           │
                    │ - Tables: packages,      │
                    │           tasks, events, │
                    │           approvals,     │
                    │           memory,        │
                    │           idempotency    │
                    └────────────┬─────────────┘
                                 │
                  ┌──────────────────┐
                  │                  │
                  ↓                  ↓
            ┌───────────┐      ┌──────────┐
            │PostgreSQL │      │  Redis   │
            │           │      │          │
            │ 📦 Tables │      │ 💾 Cache │
            │ 📝 Events │      │ 📮 Queue │
            │ ✅ Audit  │      │ 🔔 Pub   │
            └───────────┘      └──────────┘
                │                    │
                └──────────────┬──────┘
                               │
                        ┌──────▼─────┐
                        │ Browser UI │
                        │ Updates    │
                        │ in Real-   │
                        │ time       │
                        └────────────┘
```

---

## 🎯 Acceptance Criteria Tracking

| Criterion | File | Status |
|-----------|------|--------|
| Dockerize API (uvicorn) | apps/api/Dockerfile | ✅ |
| Dockerize Worker (celery) | apps/worker/Dockerfile | ✅ |
| Dockerize Web (next build) | apps/web/Dockerfile | ✅ |
| Provide docker-compose.prod.yml | infra/docker-compose.prod.yml | ✅ |
| Environment variable docs | .env.example, ENV_VARS.md | ✅ |
| AWS ECS Fargate guide | DEPLOYMENT_GUIDE.md | ✅ |
| GCP Cloud Run guide | DEPLOYMENT_GUIDE.md | ✅ |
| Managed Postgres + Redis | Covered in all guides | ✅ |
| Database migration strategy | DEPLOYMENT_GUIDE.md | ✅ |
| docker compose up works | docker-compose.prod.yml | ✅ |
| Cloud deployment docs clear | DEPLOYMENT_GUIDE.md | ✅ |

---

## 📈 Performance Targets

### API Performance
```
Response Time:
  p50:  < 100ms
  p95:  < 500ms
  p99:  < 1s

Throughput:
  Requests/sec: > 1,000 (4 workers)

CPU Usage:
  Target:  < 70%
  Scale up: > 80%

Memory:
  Target: < 1.5GB (from 2GB limit)
```

### Database Performance
```
Query Response:
  Simple: < 10ms
  Complex: < 100ms

Connection Pool:
  Size: 20
  Max overflow: 40
  Recycle: 3600s

Backup: Daily (automated RDS)
```

### Worker Performance
```
Task Processing:
  Overdue check: < 30s
  Email ingest: < 5s per email

Throughput:
  Concurrent tasks: 4

Retry Policy:
  Max retries: 3
  Backoff: 60s, 120s, 180s
```

---

## 🔄 Release Process

```
Feature Development
    ↓
Code Review + Tests Pass
    ↓
Build new Docker images
    ↓
Tag with semantic version (v1.2.3)
    ↓
Push to ECR or Artifact Registry
    ↓
Staging deployment:
  ├─ Update service with new image
  ├─ Run smoke tests
  ├─ Verify logs and metrics
  └─ Get approval
    ↓
Production deployment:
  ├─ Database migrations (alembic upgrade head)
  ├─ Gradual rollout (canary deployment)
  ├─ Health checks pass
  ├─ Monitor error rate (< 5%)
  └─ Monitor performance
    ↓
✅ Release Complete

Rollback Plan (if issues):
  ├─ Update service with previous image
  ├─ Run alembic downgrade (if needed)
  ├─ Verify services healthy
  └─ Notify stakeholders
```

---

## 📋 Size Reference

| Component | Image Size | Memory (Prod) | CPU (Prod) |
|-----------|-----------|---------------|-----------|
| API | 500 MB | 1 GB | 500m |
| Worker | 450 MB | 1 GB | 512m |
| Web | 350 MB | 512 MB | 512m |
| PostgreSQL | 100 MB slim | 1 GB | 1000m |
| Redis | 50 MB alpine | 512 MB | 512m |
| **Total** | **~1.5 GB** | **~4 GB** | **~3.5 CPU** |

---

## 🔒 Security Checklist

```
Images:
  ☐ No hardcoded secrets
  ☐ Non-root users
  ☐ Minimal base images
  ☐ Latest patches applied
  ☐ Vulnerability scanned (Trivy)

Networking:
  ☐ HTTPS everywhere
  ☐ TLS 1.2+
  ☐ CORS restricted
  ☐ WAF rules (AWS)
  ☐ Cloud Armor (GCP)

Database:
  ☐ Encrypted connections
  ☐ Strong passwords
  ☐ Backups encrypted
  ☐ Audit logging enabled
  ☐ Least privilege access

Application:
  ☐ No secrets in env (use secrets manager)
  ☐ Input validation
  ☐ SQL injection protected (ORM)
  ☐ CSRF protection
  ☐ Environment isolation

Monitoring:
  ☐ Audit logging
  ☐ Error tracking (Sentry)
  ☐ CloudTrail enabled
  ☐ Access logs preserved
  ☐ Alerts configured
```

This visual reference provides quick understanding of the complete production deployment architecture and workflows.
