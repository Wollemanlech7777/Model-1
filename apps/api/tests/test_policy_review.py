from app.models.enums import DecisionOutcome
from app.services.job_store import InMemoryJobStore
from app.services.policy_review.avatar_map import (
    avatar_state_for_outcome,
    avatar_state_for_running,
)
from app.services.policy_review.extract import extract_policy_id
from app.services.policy_review.orchestrator import PolicyReviewOrchestrator
from integrations.simulated_world import WORLD


def setup_function() -> None:
    WORLD.reset()


def _orch() -> PolicyReviewOrchestrator:
    # Operational tests must not depend on live Gemini or Postgres.
    return PolicyReviewOrchestrator(store=InMemoryJobStore(), skip_interpretation=True)


def test_extract_policy_id() -> None:
    assert extract_policy_id("Revisa la póliza POL-2831") == "POL-2831"
    assert extract_policy_id("check pol-48291 please") == "POL-48291"
    assert extract_policy_id("no policy here") is None


def test_review_on_conflict_no_write() -> None:
    orch = _orch()
    result = orch.run_from_message("Revisa la póliza POL-2831")
    assert result["decision"] == DecisionOutcome.REVIEW.value
    assert result["allow_external_write"] is False
    assert result["crm_write"]["performed"] is False
    assert result["crm_write"]["skipped"] is True
    assert result["sources"]["crm"] == "ACTIVE"
    assert result["sources"]["portal"] == "CANCELLED"
    assert any("Conflict detected" in e["message"] for e in result["timeline"])
    assert any("CRM write → SKIPPED" in e["message"] for e in result["timeline"])
    assert WORLD.crm_activities == []
    assert result["avatar_state"] == "confused"


def test_execute_on_agreement_writes_crm() -> None:
    orch = _orch()
    result = orch.run_from_message("Revisa la póliza POL-48291")
    assert result["decision"] == DecisionOutcome.EXECUTE.value
    assert result["allow_external_write"] is True
    assert result["crm_write"]["performed"] is True
    assert result["crm_write"]["skipped"] is False
    assert len(WORLD.crm_activities) == 1
    assert WORLD.crm_activities[0]["policy_id"] == "POL-48291"
    assert any("CRM write → CREATED" in e["message"] for e in result["timeline"])
    assert result["avatar_state"] == "proud"


def test_fail_on_crm_401_stops_and_no_write() -> None:
    orch = _orch()
    result = orch.run_from_message("Revisa la póliza POL-77102")
    assert result["decision"] == DecisionOutcome.FAIL.value
    assert result["allow_external_write"] is False
    assert result["crm_write"]["performed"] is False
    assert result["crm_write"]["skipped"] is True
    assert WORLD.crm_activities == []
    assert any("CRM GET → 401" in e["message"] for e in result["timeline"])
    assert any("CRM write → SKIPPED" in e["message"] for e in result["timeline"])
    # Early stop: other sources should not be populated
    assert result["sources"] == {}
    assert result["avatar_state"] == "scared"


def test_write_only_on_execute_across_cases() -> None:
    orch = _orch()
    orch.run_from_message("Revisa la póliza POL-2831")
    orch.run_from_message("Revisa la póliza POL-77102")
    assert WORLD.crm_activities == []
    orch.run_from_message("Revisa la póliza POL-48291")
    assert len(WORLD.crm_activities) == 1


def test_avatar_state_mapping() -> None:
    assert avatar_state_for_running() == "working"
    assert avatar_state_for_outcome(DecisionOutcome.EXECUTE) == "proud"
    assert avatar_state_for_outcome(DecisionOutcome.REVIEW) == "confused"
    assert avatar_state_for_outcome(DecisionOutcome.FAIL) == "scared"
