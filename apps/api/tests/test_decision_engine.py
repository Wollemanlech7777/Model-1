from uuid import uuid4

from app.models.enums import DecisionOutcome
from app.services.decision import (
    AmbiguousMatch,
    DecisionContext,
    DecisionEngine,
    FactConflict,
    IntegrationFailure,
    fallback_expression_for_outcome,
)


def test_execute_when_checks_pass() -> None:
    engine = DecisionEngine()
    result = engine.decide(DecisionContext(facts={"ok": True}))
    assert result.outcome == DecisionOutcome.EXECUTE
    assert result.allow_external_write is True
    assert "checks_passed" in result.reasons


def test_fail_on_blocking_integration_error() -> None:
    engine = DecisionEngine()
    result = engine.decide(
        DecisionContext(
            integration_failures=[
                IntegrationFailure(
                    connector="crm",
                    error_code="401",
                    message="Unauthorized",
                    blocks_writes=True,
                )
            ]
        )
    )
    assert result.outcome == DecisionOutcome.FAIL
    assert result.allow_external_write is False


def test_review_on_conflict() -> None:
    engine = DecisionEngine()
    result = engine.decide(
        DecisionContext(
            conflicts=[
                FactConflict(
                    field="status",
                    left_source="crm",
                    left_value="ACTIVE",
                    right_source="portal",
                    right_value="CANCELLED",
                )
            ]
        )
    )
    assert result.outcome == DecisionOutcome.REVIEW
    assert result.allow_external_write is False


def test_review_on_missing_fields() -> None:
    engine = DecisionEngine()
    result = engine.decide(DecisionContext(missing_required_fields=["external_id"]))
    assert result.outcome == DecisionOutcome.REVIEW
    assert result.allow_external_write is False


def test_review_on_ambiguous_match() -> None:
    engine = DecisionEngine()
    result = engine.decide(
        DecisionContext(
            ambiguous_matches=[
                AmbiguousMatch(entity="customer", candidate_count=3, confidence=0.4)
            ]
        )
    )
    assert result.outcome == DecisionOutcome.REVIEW
    assert result.allow_external_write is False


def test_evidence_ids_preserved() -> None:
    engine = DecisionEngine()
    eid = uuid4()
    result = engine.decide(DecisionContext(evidence_ids=[eid]))
    assert result.evidence_ids == [eid]


def test_fallback_expressions() -> None:
    assert fallback_expression_for_outcome(DecisionOutcome.EXECUTE) == "proud"
    assert fallback_expression_for_outcome(DecisionOutcome.REVIEW) == "confused"
    assert fallback_expression_for_outcome(DecisionOutcome.FAIL) == "scared"
