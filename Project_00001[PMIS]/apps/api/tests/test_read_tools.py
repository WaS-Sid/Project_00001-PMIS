import pytest
from datetime import datetime, timedelta
from app.tools.models import Package, Task, Event, EventType
from app.tools.read_tools import (
    get_package_by_code, get_package, list_overdue_tasks, get_audit_timeline
)


@pytest.fixture
def sample_package(db_session):
    """Create a sample package for testing."""
    pkg = Package(code="PKG-001", title="Sample Package", metadata={"version": "1.0"})
    db_session.add(pkg)
    db_session.commit()
    return pkg


@pytest.fixture
def sample_tasks(db_session, sample_package):
    """Create sample tasks with various due dates."""
    now = datetime.utcnow()
    
    # Overdue task
    task1 = Task(
        package_id=sample_package.id,
        title="Overdue Task",
        due_date=now - timedelta(days=5),
        status="pending",
    )
    
    # Future task
    task2 = Task(
        package_id=sample_package.id,
        title="Future Task",
        due_date=now + timedelta(days=10),
        status="pending",
    )
    
    # Completed task (should not appear in overdue)
    task3 = Task(
        package_id=sample_package.id,
        title="Completed Task",
        due_date=now - timedelta(days=3),
        status="completed",
    )
    
    db_session.add_all([task1, task2, task3])
    db_session.commit()
    
    return [task1, task2, task3]


class TestGetPackageByCode:
    def test_get_package_by_code_found(self, db_session, sample_package):
        """Test retrieving package by code."""
        result = get_package_by_code(db_session, "PKG-001")
        assert result is not None
        assert result["code"] == "PKG-001"
        assert result["title"] == "Sample Package"
        assert result["metadata"]["version"] == "1.0"
    
    def test_get_package_by_code_not_found(self, db_session):
        """Test retrieval with non-existent code."""
        result = get_package_by_code(db_session, "NONEXISTENT")
        assert result is None


class TestGetPackage:
    def test_get_package_found(self, db_session, sample_package):
        """Test retrieving package by ID."""
        result = get_package(db_session, sample_package.id)
        assert result is not None
        assert result["id"] == sample_package.id
        assert result["code"] == "PKG-001"
    
    def test_get_package_not_found(self, db_session):
        """Test retrieval with non-existent ID."""
        result = get_package(db_session, "nonexistent-id")
        assert result is None


class TestListOverdueTasks:
    def test_list_overdue_tasks_all(self, db_session, sample_tasks):
        """Test listing all overdue tasks."""
        result = list_overdue_tasks(db_session)
        assert len(result) == 1
        assert result[0]["title"] == "Overdue Task"
        assert result[0]["status"] == "pending"
        assert result[0]["days_overdue"] == 5
    
    def test_list_overdue_tasks_by_project(self, db_session, sample_package, sample_tasks):
        """Test listing overdue tasks filtered by project."""
        result = list_overdue_tasks(db_session, project_id=sample_package.id)
        assert len(result) == 1
        assert result[0]["package_id"] == sample_package.id
    
    def test_list_overdue_tasks_empty(self, db_session):
        """Test listing when no overdue tasks exist."""
        result = list_overdue_tasks(db_session)
        assert result == []


class TestGetAuditTimeline:
    def test_get_audit_timeline_for_entity(self, db_session, sample_package):
        """Test retrieving audit timeline for an entity."""
        # Create events
        event1 = Event(
            event_type=EventType.TASK_CREATED,
            entity_type="package",
            entity_id=sample_package.id,
            payload={"action": "created"},
            triggered_by="user_001",
        )
        event2 = Event(
            event_type=EventType.PACKAGE_PATCHED,
            entity_type="package",
            entity_id=sample_package.id,
            payload={"action": "patched"},
            triggered_by="user_002",
        )
        db_session.add_all([event1, event2])
        db_session.commit()
        
        # Retrieve timeline (should be in reverse chronological order)
        result = get_audit_timeline(db_session, "package", sample_package.id)
        assert len(result) == 2
        assert result[0]["event_type"] == "package_patched"  # Most recent first
        assert result[1]["event_type"] == "task_created"
    
    def test_get_audit_timeline_limit(self, db_session, sample_package):
        """Test that limit parameter restricts results."""
        # Create 5 events
        for i in range(5):
            event = Event(
                event_type=EventType.TASK_CREATED,
                entity_type="package",
                entity_id=sample_package.id,
                payload={"index": i},
                triggered_by="user_001",
            )
            db_session.add(event)
        db_session.commit()
        
        result = get_audit_timeline(db_session, "package", sample_package.id, limit=2)
        assert len(result) == 2
    
    def test_get_audit_timeline_empty(self, db_session):
        """Test timeline for entity with no events."""
        result = get_audit_timeline(db_session, "package", "nonexistent-id")
        assert result == []
