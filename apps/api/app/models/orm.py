"""SQLAlchemy ORM schema — relational persistence for Site Companion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CustomerORM(Base):
    """Tenant / account that owns one or more deployment environments."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    environments: Mapped[list[EnvironmentORM]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EnvironmentORM(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped[CustomerORM] = relationship(back_populates="environments")
    connectors: Mapped[list[ConnectorORM]] = relationship(back_populates="environment")
    jobs: Mapped[list[JobORM]] = relationship(back_populates="environment")


class ConnectorORM(Base):
    __tablename__ = "connectors"
    __table_args__ = (
        UniqueConstraint("environment_id", "connector_type", name="uq_connectors_env_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE"), nullable=False
    )
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="discovered")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    environment: Mapped[EnvironmentORM] = relationship(back_populates="connectors")


class JobORM(Base):
    """Persisted policy_review (and future) jobs — API response shape."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    workflow_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    input_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allow_external_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avatar_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    running_avatar_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assistant_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interpretation_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    progress: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    crm_write: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    interpretation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    presentation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    environment: Mapped[EnvironmentORM | None] = relationship(back_populates="jobs")
    sources_rows: Mapped[list[SourceORM]] = relationship(back_populates="job")
    evidence: Mapped[list[EvidenceORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[DecisionORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    events: Mapped[list[ExecutionEventORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    presentation_states: Mapped[list[PresentationStateORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    crm_activities: Mapped[list[CrmActivityORM]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class SourceORM(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="sources_rows")
    evidence: Mapped[list[EvidenceORM]] = relationship(back_populates="source")


class EvidenceORM(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    field_or_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="evidence")
    source: Mapped[SourceORM | None] = relationship(back_populates="evidence")


class DecisionORM(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    allow_external_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="decisions")


class ExecutionEventORM(Base):
    __tablename__ = "execution_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="events")


class PresentationStateORM(Base):
    """Persisted semantic UI state — presentation only."""

    __tablename__ = "presentation_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expression: Mapped[str] = mapped_column(String(64), nullable=False)
    animation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_model_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="presentation_states")


class CrmActivityORM(Base):
    """Persisted CRM write outcomes — at most one activity per policy+type (idempotent)."""

    __tablename__ = "crm_activities"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_crm_activities_job_id"),
        UniqueConstraint("policy_id", "activity_type", name="uq_crm_activities_policy_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(128), nullable=False, default="policy_status_review")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[JobORM] = relationship(back_populates="crm_activities")
