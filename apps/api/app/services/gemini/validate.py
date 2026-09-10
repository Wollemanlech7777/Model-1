"""Validate Gemini JSON against schema and context-pack facts."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from ai.schemas.presentation_state import PresentationStateSchema

_POLICY_RE = re.compile(r"\bPOL-\d+\b", re.IGNORECASE)
_STATUS_RE = re.compile(r"\b(ACTIVE|CANCELLED|PENDING|EXPIRED)\b", re.IGNORECASE)


class InterpretationValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def parse_and_validate_interpretation(
    raw: str | dict[str, Any],
    context_pack: dict[str, Any],
) -> PresentationStateSchema:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = _strip_fence(text)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InterpretationValidationError(f"invalid_json:{exc}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise InterpretationValidationError("invalid_json:not_an_object")

    try:
        model = PresentationStateSchema.model_validate(payload)
    except ValidationError as exc:
        raise InterpretationValidationError(f"schema_validation:{exc}") from exc

    _assert_no_invented_facts(model, context_pack)
    return model


def _strip_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _assert_no_invented_facts(model: PresentationStateSchema, context_pack: dict[str, Any]) -> None:
    known_policies: set[str] = set()
    policy_id = context_pack.get("policy_id")
    if policy_id:
        known_policies.add(str(policy_id).upper())

    known_statuses: set[str] = set()
    sources = context_pack.get("sources") or {}
    for value in sources.values():
        if value is not None:
            known_statuses.add(str(value).upper())

    blob = " ".join(
        [model.summary, model.explanation, model.reason, str(context_pack.get("decision") or "")]
    )

    for match in _POLICY_RE.findall(blob):
        if match.upper() not in known_policies:
            raise InterpretationValidationError(f"invented_policy_id:{match}")

    # Status tokens in the narrative must appear in observed sources when sources exist.
    if known_statuses:
        for match in _STATUS_RE.findall(model.summary + " " + model.explanation):
            if match.upper() not in known_statuses:
                # Allow mentioning decision labels indirectly only if status truly unseen —
                # reject invented operational statuses.
                raise InterpretationValidationError(f"invented_status:{match}")
