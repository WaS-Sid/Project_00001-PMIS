"""
Celery worker for PMIS async tasks and scheduled jobs.

Tasks:
- check_overdue_tasks: daily scheduled job to create escalation events
- ingest_email: placeholder job to accept email payload and attach to packages
- process_task: demo async task (legacy)
"""

import os
import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from uuid import uuid4
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
broker = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
celery_app = Celery("pmis-worker", broker=broker)

# Celery Beat configuration for scheduled tasks
celery_app.conf.beat_schedule = {
    "check-overdue-tasks-daily": {
        "task": "worker.check_overdue_tasks",
        "schedule": crontab(hour=0, minute=0),  # Run daily at midnight UTC
        # For testing, use:
        # "schedule": 60.0,  # Every 60 seconds
    },
    "opsbot-supervision-every-1m": {
        "task": "apps.worker.tasks.supervision.continuous_supervision",
        "schedule": 60.0,
    },
    "tech-radar-weekly": {
        "task": "apps.worker.tasks.tech_radar.run_tech_radar",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),  # weekly on Monday 06:00 UTC
    },
}

# Celery retry and error handling configuration
celery_app.conf.task_default_retry_delay = 60  # Retry after 60 seconds
celery_app.conf.task_max_retries = 3
celery_app.conf.task_acks_late = True  # Ack after task completes
celery_app.conf.worker_prefetch_multiplier = 1  # Process one task at a time

# Dead-letter queue: tasks that fail after max retries go to 'dead_letter' queue
celery_app.conf.task_reject_on_worker_lost = True


def get_db_session():
    """Import and get a DB session."""
    from app.database import SessionLocal
    return SessionLocal()


@celery_app.task(
    name="worker.check_overdue_tasks",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def check_overdue_tasks(self):
    """
    Scheduled task: Check for overdue tasks and create escalation events (idempotent).
    
    Runs daily and:
    1. Queries for tasks with due_date in the past
    2. For each overdue task, checks if escalation event already exists (via idempotency key)
    3. Creates TASK_ESCALATED event (once per task)
    """
    try:
        db = get_db_session()
        logger.info("Starting overdue task check...")
        
        from app.tools.read_tools import list_overdue_tasks
        from app.tools.write_tools import append_event
        from app.tools.models import EventType
        from app.tools.user_context import UserContext, Role
        from app.tools.idempotency import check_idempotency, store_idempotent_result
        
        # Get overdue tasks
        overdue = list_overdue_tasks(db)
        logger.info(f"Found {len(overdue)} overdue tasks")
        
        # System user for escalation events
        system_user = UserContext(
            user_id="system-scheduler",
            name="System Scheduler",
            roles={Role.ADMIN}
        )
        
        escalated_count = 0
        for task in overdue:
            task_id = task["id"]
            package_id = task.get("package_id")
            
            # Idempotency key: ensures we only escalate once per task
            idempotency_key = f"escalate-task-{task_id}"
            
            # Check if escalation already happened
            is_new, cached = check_idempotency(
                db,
                idempotency_key,
                "escalate_task"
            )
            
            if is_new:
                try:
                    # Create escalation event
                    event = append_event(
                        db,
                        event_type=EventType.TASK_ESCALATED,
                        entity_type="task",
                        entity_id=task_id,
                        payload={
                            "task_title": task.get("title"),
                            "days_overdue": task.get("days_overdue"),
                            "due_date": task.get("due_date"),
                            "assignee_id": task.get("assignee_id"),
                        },
                        triggered_by=system_user.user_id,
                        user=system_user,
                        correlation_id=f"escalation-check-{datetime.utcnow().isoformat()}",
                        idempotency_key=idempotency_key,
                    )
                    logger.info(f"Escalated task {task_id}: event {event['event_id']}")
                    escalated_count += 1
                except Exception as e:
                    logger.error(f"Failed to escalate task {task_id}: {str(e)}")
            else:
                logger.debug(f"Task {task_id} already escalated (cached)")
        
        db.close()
        logger.info(f"Overdue task check complete. Escalated {escalated_count} tasks.")
        return {
            "status": "success",
            "overdue_count": len(overdue),
            "escalated_count": escalated_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as exc:
        logger.exception(f"Error in check_overdue_tasks: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(
    name="worker.ingest_email",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def ingest_email(self, email_payload: dict):
    """
    Task: Ingest email and attach to packages.
    
    Args:
        email_payload: dict with {
            "message_id": str (unique email ID),
            "sender": str,
            "subject": str,
            "body": str,
            "package_code": str (optional, to attach to package),
        }
    
    Returns:
        dict with status and created event ID
    """
    try:
        db = get_db_session()
        
        from app.tools.write_tools import append_event
        from app.tools.read_tools import get_package_by_code
        from app.tools.models import EventType
        from app.tools.user_context import UserContext, Role
        from app.tools.idempotency import check_idempotency, store_idempotent_result
        
        message_id = email_payload.get("message_id", str(uuid4()))
        sender = email_payload.get("sender", "unknown@example.com")
        subject = email_payload.get("subject", "")
        body = email_payload.get("body", "")
        package_code = email_payload.get("package_code")
        
        logger.info(f"Ingesting email {message_id} from {sender}")
        
        # Idempotency key: ensures we process each email once
        idempotency_key = f"email-ingest-{message_id}"
        
        # Check if email already ingested
        is_new, cached = check_idempotency(
            db,
            idempotency_key,
            "ingest_email"
        )
        
        if not is_new:
            logger.info(f"Email {message_id} already ingested (cached)")
            db.close()
            return cached
        
        # System user for email events
        system_user = UserContext(
            user_id="system-email-ingest",
            name="Email Ingestion System",
            roles={Role.ADMIN}
        )
        
        # Try to find and attach to package
        package = None
        if package_code:
            pkg_dict = get_package_by_code(db, package_code)
            if pkg_dict:
                package = pkg_dict
        
        # Create email ingestion event
        entity_id = package["id"] if package else f"email-{message_id}"
        entity_type = "package" if package else "email"
        
        event = append_event(
            db,
            event_type=EventType.EMAIL_INGESTED,
            entity_type=entity_type,
            entity_id=entity_id,
            payload={
                "message_id": message_id,
                "sender": sender,
                "subject": subject,
                "body_length": len(body),
                "package_code": package_code,
                "attached_to_package": bool(package),
            },
            triggered_by=system_user.user_id,
            user=system_user,
            correlation_id=f"email-ingest-{datetime.utcnow().isoformat()}",
            idempotency_key=idempotency_key,
        )
        
        db.close()
        
        logger.info(
            f"Email {message_id} ingested successfully. "
            f"Event: {event['event_id']}, "
            f"Attached: {bool(package)}"
        )
        
        return {
            "status": "success",
            "message_id": message_id,
            "event_id": event["event_id"],
            "attached_to_package": bool(package),
            "package_code": package_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as exc:
        logger.exception(f"Error ingesting email {email_payload.get('message_id')}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=120 * (self.request.retries + 1))


@celery_app.task
def hello_task(name: str = "world"):
    """Simple hello task for testing."""
    try:
        from common import greet
    except Exception:
        def greet(n="world"):
            return f"Hello, {n}! (fallback)"

    return greet(name)


@celery_app.task
def process_task(name: str, data: dict):
    """Process an async task: demo task that echoes input and adds timestamp."""
    import time

    try:
        from common import greet
        greeting = greet(name)
    except Exception:
        greeting = f"Hello, {name}!"

    logger.info(f"Processing task '{name}' with data: {data}")

    # Simulate some work
    time.sleep(1)

    result = {
        "name": name,
        "greeting": greeting,
        "input_data": data,
        "timestamp": datetime.utcnow().isoformat(),
        "processed": True,
    }

    logger.info(f"Task '{name}' completed: {result}")
    return result


# Ensure Celery registers external task modules
try:
    import importlib
    importlib.import_module("apps.worker.tasks.supervision")
    importlib.import_module("apps.worker.tasks.tech_radar")
except Exception:
    logger.info("Optional task modules not imported: supervision/tech_radar")
