"""PostgreSQL persistence + CRM idempotency tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.db.session import get_engine, get_session_factory
from app.models.enums import DecisionOutcome
from app.models.orm import CrmActivityORM, JobORM
from app.services.job_store import JOB_STORE, PostgresJobStore
from app.services.policy_review.orchestrator import PolicyReviewOrchestrator
from integrations.simulated_world import WORLD


def _db_available() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not available (start docker compose db + run alembic upgrade)",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    WORLD.reset()
    JOB_STORE.reset()
    yield
    WORLD.reset()
    JOB_STORE.reset()


def _orch() -> PolicyReviewOrchestrator:
    return PolicyReviewOrchestrator(store=JOB_STORE, skip_interpretation=True)


def test_create_and_read_persisted_job() -> None:
    orch = _orch()
    created = orch.run_from_message("Revisa la póliza POL-2831")
    loaded = JOB_STORE.get(created["id"])
    assert loaded is not None
    assert loaded["id"] == created["id"]
    assert loaded["policy_id"] == "POL-2831"
    assert loaded["decision"] == DecisionOutcome.REVIEW.value


def test_evidence_and_timeline_persisted() -> None:
    created = _orch().run_from_message("Revisa la póliza POL-2831")
    loaded = JOB_STORE.get(created["id"])
    assert loaded is not None
    assert len(loaded["evidence"]) >= 4
    assert any(e["source"] == "crm" for e in loaded["evidence"])
    assert any("CRM GET → 200" in e["message"] for e in loaded["timeline"])
    assert any("Conflict detected" in e["message"] for e in loaded["timeline"])


def test_interpretation_persisted_when_present() -> None:
    # Force fallback interpretation through public path.
    orch = PolicyReviewOrchestrator(store=JOB_STORE, skip_interpretation=False)
    # Use a client that fails so fallback is persisted without live Gemini.
    from app.services.gemini.client import GeminiClient, GeminiClientError

    def boom(_s: str, _u: str) -> str:
        raise GeminiClientError("gemini_error:down")

    orch.gemini_client = GeminiClient(generate_fn=boom)
    created = orch.run_from_message("Revisa la póliza POL-2831")
    loaded = JOB_STORE.get(created["id"])
    assert loaded is not None
    assert loaded.get("interpretation") is not None
    assert loaded.get("interpretation_source") == "fallback"
    assert loaded.get("presentation") is not None


def test_review_does_not_create_crm_activity() -> None:
    _orch().run_from_message("Revisa la póliza POL-2831")
    assert JOB_STORE.list_crm_activities() == []


def test_fail_does_not_create_crm_activity() -> None:
    _orch().run_from_message("Revisa la póliza POL-77102")
    assert JOB_STORE.list_crm_activities() == []


def test_execute_creates_exactly_one_crm_activity() -> None:
    created = _orch().run_from_message("Revisa la póliza POL-48291")
    activities = JOB_STORE.list_crm_activities()
    assert len(activities) == 1
    assert activities[0]["policy_id"] == "POL-48291"
    assert activities[0]["type"] == "policy_status_review"
    assert activities[0]["job_id"] == created["id"]
    loaded = JOB_STORE.get(created["id"])
    assert loaded is not None
    assert loaded["crm_write"]["performed"] is True


def test_crm_activity_idempotent_for_same_job() -> None:
    created = _orch().run_from_message("Revisa la póliza POL-48291")
    assert len(JOB_STORE.list_crm_activities()) == 1

    # Re-save the same job payload — must not create a second activity.
    again = JOB_STORE.save(created)
    assert again["id"] == created["id"]
    assert len(JOB_STORE.list_crm_activities()) == 1

    session = get_session_factory()()
    try:
        count = len(session.scalars(select(CrmActivityORM)).all())
        assert count == 1
    finally:
        session.close()


def test_crm_activity_idempotent_across_new_jobs_same_policy() -> None:
    """Second EXECUTE for the same policy_id must not create another CRM activity."""
    first = _orch().run_from_message("Revisa la póliza POL-48291")
    second = _orch().run_from_message("Revisa la póliza POL-48291")
    assert first["id"] != second["id"]
    assert first["decision"] == DecisionOutcome.EXECUTE.value
    assert second["decision"] == DecisionOutcome.EXECUTE.value
    assert second["status"] == "completed"
    assert second.get("crm_write", {}).get("performed") is True

    activities = JOB_STORE.list_crm_activities()
    assert len(activities) == 1
    assert activities[0]["policy_id"] == "POL-48291"
    assert activities[0]["type"] == "policy_status_review"
    # Canonical row stays tied to the first successful write's job.
    assert activities[0]["job_id"] == first["id"]

    # New job row must still be readable (HTTP 200 equivalent).
    loaded = JOB_STORE.get(second["id"])
    assert loaded is not None
    assert loaded["policy_id"] == "POL-48291"
    assert loaded["decision"] == DecisionOutcome.EXECUTE.value


def test_second_execute_http_200_same_policy() -> None:
    """POST /jobs/policy-review twice for POL-48291 → both 200, one CRM activity."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r1 = client.post("/jobs/policy-review", json={"message": "Revisa la póliza POL-48291"})
    r2 = client.post("/jobs/policy-review", json={"message": "Revisa la póliza POL-48291"})
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] != r2.json()["id"]
    assert r1.json()["decision"] == DecisionOutcome.EXECUTE.value
    assert r2.json()["decision"] == DecisionOutcome.EXECUTE.value
    assert len(JOB_STORE.list_crm_activities()) == 1


def test_crm_policy_type_unique_constraint_active() -> None:
    """DB UNIQUE(policy_id, activity_type) must remain enforced."""
    session = get_session_factory()()
    try:
        n = session.execute(
            text("SELECT COUNT(*) FROM pg_constraint WHERE conname = 'uq_crm_activities_policy_type'")
        ).scalar()
        assert n == 1
    finally:
        session.close()


def test_jobs_survive_new_store_instance() -> None:
    """Simulate process restart: new store instance, same DB."""
    created = _orch().run_from_message("Revisa la póliza POL-48291")
    job_id = created["id"]

    restarted = PostgresJobStore()
    loaded = restarted.get(job_id)
    assert loaded is not None
    assert loaded["decision"] == DecisionOutcome.EXECUTE.value
    assert len(restarted.list_crm_activities()) == 1

    session = get_session_factory()()
    try:
        row = session.get(JobORM, __import__("uuid").UUID(job_id))
        assert row is not None
        assert row.policy_id == "POL-48291"
    finally:
        session.close()
