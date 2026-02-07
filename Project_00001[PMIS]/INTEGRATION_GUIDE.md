# PMIS: Complete Integration & Testing Guide

This guide covers the full end-to-end workflow for the PMIS system, from chat to approvals to audit logging.

## Architecture Overview

```
Next.js UI (port 3000)
    ↓
FastAPI Backend (port 8000)
    ├─ Routes: /api/chat, /api/packages, /api/approvals, /api/audit
    ├ Database: PostgreSQL (port 5432)
    ├ ORM: SQLAlchemy
    └─ LangGraph: Orchestration graph for chat

Celery Worker (background tasks)
    ├─ Scheduled: check_overdue_tasks (daily, UTC midnight)
    ├─ On-demand: ingest_email
    └─ Message Broker: Redis (port 6379)
```

## Quick Start (Docker Compose)

The easiest way to run everything:

```bash
cd infra
docker-compose up
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (port 9000, for future use)
- API (port 8000)
- Worker with Celery Beat

Then, in a separate terminal:

```bash
cd apps/web
npm install
npm run dev
```

UI will be at `http://localhost:3000`

---

## Step-by-Step: Test Full Workflow

### Prerequisites
- Docker and Docker Compose installed
- OR Python 3.11+, Node.js 18+, and Redis running locally

### 1. Start the Backend

**Option A: Docker Compose (Recommended)**
```bash
cd infra
docker-compose up
```

**Option B: Local Development**

In Terminal 1 (API):
```bash
cd apps/api
poetry install
python -c "from app.database import init_db; init_db()"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In Terminal 2 (Worker):
```bash
cd apps/worker
poetry install
celery -A worker.celery_app worker --loglevel=info
```

In Terminal 3 (Celery Beat, optional):
```bash
cd apps/worker
celery -A worker.celery_app beat --loglevel=info
```

### 2. Start the UI

In Terminal 4 (UI):
```bash
cd apps/web
npm install
npm run dev
```

Navigate to `http://localhost:3000`

### 3. Test Workflow: Create → Approve → Verify

#### Step A: Log in as Analyst

1. Go to `http://localhost:3000`
2. Select "Alice (Analyst)" from the dropdown
3. Click "Login"
4. Confirm you see the welcome page with nav links

#### Step B: Create Approval Request via Chat

1. Click **Chat** in the navbar
2. Type: `Mark package P-001 as awarded`
3. The chat agent should respond with confirmation
4. You should see a timestamp and success message

**Expected Response Example:**
```
Bot: I can help you update the package status. Let me create an approval request for that change.
✓ Created approval (appr-xxx-yyy-zzz)
```

#### Step C: View the Approval Request

1. Click **Approvals** in the navbar
2. You should see 1 pending approval with:
   - Status: PENDING (orange badge)
   - Requested by: analyst-1
   - Proposed change: `{"status": "awarded"}`
3. Note the approval ID (you'll see it in the detail)

**Note:** As an analyst, you cannot approve (buttons are disabled)

#### Step D: Switch to Admin and Approve

1. Click your user profile (top-right) → **Logout**
2. You're returned to login page
3. Select "Charlie (Admin)"
4. Click "Login"
5. Go to **Approvals**
6. Find the pending request from step B
7. Click **✓ Approve** button
   - Optional: Leave approval reason blank or add notes
8. Status should change to **APPROVED** (green badge)

**Note:** If you have a Postgres database instead of SQLite, the changes persist. With SQLite, they're saved to `test.db` in the api folder.

#### Step E: Verify Audit Trail

1. Go to **Packages**
2. Click on **P-001** to view its detail page
3. Scroll down to **Audit Timeline**
4. You should see events (in reverse chronological order):
   - `PACKAGE_PATCHED` - when admin approved
   - `APPROVAL_DECIDED` - when admin decided
   - `APPROVAL_CREATED` - when analyst proposed
   - Plus any historical events

5. Click **Details** to expand any event payload

#### Step F: Create a Package and Propose Changes

1. Log back in as **Analyst**
2. Go to **Chat**
3. Type: `Create a new package with code P-TEST and title Test Package`
4. The agent should create it and return a confirmation
5. Go to **Packages**
6. You should see the new package in the list
7. Click on it to view details and audit trail
8. From the detail page, click "Open Chat" to propose changes

---

## API Endpoints
{
  "query": "What is the status of package P-001?",
  "impact_level": "medium",
  "uncertainty_level": "medium"
}
```

**Response:**
```json
{
  "response": "Package P-001 is in PENDING state with 2 pending approvals.",
  "action_type": "query",
  "resource_created": null,
  "evidence": []
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst" \
  -H "X-User-Name: Alice" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the status of package P-001?",
    "impact_level": "medium"
  }'
```

---

### 2. Packages Endpoints

#### GET /api/packages
List all packages.

**Response:**
```json
[
  {
    "id": "pkg-123",
    "code": "P-001",
    "title": "Supply Contract",
    "data": {
      "status": "pending",
      "vendor": "Vendor A"
    }
  }
]
```

#### GET /api/packages/{package_id}
Get package details.

**Response:**
```json
{
  "id": "pkg-123",
  "code": "P-001",
  "title": "Supply Contract",
  "data": {
    "status": "pending"
  }
}
```

#### PATCH /api/packages/{package_id}
**Propose a package patch (creates approval request, does NOT apply directly).**

This endpoint creates an approval workflow. The patch is NOT applied until approved.

**Required Headers:**
- `X-User-Id`, `X-User-Role`, `X-User-Name`

**Request Body:**
```json
{
  "status": "awarded"
}
```

**Response:**
```json
{
  "id": "appr-456",
  "package_id": "pkg-123",
  "patch_json": {
    "status": "awarded"
  },
  "status": "pending",
  "requested_by": "analyst1",
  "created_at": "2026-02-06T12:00:00Z"
}
```

**Example Workflow:**
```bash
# 1. Analyst proposes a status change
curl -X PATCH http://localhost:8000/api/packages/pkg-123 \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst" \
  -H "Content-Type: application/json" \
  -d '{"status": "awarded"}'

# Response includes approval_id: "appr-456"
```

---

### 3. Approvals Endpoints

#### GET /api/approvals
List all approval requests (optionally filter by status).

**Query Parameters:**
- `status`: "pending" | "approved" | "rejected"

**Response:**
```json
[
  {
    "id": "appr-456",
    "package_id": "pkg-123",
    "patch_json": {
      "status": "awarded"
    },
    "status": "pending",
    "requested_by": "analyst1",
    "created_at": "2026-02-06T12:00:00Z"
  }
]
```

#### POST /api/approvals/{approval_id}/approve
**Approve a patch request (applies the patch).**

Only users with ADMIN role can approve.

**Request Parameters:**
- `reason_text`: Optional reason for approval

**Response:**
```json
{
  "id": "appr-456",
  "package_id": "pkg-123",
  "patch_json": {
    "status": "awarded"
  },
  "status": "approved",
  "requested_by": "analyst1",
  "created_at": "2026-02-06T12:00:00Z"
}
```

**Example Approval Workflow:**
```bash
# 2. Admin approves the request (this applies the patch)
curl -X POST http://localhost:8000/api/approvals/appr-456/approve \
  -H "X-User-Id: admin1" \
  -H "X-User-Role: admin" \
  -H "Content-Type: application/json" \
  -d '{"reason_text": "Vendor approved in procurement meeting"}'

# Response shows status: "approved"
# The package status is now "awarded"
```

#### POST /api/approvals/{approval_id}/reject
**Reject a patch request (no changes applied).**

Only users with ADMIN role can reject.

**Response:**
```json
{
  "id": "appr-456",
  "status": "rejected",
  ...
}
```

---

### 4. Audit/Event Timeline Endpoint

#### GET /api/audit/{entity_type}/{entity_id}
Get event timeline for an entity (immutable audit log).

**Supported entity_type values:**
- "package"
- "task"
- "approval"

**Query Parameters:**
- `limit`: Max events to return (default 50)

**Example Response:**
```json
[
  {
    "id": "evt-001",
    "event_type": "task_escalated",
    "entity_type": "task",
    "entity_id": "task-123",
    "triggered_by": "system-scheduler",
    "correlation_id": "corr-001",
    "payload": {
      "task_title": "Overdue Task",
      "days_overdue": 5
    },
    "created_at": "2026-02-06T10:00:00Z"
  },
  {
    "id": "evt-002",
    "event_type": "approval_created",
    "entity_type": "approval",
    "entity_id": "appr-456",
    "triggered_by": "analyst1",
    "correlation_id": "corr-002",
    "payload": {
      "patch": {"status": "awarded"},
      "reason": "User request",
      "requested_by": "analyst1"
    },
    "created_at": "2026-02-06T11:00:00Z"
  }
]
```

**Example:**
```bash
curl http://localhost:8000/api/audit/task/task-123?limit=20 \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"
```

---

## Worker Tasks

### 1. check_overdue_tasks (Scheduled Daily)

**Schedule:** 00:00 UTC daily (configurable)

**What it does:**
1. Queries for tasks with due_date < now
2. For each overdue task, creates a TASK_ESCALATED event
3. Uses idempotency to ensure each task is escalated once

**Idempotency Key:** `escalate-task-{task_id}`

**Example Event Created:**
```json
{
  "event_type": "task_escalated",
  "entity_type": "task",
  "entity_id": "task-123",
  "payload": {
    "task_title": "Overdue Task",
    "days_overdue": 5,
    "due_date": "2026-02-01T00:00:00Z",
    "assignee_id": "user-001"
  },
  "triggered_by": "system-scheduler"
}
```

**Monitoring:**
```bash
# View escalation events
curl http://localhost:8000/api/audit/task/{task_id} \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"
```

---

### 2. ingest_email (On-demand)

**What it does:**
1. Accepts email payload with metadata
2. Matches email to package by code (optional)
3. Creates EMAIL_INGESTED event
4. Attaches event to package if match found

**Idempotency Key:** `email-ingest-{message_id}`

**Task Payload:**
```json
{
  "email_payload": {
    "message_id": "email-001",
    "sender": "vendor@example.com",
    "subject": "Package P-001 Status",
    "body": "The package is ready for delivery.",
    "package_code": "P-001"
  }
}
```

**Example Call (from API or external system):**
```python
from celery import current_app

result = current_app.send_task(
    'worker.ingest_email',
    kwargs={
        'email_payload': {
            'message_id': 'email-20260206-001',
            'sender': 'procurement@vendor.com',
            'subject': 'Package P-001 Ready',
            'body': 'Your package is ready for shipment.',
            'package_code': 'P-001',
        }
    }
)
print(f"Task ID: {result.id}")
print(f"Result: {result.get(timeout=30)}")
```

**Event Created:**
```json
{
  "event_type": "email_ingested",
  "entity_type": "package",
  "entity_id": "pkg-123",
  "payload": {
    "message_id": "email-001",
    "sender": "vendor@example.com",
    "subject": "Package Status",
    "body_length": 42,
    "package_code": "P-001",
    "attached_to_package": true
  },
  "triggered_by": "system-email-ingest"
}
```

---

## Full Workflow Example

### Scenario: Approve and Monitor a Package

```bash
# 1. Create or use existing package P-001
# (assuming it exists)

# 2. List packages
curl http://localhost:8000/api/packages \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"

# 3. Propose a status change (analyst)
APPROVAL_ID=$(curl -X PATCH http://localhost:8000/api/packages/pkg-123 \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst" \
  -H "Content-Type: application/json" \
  -d '{"status": "awarded"}' \
  | jq -r '.id')

echo "Created approval: $APPROVAL_ID"

# 4. Check approval status
curl http://localhost:8000/api/approvals \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"

# 5. Admin approves the request
curl -X POST http://localhost:8000/api/approvals/$APPROVAL_ID/approve \
  -H "X-User-Id: admin1" \
  -H "X-User-Role: admin" \
  -H "Content-Type: application/json" \
  -d '{"reason_text": "Approved in review meeting"}'

# 6. Verify package was updated
curl http://localhost:8000/api/packages/pkg-123 \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"

# 7. View audit timeline
curl http://localhost:8000/api/audit/package/pkg-123 \
  -H "X-User-Id: analyst1" \
  -H "X-User-Role: analyst"

# Timeline will show:
# - approval_created event (when analyst proposed)
# - approval_decided event (when admin approved)
# - package_patched event (patch applied to package)
```

---

## Error Handling & Role-Based Access

### Authorization
- **Read**: analyst, operator, viewer, admin
- **Write (Propose Patch)**: analyst, operator, admin
- **Approve/Reject**: admin only

### Errors
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `400 Bad Request`: Invalid request or policy violation
- `500 Internal Server Error`: Execution failed

### Retry & Resilience
- **API**: Fast internal retries via FastAPI error handling
- **Worker**: Max 3 retries with exponential backoff (60s, 120s, 180s)
- **Dead-letter**: Failed tasks committed to `dead_letter` queue

---

## Testing

### Unit Tests (API)
```bash
cd apps/api
pytest tests/test_approval_workflow.py -v
pytest tests/test_write_tools.py -v
pytest tests/test_worker_integration.py -v
```

### Integration Tests (Full Stack)
```bash
# Start full stack
cd infra
docker-compose up

# Or manually start components
celery -A worker.celery_app worker --loglevel=info &
celery -A worker.celery_app beat --loglevel=info &
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### Manual API Testing with curl

See examples above, or use Postman/Thunder Client with the OpenAPI spec at `/openapi.json`.

---

## Configuration

### API Environment Variables
- `DATABASE_URL`: PostgreSQL connection (default: sqlite:///./test.db)
- `CELERY_BROKER`: Redis broker URL (default: redis://localhost:6379/0)
- `SQL_ECHO`: Enable SQL logging (set to "true" for debug)

### Worker Environment Variables
- `CELERY_BROKER`: Redis broker URL (default: redis://localhost:6379/0)
- `CELERY_RESULT_BACKEND`: Result backend URL
- `DATABASE_URL`: PostgreSQL connection
- `SQL_ECHO`: Enable SQL logging

### Celery Beat Schedule (worker/worker.py)
Edit `celery_app.conf.beat_schedule` to adjust task timing:
```python
# Daily at midnight UTC
"schedule": crontab(hour=0, minute=0)

# Every 60 seconds (for testing)
"schedule": 60.0
```

---

## Monitoring & Debugging

### View Worker Status
```bash
celery -A worker.celery_app inspect active
celery -A worker.celery_app inspect stats
celery -A worker.celery_app inspect scheduled
```

### View Events in Database
```bash
python -c "
from app.database import get_db
from app.tools.models import Event, EventType

db = get_db()
events = db.query(Event).order_by(Event.created_at.desc()).limit(20).all()
for evt in events:
    print(f'{evt.created_at} | {evt.event_type.value} | {evt.entity_type}:{evt.entity_id}')
db.close()
"
```

### API OpenAPI Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
