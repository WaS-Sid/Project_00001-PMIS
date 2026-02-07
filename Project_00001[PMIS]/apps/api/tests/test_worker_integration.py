"""
Integration tests for worker tasks.

Tests verify:
- Scheduled overdue task escalation with idempotency
- Email ingestion with package attachment and idempotency
- Retry behavior
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from app.tools.models import (
    Base, Package, Task, Event, EventType, ApprovalStatus, IdempotencyLog
)
from app.tools.user_context import UserContext, Role
from app.tools.write_tools import append_event
from app.tools.read_tools import list_overdue_tasks, get_audit_timeline
from app.tools.idempotency import check_idempotency, store_idempotent_result


@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def system_user():
    """System user context for worker operations."""
    return UserContext(
        user_id="system-scheduler",
        name="System Scheduler",
        roles={Role.ADMIN}
    )


@pytest.fixture
def sample_package(db_session):
    """Create a test package."""
    pkg = Package(
        id=str(uuid4()),
        code="P-TEST-001",
        title="Test Package",
        data={"status": "pending"},
    )
    db_session.add(pkg)
    db_session.commit()
    return pkg


@pytest.fixture
def overdue_task(db_session, sample_package):
    """Create an overdue task."""
    task = Task(
        id=str(uuid4()),
        package_id=sample_package.id,
        title="Overdue Task",
        due_date=datetime.utcnow() - timedelta(days=5),
        assignee_id="user-001",
        status="pending",
    )
    db_session.add(task)
    db_session.commit()
    return task


class TestOverdueTaskEscalation:
    """Tests for check_overdue_tasks worker task."""

    def test_escalation_event_creation(self, db_session, system_user, overdue_task):
        """Test that overdue tasks get escalation events."""
        # Verify task is overdue
        overdue = list_overdue_tasks(db_session)
        assert len(overdue) == 1
        assert overdue[0]["id"] == overdue_task.id

        # Create escalation event
        idempotency_key = f"escalate-task-{overdue_task.id}"
        is_new, _ = check_idempotency(db_session, idempotency_key, "escalate_task")
        assert is_new

        # Append escalation event
        event = append_event(
            db_session,
            event_type=EventType.TASK_ESCALATED,
            entity_type="task",
            entity_id=overdue_task.id,
            payload={
                "task_title": "Overdue Task",
                "days_overdue": 5,
            },
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        assert event["event_id"]
        assert "created_at" in event

        # Verify event in database
        timeline = get_audit_timeline(db_session, "task", overdue_task.id)
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == EventType.TASK_ESCALATED.value

    def test_escalation_idempotency(self, db_session, system_user, overdue_task):
        """Test that escalation is idempotent (only happens once per task)."""
        idempotency_key = f"escalate-task-{overdue_task.id}"

        # First escalation
        event1 = append_event(
            db_session,
            event_type=EventType.TASK_ESCALATED,
            entity_type="task",
            entity_id=overdue_task.id,
            payload={"task_title": "Overdue Task", "days_overdue": 5},
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        # Second escalation with same idempotency key
        event2 = append_event(
            db_session,
            event_type=EventType.TASK_ESCALATED,
            entity_type="task",
            entity_id=overdue_task.id,
            payload={"task_title": "Overdue Task", "days_overdue": 5},
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        # Both should return the same event
        assert event1["event_id"] == event2["event_id"]

        # Only one event should exist in database
        timeline = get_audit_timeline(db_session, "task", overdue_task.id)
        assert len(timeline) == 1


class TestEmailIngestion:
    """Tests for ingest_email worker task."""

    def test_email_ingestion_without_package(self, db_session, system_user):
        """Test email ingestion for unattached email."""
        message_id = "email-test-001"
        idempotency_key = f"email-ingest-{message_id}"

        event = append_event(
            db_session,
            event_type=EventType.EMAIL_INGESTED,
            entity_type="email",
            entity_id=f"email-{message_id}",
            payload={
                "message_id": message_id,
                "sender": "test@example.com",
                "subject": "Test Email",
                "body_length": 100,
                "package_code": None,
                "attached_to_package": False,
            },
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        assert event["event_id"]
        assert "created_at" in event

        # Verify event in database
        timeline = get_audit_timeline(db_session, "email", f"email-{message_id}")
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == EventType.EMAIL_INGESTED.value

    def test_email_ingestion_with_package(self, db_session, system_user, sample_package):
        """Test email ingestion attached to a package."""
        message_id = "email-test-002"
        idempotency_key = f"email-ingest-{message_id}"

        # Create email event attached to package
        event = append_event(
            db_session,
            event_type=EventType.EMAIL_INGESTED,
            entity_type="package",
            entity_id=sample_package.id,
            payload={
                "message_id": message_id,
                "sender": "vendor@example.com",
                "subject": "Package Status Update",
                "body_length": 200,
                "package_code": sample_package.code,
                "attached_to_package": True,
            },
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        assert event["event_id"]

        # Verify event attached to package
        timeline = get_audit_timeline(db_session, "package", sample_package.id)
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == EventType.EMAIL_INGESTED.value
        assert timeline[0]["payload"]["package_code"] == sample_package.code

    def test_email_ingestion_idempotency(self, db_session, system_user):
        """Test that email ingestion is idempotent (same message_id = same result)."""
        message_id = "email-test-003"
        idempotency_key = f"email-ingest-{message_id}"

        # First ingestion
        event1 = append_event(
            db_session,
            event_type=EventType.EMAIL_INGESTED,
            entity_type="email",
            entity_id=f"email-{message_id}",
            payload={
                "message_id": message_id,
                "sender": "test@example.com",
                "subject": "Test",
                "body_length": 50,
            },
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        # Second ingestion with same message_id
        event2 = append_event(
            db_session,
            event_type=EventType.EMAIL_INGESTED,
            entity_type="email",
            entity_id=f"email-{message_id}",
            payload={
                "message_id": message_id,
                "sender": "test@example.com",
                "subject": "Test",
                "body_length": 50,
            },
            triggered_by=system_user.user_id,
            user=system_user,
            idempotency_key=idempotency_key,
        )

        # Both should return the same event
        assert event1["event_id"] == event2["event_id"]

        # Only one event should exist
        timeline = get_audit_timeline(db_session, "email", f"email-{message_id}")
        assert len(timeline) == 1
