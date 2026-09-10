"""Build DecisionContext from normalized multi-source policy statuses."""

from __future__ import annotations

from typing import Any

from app.services.decision.types import DecisionContext, FactConflict, IntegrationFailure


def normalize_status(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def build_decision_context(
    *,
    policy_id: str,
    source_statuses: dict[str, str | None],
    integration_failures: list[IntegrationFailure],
) -> DecisionContext:
    """Compare successful source statuses; any disagreement becomes a conflict."""

    present = {
        source: normalize_status(status)
        for source, status in source_statuses.items()
        if normalize_status(status) is not None
    }

    conflicts: list[FactConflict] = []
    unique_values = sorted(set(present.values()))
    if len(unique_values) > 1:
        # Pairwise conflicts against a stable baseline (first sorted source).
        baseline_source = sorted(present.keys())[0]
        baseline_value = present[baseline_source]
        for source, value in sorted(present.items()):
            if source == baseline_source:
                continue
            if value != baseline_value:
                conflicts.append(
                    FactConflict(
                        field="policy_status",
                        left_source=baseline_source,
                        left_value=baseline_value,
                        right_source=source,
                        right_value=value,
                    )
                )

    facts: dict[str, Any] = {
        "policy_id": policy_id,
        "source_statuses": present,
    }

    return DecisionContext(
        facts=facts,
        conflicts=conflicts,
        integration_failures=list(integration_failures),
        missing_required_fields=[],
        ambiguous_matches=[],
    )
