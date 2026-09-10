"""Job persistence — in-memory (tests) and PostgreSQL (runtime source of truth)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_session_factory
from app.models.orm import (
    CrmActivityORM,
    DecisionORM,
    EvidenceORM,
    ExecutionEventORM,
    JobORM,
    PresentationStateORM,
)


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class JobStore(Protocol):
    def reset(self) -> None: ...

    def save(self, job: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, job_id: str) -> dict[str, Any] | None: ...


class InMemoryJobStore:
    """Process-local store — used by unit tests that do not need Postgres."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        with self._lock:
            self._jobs.clear()

    def save(self, job: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job_id = str(job.get("id") or uuid4())
            stored = deepcopy(job)
            stored["id"] = job_id
            self._jobs[job_id] = stored
            return deepcopy(stored)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None


class PostgresJobStore:
    """PostgreSQL-backed job store — runtime source of truth."""

    def reset(self) -> None:
        session = get_session_factory()()
        try:
            session.execute(delete(CrmActivityORM))
            session.execute(delete(EvidenceORM))
            session.execute(delete(ExecutionEventORM))
            session.execute(delete(DecisionORM))
            session.execute(delete(PresentationStateORM))
            session.execute(delete(JobORM))
            session.commit()
        finally:
            session.close()

    def save(self, job: dict[str, Any]) -> dict[str, Any]:
        session = get_session_factory()()
        try:
            stored = self._save(session, job)
            session.commit()
            return stored
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, job_id: str) -> dict[str, Any] | None:
        session = get_session_factory()()
        try:
            return self._load(session, job_id)
        finally:
            session.close()

    def list_crm_activities(self) -> list[dict[str, Any]]:
        session = get_session_factory()()
        try:
            rows = session.scalars(
                select(CrmActivityORM).order_by(CrmActivityORM.created_at.asc())
            ).all()
            return [self._activity_dict(row) for row in rows]
        finally:
            session.close()

    def clear_crm_activities(self) -> None:
        session = get_session_factory()()
        try:
            session.execute(delete(CrmActivityORM))
            session.commit()
        finally:
            session.close()

    def _save(self, session: Session, job: dict[str, Any]) -> dict[str, Any]:
        job_id = _as_uuid(job.get("id") or uuid4())
        now = datetime.now(timezone.utc)

        row = session.get(JobORM, job_id)
        if row is None:
            row = JobORM(id=job_id, created_at=now, started_at=now)
            session.add(row)

        row.status = str(job.get("status") or "completed")
        row.workflow_key = job.get("workflow_key")
        row.policy_id = job.get("policy_id")
        row.input_message = str(job.get("input_message") or "")
        row.decision = job.get("decision")
        row.allow_external_write = bool(job.get("allow_external_write"))
        row.avatar_state = job.get("avatar_state")
        row.running_avatar_state = job.get("running_avatar_state")
        row.assistant_summary = str(job.get("assistant_summary") or "")
        row.interpretation_source = job.get("interpretation_source")
        row.request_payload = {"message": job.get("input_message")}
        row.sources = dict(job.get("sources") or {})
        row.progress = list(job.get("progress") or [])
        row.reasons = list(job.get("reasons") or [])
        row.facts = dict(job.get("facts") or {})
        row.crm_write = dict(job.get("crm_write") or {})
        row.interpretation = job.get("interpretation")
        row.presentation = job.get("presentation")
        row.finished_at = now
        env_raw = job.get("environment_id")
        if env_raw:
            try:
                row.environment_id = _as_uuid(env_raw)
            except (ValueError, TypeError):
                row.environment_id = None
        else:
            row.environment_id = None

        # Replace child collections for a clean snapshot of this job.
        session.execute(delete(EvidenceORM).where(EvidenceORM.job_id == job_id))
        session.execute(delete(ExecutionEventORM).where(ExecutionEventORM.job_id == job_id))
        session.execute(delete(DecisionORM).where(DecisionORM.job_id == job_id))
        session.execute(delete(PresentationStateORM).where(PresentationStateORM.job_id == job_id))
        session.flush()

        for item in job.get("evidence") or []:
            evidence_id = _as_uuid(item.get("id") or uuid4())
            meta = {
                "relevant_data": item.get("relevant_data") or {},
                "errors": item.get("errors") or [],
                "decision": item.get("decision"),
                "timestamp": item.get("timestamp"),
                "result": item.get("result"),
                "source": item.get("source"),
            }
            row.evidence.append(
                EvidenceORM(
                    id=evidence_id,
                    kind=str(item.get("source") or "unknown"),
                    field_or_excerpt=str(item.get("result") or ""),
                    confidence=1.0,
                    metadata_=meta,
                    created_at=_parse_ts(item.get("timestamp")) or now,
                )
            )

        for event in job.get("timeline") or []:
            payload = dict(event.get("payload") or {})
            if event.get("timestamp"):
                payload = {**payload, "_timestamp": event.get("timestamp")}
            row.events.append(
                ExecutionEventORM(
                    event_type=str(event.get("event_type") or "event"),
                    message=str(event.get("message") or ""),
                    success=bool(event.get("success", True)),
                    payload=payload,
                    created_at=_parse_ts(event.get("timestamp")) or now,
                )
            )

        if job.get("decision"):
            evidence_ids = [str(item.get("id")) for item in (job.get("evidence") or []) if item.get("id")]
            row.decisions.append(
                DecisionORM(
                    outcome=str(job.get("decision")),
                    allow_external_write=bool(job.get("allow_external_write")),
                    reasons=list(job.get("reasons") or []),
                    evidence_ids=evidence_ids,
                    facts=dict(job.get("facts") or {}),
                )
            )

        presentation = job.get("presentation") or {}
        interpretation = job.get("interpretation") or {}
        if presentation or interpretation:
            row.presentation_states.append(
                PresentationStateORM(
                    state=str(
                        presentation.get("semantic_state")
                        or interpretation.get("semantic_state")
                        or "idle"
                    ),
                    severity=str(presentation.get("severity") or interpretation.get("severity") or "low"),
                    reason=str(presentation.get("reason") or interpretation.get("reason") or "n/a"),
                    message=str(
                        interpretation.get("summary")
                        or job.get("assistant_summary")
                        or ""
                    ),
                    expression=str(
                        presentation.get("expression")
                        or interpretation.get("expression")
                        or job.get("avatar_state")
                        or "idle"
                    ),
                    animation=(
                        presentation.get("animation")
                        or interpretation.get("animation")
                        or job.get("avatar_state")
                    ),
                    raw_model_output=interpretation or None,
                    used_fallback=str(job.get("interpretation_source") or "") == "fallback",
                )
            )

        crm_write = job.get("crm_write") or {}
        if crm_write.get("performed") and crm_write.get("activity"):
            self._upsert_crm_activity(session, job_id, crm_write["activity"], job)

        session.flush()
        stored = deepcopy(job)
        stored["id"] = str(job_id)
        return stored

    def _upsert_crm_activity(
        self,
        session: Session,
        job_id: UUID,
        activity: dict[str, Any],
        job: dict[str, Any],
    ) -> None:
        """Persist at most one CRM activity per (policy_id, activity_type).

        Uses Core INSERT … ON CONFLICT DO NOTHING so a second EXECUTE job does not
        leave a pending CrmActivityORM on the Job relationship (cascade) that would
        re-INSERT and raise UniqueViolation on the outer session.flush().
        """
        policy_id = str(activity.get("policy_id") or job.get("policy_id") or "")
        activity_type = str(activity.get("type") or "policy_status_review")

        existing = session.scalar(
            select(CrmActivityORM).where(
                CrmActivityORM.policy_id == policy_id,
                CrmActivityORM.activity_type == activity_type,
            )
        )
        if existing is not None:
            return

        external_id = activity.get("id")
        stmt = (
            pg_insert(CrmActivityORM)
            .values(
                id=uuid4(),
                job_id=job_id,
                external_id=str(external_id) if external_id else None,
                policy_id=policy_id,
                activity_type=activity_type,
                note=activity.get("note"),
                decision=str(activity.get("decision") or job.get("decision") or ""),
                payload=dict(activity),
            )
            .on_conflict_do_nothing(constraint="uq_crm_activities_policy_type")
        )
        session.execute(stmt)

    def _load(self, session: Session, job_id: str) -> dict[str, Any] | None:
        try:
            uid = _as_uuid(job_id)
        except ValueError:
            return None
        row = session.scalar(
            select(JobORM)
            .where(JobORM.id == uid)
            .options(
                selectinload(JobORM.evidence),
                selectinload(JobORM.events),
                selectinload(JobORM.decisions),
                selectinload(JobORM.presentation_states),
                selectinload(JobORM.crm_activities),
            )
        )
        if row is None:
            return None
        return self._job_dict(row)

    def _job_dict(self, row: JobORM) -> dict[str, Any]:
        evidence = []
        for item in sorted(row.evidence, key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc)):
            meta = item.metadata_ or {}
            evidence.append(
                {
                    "id": str(item.id),
                    "source": meta.get("source") or item.kind,
                    "result": meta.get("result") or item.field_or_excerpt,
                    "relevant_data": meta.get("relevant_data") or {},
                    "errors": meta.get("errors") or [],
                    "timestamp": meta.get("timestamp")
                    or (item.created_at.isoformat() if item.created_at else None),
                    "decision": meta.get("decision") or row.decision,
                }
            )

        timeline = []
        for event in sorted(row.events, key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc)):
            payload = dict(event.payload or {})
            timestamp = payload.pop("_timestamp", None) or (
                event.created_at.isoformat() if event.created_at else None
            )
            timeline.append(
                {
                    "event_type": event.event_type,
                    "message": event.message,
                    "success": event.success,
                    "payload": payload,
                    "timestamp": timestamp,
                }
            )

        return {
            "id": str(row.id),
            "status": row.status,
            "workflow_key": row.workflow_key or "policy_review",
            "policy_id": row.policy_id,
            "environment_id": str(row.environment_id) if row.environment_id else None,
            "input_message": row.input_message,
            "decision": row.decision,
            "allow_external_write": row.allow_external_write,
            "avatar_state": row.avatar_state,
            "running_avatar_state": row.running_avatar_state,
            "crm_write": dict(row.crm_write or {}),
            "sources": dict(row.sources or {}),
            "timeline": timeline,
            "evidence": evidence,
            "progress": list(row.progress or []),
            "assistant_summary": row.assistant_summary,
            "reasons": list(row.reasons or []),
            "facts": dict(row.facts or {}),
            "interpretation": row.interpretation,
            "interpretation_source": row.interpretation_source,
            "presentation": row.presentation,
        }

    @staticmethod
    def _activity_dict(row: CrmActivityORM) -> dict[str, Any]:
        payload = dict(row.payload or {})
        return {
            "id": row.external_id or str(row.id),
            "job_id": str(row.job_id),
            "policy_id": row.policy_id,
            "type": row.activity_type,
            "note": row.note,
            "decision": row.decision,
            **{k: v for k, v in payload.items() if k not in {"id", "policy_id", "type", "note", "decision"}},
        }


# Runtime source of truth.
JOB_STORE: PostgresJobStore = PostgresJobStore()
