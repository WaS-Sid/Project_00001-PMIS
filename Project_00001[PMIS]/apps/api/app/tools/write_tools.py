from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from uuid import uuid4
from typing import Optional, Dict, Any
import json

from .models import (
    Event, EventType, Task, Package, Approval, ApprovalStatus,
    IdempotencyLog,
)
from .user_context import UserContext
from .idempotency import check_idempotency, store_idempotent_result


def append_event(
    db: Session,
    event_type: EventType,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    triggered_by: str,
    user: UserContext,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Write tool: Append event to audit log (event-first pattern).
    
    Args:
        db: Database session
        event_type: Type of event (task_created, package_patched, etc.)
        entity_type: Type of entity affected ('package', 'task', 'approval')
        entity_id: ID of affected entity
        payload: Event payload (dict with details)
        triggered_by: User ID or system name that triggered event
        user: UserContext for authorization
        correlation_id: Optional correlation ID for tracing
        idempotency_key: Required for write ops; ensures no duplication
    
    Returns:
        Dict with event_id, created_at, etc.
    """
    if not idempotency_key:
        raise ValueError("idempotency_key is required for event writes")
    
    # Check idempotency
    is_new, cached = check_idempotency(db, idempotency_key, f"append_event:{entity_type}")
    if not is_new:
        return cached
    
    event = Event(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        triggered_by=triggered_by,
        correlation_id=correlation_id or str(uuid4()),
        idempotency_key=idempotency_key,
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    result = {
        "event_id": event.id,
        "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
        "created_at": event.created_at.isoformat(),
        "idempotency_key": idempotency_key,
    }
    
    # Store for idempotency
    store_idempotent_result(db, idempotency_key, f"append_event:{entity_type}", result)
    
    return result


def create_task(
    db: Session,
    package_id: str,
    title: str,
    due_date: Optional[datetime],
    assignee_id: Optional[str],
    source_id: Optional[str],
    correlation_id: Optional[str],
    idempotency_key: str,
    user: UserContext,
) -> dict:
    """
    Write tool: Create task (event-first, idempotent).
    
    Writes event FIRST, then creates task record.
    Duplicate calls with same idempotency_key return cached result.
    """
    # Check idempotency
    is_new, cached = check_idempotency(db, idempotency_key, "create_task")
    if not is_new:
        return cached
    
    # Verify package exists
    package = db.query(Package).filter_by(id=package_id).first()
    if not package:
        raise ValueError(f"Package {package_id} not found")
    
    correlation_id = correlation_id or str(uuid4())
    task = Task(
        package_id=package_id,
        title=title,
        due_date=due_date,
        assignee_id=assignee_id,
        source_id=source_id,
        correlation_id=correlation_id,
        status="pending",
    )
    
    db.add(task)
    db.flush()  # Get task.id
    
    # EVENT FIRST: Write event for this task creation
    event = Event(
        event_type=EventType.TASK_CREATED,
        entity_type="task",
        entity_id=task.id,
        task_id=task.id,
        package_id=package_id,
        payload={
            "title": title,
            "due_date": due_date.isoformat() if due_date else None,
            "assignee_id": assignee_id,
            "source_id": source_id,
        },
        triggered_by=user.user_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )
    
    db.add(event)
    db.commit()
    db.refresh(task)
    
    result = {
        "task_id": task.id,
        "package_id": package_id,
        "title": title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "assignee_id": assignee_id,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
        "event_id": event.id,
    }
    
    store_idempotent_result(db, idempotency_key, "create_task", result)
    return result


def propose_package_patch(
    db: Session,
    package_id: str,
    patch_json: Dict[str, Any],
    reason: str,
    requested_by: str,
    user: UserContext,
) -> dict:
    """
    Write tool: Propose a package patch (creates approval record).
    
    Does NOT apply patch immediately; requires approval workflow.
    """
    # Verify package exists
    package = db.query(Package).filter_by(id=package_id).first()
    if not package:
        raise ValueError(f"Package {package_id} not found")
    
    approval = Approval(
        package_id=package_id,
        patch_json=patch_json,
        reason=reason,
        requested_by=requested_by,
        status=ApprovalStatus.PENDING,
    )
    
    db.add(approval)
    db.commit()
    db.refresh(approval)
    
    # Write event for proposal
    event = Event(
        event_type=EventType.APPROVAL_CREATED,
        entity_type="approval",
        entity_id=approval.id,
        package_id=package_id,
        payload={
            "patch": patch_json,
            "reason": reason,
            "requested_by": requested_by,
        },
        triggered_by=user.user_id,
        idempotency_key=None,  # Not idempotent for now
    )
    db.add(event)
    db.commit()
    
    return {
        "approval_id": approval.id,
        "status": approval.status.value,
        "created_at": approval.created_at.isoformat(),
    }


def approve_proposal(
    db: Session,
    approval_id: str,
    decided_by: str,
    decision: str,  # "approved" or "rejected"
    reason: Optional[str],
    idempotency_key: str,
    user: UserContext,
) -> dict:
    """
    Write tool: Decide on approval (event-first, idempotent).
    
    If approved: apply patch and write two events (approval_decided + package_patched).
    If rejected: just write approval_decided event.
    All idempotent.
    """
    # Check idempotency
    is_new, cached = check_idempotency(db, idempotency_key, "approve_proposal")
    if not is_new:
        return cached
    
    # Verify approval exists
    approval = db.query(Approval).filter_by(id=approval_id).first()
    if not approval:
        raise ValueError(f"Approval {approval_id} not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise ValueError(f"Approval {approval_id} already {approval.status.value}")
    
    approval.decided_by = decided_by
    approval.decision_reason = reason
    approval.decided_at = datetime.utcnow()
    
    if decision.lower() == "approved":
        approval.status = ApprovalStatus.APPROVED
        
        # Apply patch to package
        package = db.query(Package).filter_by(id=approval.package_id).first()
        if package:
            # Merge patch into metadata
            if package.metadata is None:
                package.metadata = {}
            package.metadata.update(approval.patch_json)
        
        # Write package_patched event
        patch_event = Event(
            event_type=EventType.PACKAGE_PATCHED,
            entity_type="package",
            entity_id=approval.package_id,
            package_id=approval.package_id,
            payload={
                "patch": approval.patch_json,
                "approved_by": decided_by,
                "approval_id": approval_id,
            },
            triggered_by=user.user_id,
            idempotency_key=idempotency_key,
        )
        db.add(patch_event)
    
    else:
        approval.status = ApprovalStatus.REJECTED
    
    # Write approval_decided event
    decision_event = Event(
        event_type=EventType.APPROVAL_DECIDED,
        entity_type="approval",
        entity_id=approval_id,
        package_id=approval.package_id,
        payload={
            "decision": decision,
            "decided_by": decided_by,
            "reason": reason,
        },
        triggered_by=user.user_id,
        idempotency_key=idempotency_key,
    )
    db.add(decision_event)
    db.commit()
    db.refresh(approval)
    
    result = {
        "approval_id": approval_id,
        "status": approval.status.value,
        "decision": decision,
        "decided_at": approval.decided_at.isoformat(),
    }
    
    store_idempotent_result(db, idempotency_key, "approve_proposal", result)
    return result
