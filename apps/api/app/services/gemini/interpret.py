"""Gemini interpretation service — never changes operational decisions."""

from __future__ import annotations

from typing import Any

from app.services.gemini.chat_copy import (
    describe_conflict,
    describe_what_happened,
    describe_why_no_crm_write,
    looks_like_internal_leak,
)
from app.services.gemini.client import (
    ASK_SYSTEM,
    INTERPRET_SYSTEM,
    GeminiClient,
    GeminiClientError,
    build_ask_user_prompt,
    build_interpret_user_prompt,
)
from app.services.gemini.context_pack import build_context_pack
from app.services.gemini.fallback import fallback_interpretation
from app.services.gemini.validate import (
    InterpretationValidationError,
    parse_and_validate_interpretation,
)


def interpret_job(
    job: dict[str, Any],
    *,
    client: GeminiClient | None = None,
) -> dict[str, Any]:
    """Attach presentation interpretation. Decision / writes remain unchanged."""

    context_pack = build_context_pack(job)
    gemini = client or GeminiClient()

    try:
        raw = gemini.generate_json(
            system=INTERPRET_SYSTEM,
            user=build_interpret_user_prompt(context_pack),
        )
        model = parse_and_validate_interpretation(raw, context_pack)
        payload = model.model_dump()
        # Keep chat copy clean even if the model leaks internals.
        if looks_like_internal_leak(payload.get("summary", "")) or looks_like_internal_leak(
            payload.get("explanation", "")
        ):
            return fallback_interpretation(job)
        payload["source"] = "gemini"
        return payload
    except (GeminiClientError, InterpretationValidationError):
        return fallback_interpretation(job)


def apply_interpretation(job: dict[str, Any], interpretation: dict[str, Any]) -> dict[str, Any]:
    """Merge presentation fields without mutating operational authority fields."""

    updated = dict(job)
    updated["interpretation"] = interpretation
    updated["interpretation_source"] = interpretation.get("source", "fallback")
    # Natural language for chat — presentation only
    if interpretation.get("summary"):
        updated["assistant_summary"] = interpretation["summary"]
    # Avatar presentation from validated animation (or fallback animation)
    animation = interpretation.get("animation")
    if animation:
        updated["avatar_state"] = animation
    updated["presentation"] = {
        "semantic_state": interpretation.get("semantic_state"),
        "severity": interpretation.get("severity"),
        "reason": interpretation.get("reason"),
        "expression": interpretation.get("expression"),
        "animation": interpretation.get("animation"),
        "explanation": interpretation.get("explanation"),
    }
    return updated


def answer_job_question(
    job: dict[str, Any],
    question: str,
    *,
    client: GeminiClient | None = None,
) -> dict[str, Any]:
    context_pack = build_context_pack(job)
    # Include prior interpretation if present for continuity
    if job.get("interpretation"):
        context_pack["prior_interpretation"] = job["interpretation"]

    gemini = client or GeminiClient()
    try:
        raw = gemini.generate_json(
            system=ASK_SYSTEM,
            user=build_ask_user_prompt(context_pack, question),
        )
        import json

        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        answer = str(data.get("answer") or "").strip()
        if not answer:
            raise InterpretationValidationError("missing_answer")
        if looks_like_internal_leak(answer):
            return {
                "answer": _deterministic_ask_fallback(job, question),
                "source": "fallback",
            }
        return {"answer": answer, "source": "gemini"}
    except (GeminiClientError, InterpretationValidationError, Exception):
        return {
            "answer": _deterministic_ask_fallback(job, question),
            "source": "fallback",
        }


def _deterministic_ask_fallback(job: dict[str, Any], question: str) -> str:
    q = question.lower()
    decision = str(job.get("decision") or "").lower()
    sources = job.get("sources") or {}

    if "crm" in q and ("no" in q or "por qué" in q or "porque" in q or "actualiz" in q):
        return describe_why_no_crm_write(job)

    if "conflicto" in q or "fuente" in q or "fuentes" in q:
        if decision == "review" and sources:
            return describe_conflict(sources)
        if decision == "fail":
            return (
                "No llegué a comparar todas las fuentes porque el CRM respondió "
                "con un error de autorización (401)."
            )
        if decision == "execute" and sources:
            return (
                "No hubo conflicto: "
                + describe_conflict(sources).replace("mientras que", "y").rstrip(".")
                + "."
            )
        return describe_conflict(sources)

    if "qué pasó" in q or "que paso" in q or "por qué" in q or "porque" in q:
        explanation = (job.get("interpretation") or {}).get("explanation")
        if explanation and not looks_like_internal_leak(explanation):
            return explanation
        return describe_what_happened(job)

    return describe_what_happened(job)
