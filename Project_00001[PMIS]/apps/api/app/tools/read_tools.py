from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from typing import Optional, List
from .models import Package, Task, Event, EventType
from .user_context import UserContext


def get_package_by_code(db: Session, code: str) -> Optional[dict]:
    """
    Read tool: Get package by code.
    Returns dict with id, code, title, metadata.
    """
    package = db.query(Package).filter_by(code=code).first()
    if not package:
        return None
    
    return {
        "id": package.id,
        "code": package.code,
        "title": package.title,
        "metadata": package.metadata or {},
        "created_at": package.created_at.isoformat(),
    }


def get_package(db: Session, package_id: str) -> Optional[dict]:
    """
    Read tool: Get package by ID.
    """
    package = db.query(Package).filter_by(id=package_id).first()
    if not package:
        return None
    
    return {
        "id": package.id,
        "code": package.code,
        "title": package.title,
        "metadata": package.metadata or {},
        "created_at": package.created_at.isoformat(),
        "updated_at": package.updated_at.isoformat(),
    }


def list_overdue_tasks(db: Session, project_id: Optional[str] = None) -> List[dict]:
    """
    Read tool: List overdue tasks (tasks with due_date in past).
    If project_id provided, filter by package_id.
    """
    query = db.query(Task).filter(
        and_(
            Task.due_date < datetime.utcnow(),
            Task.status != "completed"
        )
    )
    
    if project_id:
        query = query.filter_by(package_id=project_id)
    
    tasks = query.order_by(Task.due_date).all()
    
    return [
        {
            "id": t.id,
            "package_id": t.package_id,
            "title": t.title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "assignee_id": t.assignee_id,
            "status": t.status,
            "days_overdue": (datetime.utcnow() - t.due_date).days if t.due_date else None,
        }
        for t in tasks
    ]


def get_audit_timeline(
    db: Session,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> List[dict]:
    """
    Read tool: Get audit timeline for entity (events in reverse chronological order).
    entity_type: 'package', 'task', 'approval'
    """
    events = (
        db.query(Event)
        .filter(and_(Event.entity_type == entity_type, Event.entity_id == entity_id))
        .order_by(desc(Event.created_at))
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": e.id,
            "event_type": e.event_type.value if hasattr(e.event_type, 'value') else str(e.event_type),
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "payload": e.payload,
            "triggered_by": e.triggered_by,
            "created_at": e.created_at.isoformat(),
            "correlation_id": e.correlation_id,
        }
        for e in events
    ]
