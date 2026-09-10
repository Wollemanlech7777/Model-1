"""Gemini API client — interpretation only."""

from __future__ import annotations

import concurrent.futures
import json
from typing import Any, Callable

from app.config import get_settings


class GeminiClientError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


GenerateFn = Callable[[str, str], str]


def _sdk_generate(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiClientError("missing_api_key")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiClientError("gemini_sdk_missing") from exc

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system,
    )
    try:
        response = model.generate_content(
            user,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
            request_options={"timeout": settings.gemini_timeout_seconds},
        )
    except Exception as exc:  # noqa: BLE001 — map any SDK/network failure to fallback
        raise GeminiClientError(f"gemini_error:{exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise GeminiClientError("empty_response")
    return text


def _default_generate(system: str, user: str) -> str:
    """Call Gemini with a hard wall-clock timeout.

    SDK request_options timeout is not always honored. Without a hard cutoff,
    /jobs/policy-review can hang and the chat UI freezes after the user message
    with no progress/result.
    """
    settings = get_settings()
    timeout = max(1.0, float(settings.gemini_timeout_seconds))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_sdk_generate, system, user)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise GeminiClientError("gemini_error:timeout") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class GeminiClient:
    def __init__(self, generate_fn: GenerateFn | None = None) -> None:
        self._generate = generate_fn or _default_generate

    def generate_json(self, *, system: str, user: str) -> str:
        settings = get_settings()
        if not settings.gemini_api_key and self._generate is _default_generate:
            raise GeminiClientError("missing_api_key")
        return self._generate(system, user)


INTERPRET_SYSTEM = """You are a presentation layer for Site Companion.
You ONLY interpret facts already computed by the backend.
You MUST return a single JSON object with keys:
summary, explanation, semantic_state, severity, reason, expression, animation.

Rules:
- Never decide EXECUTE, REVIEW, or FAIL — that decision is already fixed in the context.
- Never authorize writes or invent CRM/legacy/email/portal facts.
- Never invent policy IDs or statuses not present in the context pack.
- expression and animation must be one of the avatar animation keys provided.
- semantic_state must be one of: idle, configuring, running, success, ambiguous, blocked, failed.
- severity must be low, medium, or high.
- Write summary/explanation in Spanish, clear for a non-technical stakeholder.
- NEVER include internal codes like decision_not_execute or conflict:policy_status:...
- NEVER dump raw JSON/dicts of sources; describe them in natural language.
"""


ASK_SYSTEM = """You answer follow-up questions about ONE completed Site Companion job.
Use ONLY the provided context pack facts.
If the question cannot be answered from the context, say you do not have that fact.
Do not invent sources, statuses, or actions.
Do not change or re-decide the operational decision.
Reply as JSON: {"answer": "..."} in Spanish.

Presentation rules (critical for the user-facing chat):
- Write clear natural language for a non-technical stakeholder.
- NEVER include internal reason codes such as decision_not_execute, conflict:policy_status, checks_passed.
- NEVER dump raw JSON, Python dicts, or lists of internal reasons.
- You MAY mention external HTTP codes like 401 when they explain a failure.
- Prefer sentences like: "CRM y Legacy indican ACTIVA, mientras Email y Portal indican CANCELADA."
"""


def build_interpret_user_prompt(context_pack: dict[str, Any]) -> str:
    allowed_animations = [
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
    return (
        "Context pack (authoritative facts):\n"
        f"{json.dumps(context_pack, ensure_ascii=False, indent=2)}\n\n"
        f"Allowed expression/animation keys: {allowed_animations}\n"
        "Return only the JSON object."
    )


def build_ask_user_prompt(context_pack: dict[str, Any], question: str) -> str:
    return (
        "Context pack (authoritative facts):\n"
        f"{json.dumps(context_pack, ensure_ascii=False, indent=2)}\n\n"
        f"Question: {question}\n"
        'Return JSON: {"answer": "..."}'
    )
