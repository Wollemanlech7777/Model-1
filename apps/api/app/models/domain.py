"""Pydantic domain models — workflow-agnostic."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.enums import (
    AvatarExpression,
    ConnectorStatus,
    ConnectorType,
    DecisionOutcome,
    EnvironmentStatus,
    EvidenceKind,
    ExecutionEventType,
    JobStatus,
    SemanticSystemState,
)


class DomainModel(BaseModel):
    model_config = {"from_attributes": True}


class Customer(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    external_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomerEnvironment(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    name: str
    status: EnvironmentStatus = EnvironmentStatus.DRAFT
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConnectorConfig(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    environment_id: UUID
    connector_type: ConnectorType
    name: str
    status: ConnectorStatus = ConnectorStatus.DISCOVERED
    config: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None


class Job(DomainModel):
    """A single operational run. Workflow kind is opaque until a demo workflow is chosen."""

    id: UUID = Field(default_factory=uuid4)
    environment_id: UUID
    status: JobStatus = JobStatus.PENDING
    workflow_key: str | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SourceRef(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    connector_type: ConnectorType
    label: str
    external_ref: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class Evidence(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    source_id: UUID | None = None
    kind: EvidenceKind
    field_or_excerpt: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRecord(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    outcome: DecisionOutcome
    allow_external_write: bool
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)


class ExecutionEvent(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    event_type: ExecutionEventType
    message: str
    success: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    created_at: datetime | None = None


class SemanticUIState(DomainModel):
    """Presentation state only — never grants write authority."""

    state: SemanticSystemState
    severity: str = "low"
    reason: str
    message: str
    expression: AvatarExpression
    animation: str | None = None
