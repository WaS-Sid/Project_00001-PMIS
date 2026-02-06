from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import (
    String, Integer, DateTime, Boolean, JSON, ForeignKey, Index, UniqueConstraint,
    Enum as SQLEnum, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    PACKAGE_PATCHED = "package_patched"
    APPROVAL_CREATED = "approval_created"
    APPROVAL_DECIDED = "approval_decided"
    MEMORY_STORED = "memory_stored"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryType(str, Enum):
    CONTEXT = "context"
    DECISION = "decision"
    ANALYSIS = "analysis"
    INTEGRATION = "integration"


# ============== Models ==============


class Package(Base):
    """Core package entity."""
    __tablename__ = "packages"

    id = String(36, primary_key=True, default=lambda: str(uuid4()))
    code = String(50, unique=True, index=True, nullable=False)
    title = String(255, nullable=False)
    metadata = JSON(nullable=True)
    created_at = DateTime(timezone=True, server_default=func.now())
    updated_at = DateTime(timezone=True, server_default=func.now(), onupdate=func.now())

    tasks = relationship("Task", back_populates="package", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="package", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="package", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="package", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_packages_code", "code"),)


class Task(Base):
    """Task entity with audit trail."""
    __tablename__ = "tasks"

    id = String(36, primary_key=True, default=lambda: str(uuid4()))
    package_id = String(36, ForeignKey("packages.id"), nullable=False, index=True)
    title = String(255, nullable=False)
    due_date = DateTime(timezone=True, nullable=True)
    assignee_id = String(50, nullable=True)
    source_id = String(50, nullable=True)
    correlation_id = String(100, index=True, nullable=True)
    status = String(50, default="pending")
    created_at = DateTime(timezone=True, server_default=func.now())
    updated_at = DateTime(timezone=True, server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="tasks")
    events = relationship("Event", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_tasks_correlation_id", "correlation_id"),)


class Event(Base):
    """Event log for audit trail and event sourcing."""
    __tablename__ = "events"

    id = String(36, primary_key=True, default=lambda: str(uuid4()))
    event_type = SQLEnum(EventType, native_enum=False, nullable=False)
    package_id = String(36, ForeignKey("packages.id"), nullable=True, index=True)
    task_id = String(36, ForeignKey("tasks.id"), nullable=True, index=True)
    entity_type = String(50, index=True, nullable=False)  # 'package', 'task', 'approval'
    entity_id = String(36, index=True, nullable=False)
    payload = JSON(nullable=False)
    triggered_by = String(50, nullable=False)
    correlation_id = String(100, index=True, nullable=True)
    idempotency_key = String(100, index=True, nullable=True)
    created_at = DateTime(timezone=True, server_default=func.now(), index=True)

    package = relationship("Package", back_populates="events")
    task = relationship("Task", back_populates="events")

    __table_args__ = (
        Index("ix_events_entity", "entity_type", "entity_id"),
        Index("ix_events_idempotency", "idempotency_key"),
        UniqueConstraint("idempotency_key", name="uq_event_idempotency"),
    )


class Approval(Base):
    """Approval workflow for package patches."""
    __tablename__ = "approvals"

    id = String(36, primary_key=True, default=lambda: str(uuid4()))
    package_id = String(36, ForeignKey("packages.id"), nullable=False, index=True)
    patch_json = JSON(nullable=False)
    reason = String(500, nullable=False)
    requested_by = String(50, nullable=False)
    status = SQLEnum(ApprovalStatus, native_enum=False, default=ApprovalStatus.PENDING)
    decided_by = String(50, nullable=True)
    decision_reason = String(500, nullable=True)
    idempotency_key = String(100, unique=True, nullable=True, index=True)
    created_at = DateTime(timezone=True, server_default=func.now())
    decided_at = DateTime(timezone=True, nullable=True)

    package = relationship("Package", back_populates="approvals")
    events = relationship("Event", backref="approval")

    __table_args__ = (Index("ix_approvals_status", "status"),)


class Memory(Base):
    """Store memory/context for entities (e.g., conversation history, analysis notes)."""
    __tablename__ = "memories"

    id = String(36, primary_key=True, default=lambda: str(uuid4()))
    package_id = String(36, ForeignKey("packages.id"), nullable=True, index=True)
    entity_type = String(50, index=True, nullable=False)  # 'package', 'task', 'user'
    entity_id = String(36, index=True, nullable=False)
    memory_type = SQLEnum(MemoryType, native_enum=False)
    content = String(2000, nullable=False)
    metadata = JSON(nullable=True)
    source_refs = JSON(nullable=True)  # References to source (e.g., event IDs, task IDs)
    created_at = DateTime(timezone=True, server_default=func.now())
    updated_at = DateTime(timezone=True, server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="memories")

    __table_args__ = (
        Index("ix_memories_entity", "entity_type", "entity_id"),
        Index("ix_memories_type", "memory_type"),
    )


class IdempotencyLog(Base):
    """Track idempotency keys to prevent duplicate writes."""
    __tablename__ = "idempotency_logs"

    idempotency_key = String(100, primary_key=True)
    operation = String(100, nullable=False)
    result = JSON(nullable=False)
    created_at = DateTime(timezone=True, server_default=func.now())
