# PMIS Worker

Celery worker for PMIS async tasks and scheduled jobs.

## Tasks

### `check_overdue_tasks` (Scheduled, Daily)
Checks for tasks with due dates in the past and creates TASK_ESCALATED events. 

**Features:**
- Runs daily at midnight UTC (configurable via `celery_app.conf.beat_schedule`)
- Idempotent: uses idempotency keys to ensure each task is escalated only once
- Handles failures gracefully with exponential backoff retry

**Configuration:**
- Default schedule: `crontab(hour=0, minute=0)` (daily at midnight)
- For testing, edit `celery_app.conf.beat_schedule` to use `"schedule": 60.0` (every 60 seconds)
- Max retries: 3
- Retry delay: 60 seconds (exponential backoff)

**Example Celery Beat Output:**
```
Starting overdue task check...
Found 2 overdue tasks
Escalated task task-123: event evt-456
Escalated task task-789: event evt-790
Overdue task check complete. Escalated 2 tasks.
```

### `ingest_email` (On-demand)
Accepts email payloads and creates EMAIL_INGESTED events, optionally attaching to packages.

**Parameters:**
```python
{
    "message_id": "unique-email-id",        # Required; used for idempotency
    "sender": "user@example.com",           # Required
    "subject": "Email subject",             # Required
    "body": "Email body text",              # Required
    "package_code": "P-001"                 # Optional; if provided, event is attached to package
}
```

**Features:**
- Idempotent: processes each email only once (based on message_id)
- Matches emails to packages by code
- Creates event attached to package if match found
- Falls back to standalone email event if no package match

**Example Task Call:**
```python
from celery import current_app

result = current_app.send_task(
    'worker.ingest_email',
    kwargs={
        'email_payload': {
            'message_id': 'email-20260206-001',
            'sender': 'procurement@vendor.com',
            'subject': 'Package P-001 Status Update',
            'body': 'The awarded package is ready for delivery.',
            'package_code': 'P-001',
        }
    }
)
print(f"Task ID: {result.id}")
```

**Example Response:**
```json
{
  "status": "success",
  "message_id": "email-20260206-001",
  "event_id": "evt-001",
  "attached_to_package": true,
  "package_code": "P-001",
  "timestamp": "2026-02-06T12:34:56.789012"
}
```

## Running the Worker

### Local Development

1. **Install dependencies:**
   ```bash
   cd apps/worker
   poetry install
   ```

2. **Ensure Redis is running:**
   ```bash
   # Start Redis (if using Docker)
   docker run -d -p 6379:6379 redis:7
   ```

3. **Ensure database is initialized:**
   ```bash
   cd ../api
   python -c "from app.database import init_db; init_db()"
   cd ../worker
   ```

4. **Start the worker:**
   ```bash
   celery -A worker.celery_app worker --loglevel=info
   ```

5. **In a separate terminal, start Celery Beat (for scheduled tasks):**
   ```bash
   celery -A worker.celery_app beat --loglevel=info
   ```

### Docker Compose

```bash
cd infra
docker-compose up
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO (port 9000)
- API (port 8000)
- Worker with Celery Beat

## Testing

### Test 1: Manual Email Ingestion

```bash
python -c "
from worker.worker import ingest_email

# Test email ingestion
result = ingest_email.apply_async(kwargs={
    'email_payload': {
        'message_id': 'test-email-001',
        'sender': 'test@example.com',
        'subject': 'Test Email',
        'body': 'This is a test email.',
        'package_code': None,
    }
})
print(f'Task ID: {result.id}')
print(f'Result: {result.get(timeout=10)}')
"
```

### Test 2: Idempotency Verification

Send the same email twice (same `message_id`) - should return cached result on second call:

```bash
python -c "
from worker.worker import ingest_email

# First call
result1 = ingest_email.apply_async(kwargs={
    'email_payload': {
        'message_id': 'test-idempotent-001',
        'sender': 'test@example.com',
        'subject': 'Idempotency Test',
        'body': 'Testing idempotency.',
    }
})
print(f'First call: {result1.get(timeout=10)}')

# Second call with same message_id
result2 = ingest_email.apply_async(kwargs={
    'email_payload': {
        'message_id': 'test-idempotent-001',
        'sender': 'test@example.com',
        'subject': 'Idempotency Test',
        'body': 'Testing idempotency.',
    }
})
print(f'Second call (should be cached): {result2.get(timeout=10)}')
"
```

### Test 3: Overdue Task Escalation

First, create an overdue task:

```bash
python -c "
from app.database import get_db
from app.tools.models import Package, Task
from datetime import datetime, timedelta

db = get_db()

# Create or use existing package
pkg = db.query(Package).first()
if not pkg:
    from uuid import uuid4
    pkg = Package(id=str(uuid4()), code='P-TEST', title='Test Package')
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

# Create an overdue task
task = Task(
    package_id=pkg.id,
    title='Overdue Task',
    due_date=datetime.utcnow() - timedelta(days=5),
    assignee_id='user-001',
    status='pending',
)
db.add(task)
db.commit()

print(f'Created overdue task: {task.id}')
db.close()
"
```

Then trigger the scheduled task:

```bash
python -c "
from worker.worker import check_overdue_tasks

result = check_overdue_tasks.apply_async()
print(f'Task ID: {result.id}')
print(f'Result: {result.get(timeout=10)}')
"
```

## Monitoring

### View Worker Logs

```bash
celery -A worker.celery_app events  # Real-time monitoring
celery -A worker.celery_app inspect active  # Active tasks
celery -A worker.celery_app inspect stats  # Worker stats
```

### View Scheduled Tasks

```bash
celery -A worker.celery_app inspect scheduled
```

### View Event Timeline in Database

```bash
python -c "
from app.database import get_db
from app.tools.models import Event, EventType

db = get_db()
events = db.query(Event).filter(
    Event.event_type.in_([
        EventType.TASK_ESCALATED,
        EventType.EMAIL_INGESTED,
    ])
).order_by(Event.created_at.desc()).limit(20).all()

for evt in events:
    print(f'{evt.created_at} | {evt.event_type.value} | {evt.entity_id}')
    print(f'  Payload: {evt.payload}')
    print()

db.close()
"
```

## Error Handling & Retries

- **Max retries:** 3 (per task configuration)
- **Retry delay:** Exponential backoff starting at 60-120 seconds
- **Acks late:** Tasks are acknowledged only after successful completion
- **Dead-letter queue:** Failed tasks after max retries are sent to `dead_letter` queue (can be monitored separately)

To inspect tasks in the dead-letter queue:

```bash
celery -A worker.celery_app inspect active_queues
# Look for 'dead_letter' queue
```

## Configuration

Edit `worker.py` to customize:

```python
# Scheduled task timing
celery_app.conf.beat_schedule = {
    "check-overdue-tasks-daily": {
        "schedule": crontab(hour=0, minute=0),  # Change hour/minute
    }
}

# Retry policy
celery_app.conf.task_default_retry_delay = 60  # Seconds
celery_app.conf.task_max_retries = 3

# Other settings
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
```

## Environment Variables

- `CELERY_BROKER`: Redis broker URL (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: Result backend URL (default: uses broker)
- `DATABASE_URL`: PostgreSQL connection string (default: `sqlite:///./test.db`)
- `SQL_ECHO`: Enable SQL logging (set to `true` for debug)
