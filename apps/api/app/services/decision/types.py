"""Inputs and outputs for the deterministic decision engine.

Workflow-agnostic: no demo-specific business rules live here yet.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.enums import DecisionOutcome


@dataclass(frozen=True)
class FactConflict:
    """Two sources disagree on a comparable field."""

    field: str
    left_source: str
    left_value: Any
    right_source: str
    right_value: Any


@dataclass(frozen=True)
class AmbiguousMatch:
    """Identity or record match is not unique / confident enough."""

    entity: str
    candidate_count: int
    confidence: float
    detail: str | None = None


@dataclass(frozen=True)
class IntegrationFailure:
    """An adapter call failed in a way that blocks safe automation."""

    connector: str
    error_code: str | None
    message: str
    blocks_writes: bool = True


@dataclass
class DecisionContext:
    """Computed facts only — never model prose as authority."""

    facts: dict[str, Any] = field(default_factory=dict)
    conflicts: list[FactConflict] = field(default_factory=list)
    ambiguous_matches: list[AmbiguousMatch] = field(default_factory=list)
    integration_failures: list[IntegrationFailure] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)
    evidence_ids: list[UUID] = field(default_factory=list)
    # Optional explicit signals for future workflow rules (unused in skeleton).
    allow_write_signal: bool | None = None


@dataclass(frozen=True)
class DecisionResult:
    outcome: DecisionOutcome
    allow_external_write: bool
    reasons: list[str]
    evidence_ids: list[UUID]
    facts: dict[str, Any]
