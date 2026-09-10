"""Deterministic decision engine skeleton.

Authority rules (v0 — workflow-agnostic):
1. Auth / hard integration failures that block writes → FAIL
2. Missing required fields → REVIEW (or FAIL if configured later)
3. Source conflicts → REVIEW
4. Ambiguous matches below confidence → REVIEW
5. Otherwise → EXECUTE (write allowed)

No demo-specific workflow rules are encoded here yet.
"""

from __future__ import annotations

from app.models.enums import DecisionOutcome
from app.services.decision.types import DecisionContext, DecisionResult

DEFAULT_MATCH_CONFIDENCE_THRESHOLD = 0.85


class DecisionEngine:
    def __init__(self, match_confidence_threshold: float = DEFAULT_MATCH_CONFIDENCE_THRESHOLD) -> None:
        self.match_confidence_threshold = match_confidence_threshold

    def decide(self, context: DecisionContext) -> DecisionResult:
        reasons: list[str] = []

        blocking_failures = [f for f in context.integration_failures if f.blocks_writes]
        if blocking_failures:
            for failure in blocking_failures:
                code = failure.error_code or "error"
                reasons.append(
                    f"integration_failure:{failure.connector}:{code}:{failure.message}"
                )
            return DecisionResult(
                outcome=DecisionOutcome.FAIL,
                allow_external_write=False,
                reasons=reasons,
                evidence_ids=list(context.evidence_ids),
                facts=dict(context.facts),
            )

        if context.missing_required_fields:
            for field_name in context.missing_required_fields:
                reasons.append(f"missing_required_field:{field_name}")
            return DecisionResult(
                outcome=DecisionOutcome.REVIEW,
                allow_external_write=False,
                reasons=reasons,
                evidence_ids=list(context.evidence_ids),
                facts=dict(context.facts),
            )

        if context.conflicts:
            for conflict in context.conflicts:
                reasons.append(
                    "conflict:"
                    f"{conflict.field}:"
                    f"{conflict.left_source}={conflict.left_value!r}:"
                    f"{conflict.right_source}={conflict.right_value!r}"
                )
            return DecisionResult(
                outcome=DecisionOutcome.REVIEW,
                allow_external_write=False,
                reasons=reasons,
                evidence_ids=list(context.evidence_ids),
                facts=dict(context.facts),
            )

        for match in context.ambiguous_matches:
            if match.candidate_count != 1 or match.confidence < self.match_confidence_threshold:
                reasons.append(
                    "ambiguous_match:"
                    f"{match.entity}:candidates={match.candidate_count}:"
                    f"confidence={match.confidence:.2f}"
                )
                if match.detail:
                    reasons.append(f"ambiguous_match_detail:{match.detail}")
                return DecisionResult(
                    outcome=DecisionOutcome.REVIEW,
                    allow_external_write=False,
                    reasons=reasons,
                    evidence_ids=list(context.evidence_ids),
                    facts=dict(context.facts),
                )

        if context.allow_write_signal is False:
            reasons.append("allow_write_signal:false")
            return DecisionResult(
                outcome=DecisionOutcome.REVIEW,
                allow_external_write=False,
                reasons=reasons,
                evidence_ids=list(context.evidence_ids),
                facts=dict(context.facts),
            )

        reasons.append("checks_passed")
        return DecisionResult(
            outcome=DecisionOutcome.EXECUTE,
            allow_external_write=True,
            reasons=reasons,
            evidence_ids=list(context.evidence_ids),
            facts=dict(context.facts),
        )


def fallback_expression_for_outcome(outcome: DecisionOutcome) -> str:
    """Deterministic avatar fallback when Claude is unavailable."""
    return {
        DecisionOutcome.EXECUTE: "proud",
        DecisionOutcome.REVIEW: "confused",
        DecisionOutcome.FAIL: "scared",
    }[outcome]
