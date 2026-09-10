from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.db.session import get_session_factory
from app.errors import get_request_id
from app.errors import logger as api_logger
from app.errors import sanitize_log_text
from app.models.orm import EnvironmentORM
from app.routes.schemas import JobAskRequest, PolicyReviewRequest, PolicyReviewResponse
from app.services.adapters import UnknownAdapterError
from app.services.gemini.interpret import answer_job_question
from app.services.job_store import JOB_STORE
from app.services.policy_review.runtime import create_policy_review_orchestrator

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _parse_job_id(job_id: str) -> str:
    try:
        return str(UUID(job_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="job_id must be a valid UUID") from exc


def _ensure_environment_exists(environment_id: str | None) -> None:
    """When the client supplies environment_id, require a real Environment row."""
    if environment_id is None:
        return
    try:
        uid = UUID(environment_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="environment_id must be a valid UUID") from exc

    session = get_session_factory()()
    try:
        row = session.get(EnvironmentORM, uid)
        if row is None:
            raise HTTPException(status_code=404, detail="environment not found")
    finally:
        session.close()


def _log_policy_review_outcome(request_id: str, result: dict[str, Any]) -> None:
    """Correlate request → job without logging secrets or raw payloads."""
    job_id = result.get("id")
    decision = result.get("decision")
    policy_id = result.get("policy_id")
    api_logger.info(
        "policy_review_complete request_id=%s job_id=%s decision=%s policy_id=%s",
        request_id,
        job_id,
        decision,
        policy_id,
    )
    for item in result.get("evidence") or []:
        errors = item.get("errors") or []
        if not errors:
            continue
        safe_errors = [sanitize_log_text(err, max_len=120) for err in errors[:5]]
        api_logger.warning(
            "policy_review_integration_issue request_id=%s job_id=%s source=%s errors=%s",
            request_id,
            job_id,
            item.get("source"),
            safe_errors,
        )


@router.post("/policy-review", response_model=PolicyReviewResponse)
def create_policy_review(request: Request, body: PolicyReviewRequest) -> PolicyReviewResponse:
    request_id = get_request_id(request)
    _ensure_environment_exists(body.environment_id)
    try:
        orchestrator = create_policy_review_orchestrator(environment_id=body.environment_id)
        result = orchestrator.run_from_message(body.message)
        _log_policy_review_outcome(request_id, result)
        return PolicyReviewResponse(**result)
    except HTTPException:
        raise
    except UnknownAdapterError as exc:
        raise HTTPException(
            status_code=400,
            detail="unknown adapter configuration for environment",
        ) from exc
    except Exception as exc:
        api_logger.exception(
            "policy_review_failed request_id=%s error_type=%s error=%s",
            request_id,
            type(exc).__name__,
            sanitize_log_text(exc),
        )
        raise HTTPException(status_code=500, detail="internal server error") from exc


@router.get("/{job_id}", response_model=PolicyReviewResponse)
def get_job(job_id: str) -> PolicyReviewResponse:
    parsed = _parse_job_id(job_id)
    job = JOB_STORE.get(parsed)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return PolicyReviewResponse(**job)


@router.get("/{job_id}/evidence")
def get_job_evidence(job_id: str) -> dict:
    parsed = _parse_job_id(job_id)
    job = JOB_STORE.get(parsed)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": parsed,
        "decision": job.get("decision"),
        "evidence": job.get("evidence", []),
        "timeline": job.get("timeline", []),
        "sources": job.get("sources", {}),
        "reasons": job.get("reasons", []),
        "interpretation": job.get("interpretation"),
        "presentation": job.get("presentation"),
    }


@router.post("/{job_id}/ask")
def ask_about_job(job_id: str, body: JobAskRequest) -> dict:
    parsed = _parse_job_id(job_id)
    job = JOB_STORE.get(parsed)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    result = answer_job_question(job, body.question)
    return {"job_id": parsed, **result}
