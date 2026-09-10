"""Structured Gemini interpretation output — presentation only, never write authority."""

from typing import Literal

from pydantic import BaseModel, Field

# Animations present in apps/web/src/assets/grok-bot.avatar.json
ALLOWED_ANIMATIONS = Literal[
    "sleeping",
    "waking",
    "idle",
    "listening",
    "thinking",
    "searching",
    "working",
    "excited",
    "bored",
    "suspicious",
    "angry",
    "drowsy",
    "happy",
    "curious",
    "confused",
    "surprised",
    "proud",
    "shy",
    "sad",
    "laughing",
    "scared",
    "playful",
    "celebrate",
    "mad",
]

ALLOWED_EXPRESSIONS = ALLOWED_ANIMATIONS  # same vocabulary for this avatar file

ALLOWED_SEMANTIC_STATES = Literal[
    "idle",
    "configuring",
    "running",
    "success",
    "ambiguous",
    "blocked",
    "failed",
]


class PresentationStateSchema(BaseModel):
    """Validated semantic UI / chat interpretation from Gemini."""

    summary: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=4000)
    semantic_state: ALLOWED_SEMANTIC_STATES
    severity: Literal["low", "medium", "high"] = "low"
    reason: str = Field(min_length=1, max_length=255)
    expression: ALLOWED_EXPRESSIONS
    animation: ALLOWED_ANIMATIONS


# Backward-compatible alias
GeminiInterpretationSchema = PresentationStateSchema
