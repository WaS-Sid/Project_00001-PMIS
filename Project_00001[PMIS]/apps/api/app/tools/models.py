from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import (
    String, Integer, DateTime, Boolean, JSON, ForeignKey, Index, UniqueConstraint,
    Enum as SQLEnum, create_engine, Column
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_ESCALATED = "task_escalated"
    PACKAGE_PATCHED = "package_patched"
    APPROVAL_CREATED = "approval_created"
    APPROVAL_DECIDED = "approval_decided"
    MEMORY_STORED = "memory_stored"
    EMAIL_INGESTED = "email_ingested"


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

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved keyword)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tasks = relationship("Task", back_populates="package", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="package", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="package", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="package", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_packages_code", "code"),)


class Task(Base):
    """Task entity with audit trail."""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_id = Column(String(36), ForeignKey("packages.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    assignee_id = Column(String(50), nullable=True)
    source_id = Column(String(50), nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="tasks")
    events = relationship("Event", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_tasks_correlation_id", "correlation_id"),)


class Event(Base):
    """Event log for audit trail and event sourcing."""
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type = Column(SQLEnum(EventType, native_enum=False), nullable=False)
    package_id = Column(String(36), ForeignKey("packages.id"), nullable=True, index=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    entity_type = Column(String(50), index=True, nullable=False)  # 'package', 'task', 'approval'
    entity_id = Column(String(36), index=True, nullable=False)
    payload = Column(JSON, nullable=False)
    triggered_by = Column(String(50), nullable=False)
    correlation_id = Column(String(100), index=True, nullable=True)
    idempotency_key = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

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

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_id = Column(String(36), ForeignKey("packages.id"), nullable=False, index=True)
    patch_json = Column(JSON, nullable=False)
    reason = Column(String(500), nullable=False)
    requested_by = Column(String(50), nullable=False)
    status = Column(SQLEnum(ApprovalStatus, native_enum=False), default=ApprovalStatus.PENDING)
    decided_by = Column(String(50), nullable=True)
    decision_reason = Column(String(500), nullable=True)
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)

    package = relationship("Package", back_populates="approvals")
    events = relationship("Event", backref="approval")

    __table_args__ = (Index("ix_approvals_status", "status"),)


class Memory(Base):
    """Store memory/context for entities (e.g., conversation history, analysis notes)."""
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_id = Column(String(36), ForeignKey("packages.id"), nullable=True, index=True)
    entity_type = Column(String(50), index=True, nullable=False)  # 'package', 'task', 'user'
    entity_id = Column(String(36), index=True, nullable=False)
    memory_type = Column(SQLEnum(MemoryType, native_enum=False))
    content = Column(String(2000), nullable=False)
    attrs = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved keyword)
    source_refs = Column(JSON, nullable=True)  # References to source (e.g., event IDs, task IDs)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    package = relationship("Package", back_populates="memories")

    __table_args__ = (
        Index("ix_memories_entity", "entity_type", "entity_id"),
        Index("ix_memories_type", "memory_type"),
    )


class IdempotencyLog(Base):
    """Track idempotency keys to prevent duplicate writes."""
    __tablename__ = "idempotency_logs"

    idempotency_key = Column(String(100), primary_key=True)
    operation = Column(String(100), nullable=False)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ============== SupportBot / Object Storage Models ==============

class Object(Base):
    """Represents an uploaded object stored in object store (S3/MinIO)"""
    __tablename__ = "objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(50), index=True, nullable=False)
    uploaded_by = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    size = Column(Integer, nullable=True)
    storage_path = Column(String(1024), nullable=False)  # bucket/key or URL
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    artifacts = relationship("ObjectArtifact", back_populates="object", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_objects_tenant", "tenant_id"),)


class ObjectArtifact(Base):
    """Extracted artifact from an object (OCR text, entities, transcript, etc.)"""
    __tablename__ = "object_artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    object_id = Column(String(36), ForeignKey("objects.id"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False)  # e.g., 'ocr', 'text', 'entities', 'transcript'
    data = Column(JSON, nullable=True)
    text = Column(String, nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    object = relationship("Object", back_populates="artifacts")

    __table_args__ = (Index("ix_object_artifacts_object", "object_id"),)


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Ticket(Base):
    """Lightweight ticketing table used by SupportBot for audit and idempotent ticket creation."""
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(50), index=True, nullable=False)
    created_by = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=True)
    status = Column(SQLEnum(TicketStatus, native_enum=False), default=TicketStatus.OPEN)
    evidence = Column(JSON, nullable=True)  # list of evidence refs {object_id, artifact_id, snippet}
    external_ticket_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_tickets_tenant_status", "tenant_id", "status"),
        UniqueConstraint("idempotency_key", name="uq_tickets_idempotency"),
    )


# ============== Ops / Incidents / Telemetry / TechRadar Models ==============


class IncidentSeverity(str, Enum):
    SEV0 = "sev0"
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"


class IncidentStatus(str, Enum):
    OPEN = "open"
    ACKED = "acknowledged"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(50), index=True, nullable=False)
    created_by = Column(String(50), nullable=False)
    severity = Column(SQLEnum(IncidentSeverity, native_enum=False), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(String(4000), nullable=True)
    status = Column(SQLEnum(IncidentStatus, native_enum=False), default=IncidentStatus.OPEN)
    correlation_id = Column(String(100), nullable=True, index=True)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_incidents_tenant_status", "tenant_id", "status"),
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # lightweight relationship backref optional


class ServiceMode(str, Enum):
    FULL = "full"
    SAFE = "safe"
    READ_ONLY = "read_only"
    MINIMAL = "minimal"
    OFFLINE_QUEUE = "offline_queue"


class ServiceModeRecord(Base):
    __tablename__ = "service_modes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    service_name = Column(String(200), index=True, nullable=False)
    mode = Column(SQLEnum(ServiceMode, native_enum=False), nullable=False)
    set_by = Column(String(50), nullable=False)
    reason = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TelemetrySpan(Base):
    __tablename__ = "telemetry_spans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    correlation_id = Column(String(100), index=True, nullable=True)
    service = Column(String(200), nullable=True)
    name = Column(String(500), nullable=True)
    payload = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TechRadarRun(Base):
    __tablename__ = "tech_radar_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    week_tag = Column(String(20), index=True, nullable=False)  # e.g., 2026-W05
    retrieved_at = Column(DateTime(timezone=True), server_default=func.now())
    sources = Column(JSON, nullable=True)


class TechRadarItem(Base):
    __tablename__ = "tech_radar_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id = Column(String(36), ForeignKey("tech_radar_runs.id"), nullable=False, index=True)
    url = Column(String(2000), nullable=False)
    title = Column(String(1000), nullable=True)
    summary = Column(String(2000), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), server_default=func.now())


class TechRadarReport(Base):
    __tablename__ = "tech_radar_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id = Column(String(36), ForeignKey("tech_radar_runs.id"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

