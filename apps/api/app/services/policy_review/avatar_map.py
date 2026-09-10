"""Map job / decision outcomes to avatar animation keys (Grok bot file)."""

from __future__ import annotations

from app.models.enums import DecisionOutcome


def avatar_state_for_running() -> str:
    return "working"


def avatar_state_for_idle() -> str:
    return "idle"


def avatar_state_for_outcome(outcome: DecisionOutcome) -> str:
    return {
        DecisionOutcome.EXECUTE: "proud",
        DecisionOutcome.REVIEW: "confused",
        DecisionOutcome.FAIL: "scared",
    }[outcome]
