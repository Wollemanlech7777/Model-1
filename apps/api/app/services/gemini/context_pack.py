"""Build a facts-only context pack for Gemini (no authority)."""

from __future__ import annotations

from typing import Any


def build_context_pack(job: dict[str, Any]) -> dict[str, Any]:
    """Facts already computed by adapters + decision engine."""

    return {
        "job_id": job.get("id"),
        "workflow_key": job.get("workflow_key"),
        "policy_id": job.get("policy_id"),
        "input_message": job.get("input_message"),
        "sources": job.get("sources") or {},
        "normalized_facts": job.get("facts") or {},
        "reasons": job.get("reasons") or [],
        "decision": job.get("decision"),
        "allow_external_write": job.get("allow_external_write"),
        "crm_write": job.get("crm_write") or {},
        "evidence": job.get("evidence") or [],
        "timeline": job.get("timeline") or [],
        "errors": _collect_errors(job),
        "deterministic_assistant_summary": job.get("assistant_summary"),
        "deterministic_avatar_state": job.get("avatar_state"),
    }


def _collect_errors(job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in job.get("evidence") or []:
        for err in item.get("errors") or []:
            errors.append(str(err))
    for event in job.get("timeline") or []:
        if event.get("success") is False:
            errors.append(str(event.get("message")))
    return errors
