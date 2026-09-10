"""Deterministic presentation fallback when Gemini is unavailable or invalid."""

from __future__ import annotations

from typing import Any

from app.models.enums import DecisionOutcome
from app.services.gemini.chat_copy import (
    describe_conflict,
    describe_execute_success,
    describe_what_happened,
    describe_why_no_crm_write,
)
from app.services.policy_review.avatar_map import avatar_state_for_outcome


def fallback_interpretation(job: dict[str, Any]) -> dict[str, Any]:
    decision = str(job.get("decision") or DecisionOutcome.FAIL.value).lower()
    try:
        outcome = DecisionOutcome(decision)
    except ValueError:
        outcome = DecisionOutcome.FAIL

    animation = avatar_state_for_outcome(outcome)
    policy_id = job.get("policy_id") or "unknown"
    sources = job.get("sources") or {}

    if outcome == DecisionOutcome.REVIEW:
        summary = f"Encontré información contradictoria sobre {policy_id}. No hice cambios."
        explanation = (
            describe_conflict(sources)
            + " Por eso no actualicé el CRM y dejé el caso en revisión manual."
        )
        semantic_state = "ambiguous"
        reason = "conflicting_source_status"
        severity = "medium"
    elif outcome == DecisionOutcome.EXECUTE:
        summary = describe_execute_success(job)
        explanation = describe_what_happened(job)
        semantic_state = "success"
        reason = "sources_agree"
        severity = "low"
    else:
        summary = (
            f"No pude completar la revisión de {policy_id} porque el CRM rechazó "
            "la consulta por un error de autorización (401). No realicé cambios."
        )
        explanation = describe_what_happened(job)
        semantic_state = "failed"
        reason = "integration_failure"
        severity = "high"

    return {
        "summary": summary,
        "explanation": explanation,
        "semantic_state": semantic_state,
        "severity": severity,
        "reason": reason,
        "expression": animation,
        "animation": animation,
        "source": "fallback",
    }
