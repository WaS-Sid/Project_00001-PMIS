# Tool Layer Implementation

## Overview

The `apps/api/app/tools/` module provides a strict, event-driven tool layer for database operations with the following characteristics:

- **Event-first pattern**: All writes are preceded by event log entries
- **Idempotency**: Write operations are idempotent via idempotency keys
- **Audit trail**: Complete audit trail via Event table
- **Role-based access control**: UserContext for authorization checks
- **Memory/Context**: Store and search entity context (conversations, decisions, analysis)

## Architecture

### Models (`models.py`)

- **Package**: Core entity representing a package/project
- **Task**: Work items with due dates and assignees
- **Event**: Immutable event log (implements event sourcing)
- **Approval**: Workflow for approving package changes
- **Memory**: Stores context/memories for entities (conversation history, decisions, etc.)
- **IdempotencyLog**: Prevents duplicate writes by tracking idempotency keys

### Tools

#### Read Tools (`read_tools.py`)
Stateless, safe operations that don't modify state:

```python
get_package_by_code(db, code) -> Optional[dict]
get_package(db, package_id) -> Optional[dict]
list_overdue_tasks(db, project_id=None) -> List[dict]
get_audit_timeline(db, entity_type, entity_id, limit=50) -> List[dict]
```

#### Write Tools (`write_tools.py`)
All write operations are **event-first** and require idempotency keys:

```python
append_event(
    db, event_type, entity_type, entity_id, payload,
    triggered_by, user, correlation_id=None, idempotency_key=required
) -> dict

create_task(
    db, package_id, title, due_date, assignee_id, source_id,
    correlation_id, idempotency_key=required, user=required
) -> dict
    # Writes TASK_CREATED event before creating task

propose_package_patch(
    db, package_id, patch_json, reason, requested_by, user
) -> dict
    # Creates approval record (awaiting decision)

approve_proposal(
    db, approval_id, decided_by, decision, reason,
    idempotency_key=required, user=required
) -> dict
    # If approved: writes PACKAGE_PATCHED event + applies patch
    # If rejected: only writes APPROVAL_DECIDED event
    # All idempotent
```

#### Memory Tools (`memory_tools.py`)
Store and retrieve entity context:

```python
store_memory(
    db, entity_type, entity_id, content, memory_type,
    user, package_id=None, metadata=None, source_refs=None
) -> dict

search_memory(
    db, entity_type, entity_id, query=None, top_k=10,
    filters=None
) -> List[dict]
    # filters: e.g., {'memory_type': 'DECISION'}
```

### Access Control (`user_context.py`)

```python
class UserContext:
    user_id: str
    name: str
    roles: Set[Role]  # ADMIN, ANALYST, OPERATOR, VIEWER
    
    has_role(role) -> bool
    has_any_role(*roles) -> bool
    require_role(role) -> None  # Raises PermissionError
```

## Key Principles

### 1. Event-First Pattern

All writes are preceded by event creation:

```python
# WRONG: Direct write
db.add(task)
db.commit()

# RIGHT: Event-first
event = Event(event_type=TaskCreated, payload=data, ...)
db.add(event)
db.add(task)
db.commit()
```

This ensures:
- Complete audit trail
- No orphaned changes
- Ability to replay events for recovery

### 2. Idempotency

Every write operation requires an `idempotency_key`:

```python
# First call
result1 = create_task(
    db, package_id="pkg-1", title="Task", 
    idempotency_key="key-123", user=admin_user
)  # Returns {task_id: "task-1", ...}

# Retry with same key (network failure recovery)
result2 = create_task(
    db, package_id="pkg-1", title="Task",
    idempotency_key="key-123", user=admin_user
)  # Returns SAME {task_id: "task-1", ...} - no duplicate created

# Unique key = new operation
result3 = create_task(
    db, package_id="pkg-1", title="Task",
    idempotency_key="key-456", user=admin_user
)  # Returns NEW {task_id: "task-2", ...}
```

Implementation:
1. Check `IdempotencyLog` for key
2. If found, return cached result
3. If not found, perform operation & store result

### 3. Approval Workflow

Complete workflow with idempotency:

```python
# Step 1: Propose patch
proposal = propose_package_patch(
    db, package_id="pkg-1", 
    patch_json={"status": "active"},
    reason="Activate package",
    requested_by="analyst_1", user=analyst_user
)
# Creates: Approval(status=PENDING) + Event(APPROVAL_CREATED)

# Step 2: Approve (with idempotency key)
result = approve_proposal(
    db, approval_id=proposal["approval_id"],
    decision="approved", decided_by="admin_1",
    idempotency_key="approve-key-1", user=admin_user
)
# Creates: Event(PACKAGE_PATCHED) + Event(APPROVAL_DECIDED)
# Applies: patch to package.metadata
# All idempotent

# Retry = safe
result2 = approve_proposal(
    ...idempotency_key="approve-key-1"...
)  # Same result, no duplicate patch
```

## Testing

### Running tests

```bash
cd apps/api
poetry install
pytest
# or with coverage
pytest --cov=app/tools
```

### Test files

- `tests/conftest.py` — Fixtures (in-memory DB, user contexts)
- `tests/test_read_tools.py` — Read operations (get_package, list_overdue, audit_timeline)
- `tests/test_write_tools.py` — Write operations (event-first, idempotency)
- `tests/test_memory_tools.py` — Memory storage and search
- `tests/test_approval_workflow.py` — End-to-end approval workflow

### Acceptance Criteria (Tested)

✓ **No write without event**: Every write creates an event record
✓ **Idempotency**: Duplicate retries with same idempotency_key return cached result
✓ **Approval workflow**: Propose → Approve → Patch applied end-to-end

## Example: Using Tools in Routes

```python
# app/routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.tools import (
    create_task, get_package, list_overdue_tasks,
    store_memory, UserContext
)

router = APIRouter()

@router.post("/tasks")
def create_new_task(
    package_id: str,
    title: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),  # Your auth logic
):
    """Create a task using the tool layer."""
    from uuid import uuid4
    
    result = create_task(
        db=db,
        package_id=package_id,
        title=title,
        due_date=None,
        assignee_id=user.user_id,
        source_id="api",
        correlation_id=str(uuid4()),
        idempotency_key=request.headers.get("Idempotency-Key", str(uuid4())),
        user=user,
    )
    
    # Optionally store memory of this action
    store_memory(
        db=db,
        entity_type="task",
        entity_id=result["task_id"],
        content=f"Created by {user.name}",
        memory_type="context",
        user=user,
    )
    
    return result

@router.get("/packages/{package_id}/audit")
def get_package_audit(
    package_id: str,
    db: Session = Depends(get_db),
):
    """Get audit trail for a package."""
    from app.tools import get_audit_timeline
    
    return get_audit_timeline(db, "package", package_id, limit=100)
```

## Design Notes

### Why Event-First?

1. **Single source of truth**: Events are immutable changelog
2. **Auditability**: Complete history of all changes
3. **Recovery**: Can replay events to rebuild state
4. **Analysis**: Event log reveals system behavior patterns

### Why Idempotency?

1. **Network failures**: Safe to retry at any time
2. **Distributed systems**: Handle out-of-order delivery
3. **User experience**: No "double charge" or duplicate creation

### Why Separate Memory Table?

1. **Flexible context**: Store conversations, decisions, analysis without changing entity schema
2. **Scope isolation**: Entity-specific context (doesn't pollute event log)
3. **Search**: Separate query path from immutable events

## Future Enhancements

- Event versioning (schema evolution)
- Snapshot tables for large event logs (performance)
- Event replay for temporal queries
- Memory embeddings for semantic search
- Saga pattern for distributed transactions
