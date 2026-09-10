"""API hardening helpers: safe errors, request identity, redaction."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.api")

REQUEST_ID_HEADER = "X-Request-ID"

_SECRET_PATTERNS = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|authorization|bearer\s+\S+|postgresql\+[^\s]+|"
    r"database_url\s*[:=]\s*\S+|client_secret\s*[:=]\s*\S+)"
)


def client_identity(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def resolve_request_id(request: Request) -> str:
    """Reuse inbound X-Request-ID when present; otherwise generate one."""
    incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if incoming and len(incoming) <= 128 and "\n" not in incoming and "\r" not in incoming:
        return incoming
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str) and existing:
        return existing
    return str(uuid4())


def get_request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return resolve_request_id(request)


def sanitize_log_text(value: Any, *, max_len: int = 200) -> str:
    text = str(value)
    text = _SECRET_PATTERNS.sub("[REDACTED]", text)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def safe_internal_error_response(*, request_id: str | None = None) -> JSONResponse:
    content: dict[str, str] = {"detail": "internal server error"}
    headers = {}
    if request_id:
        content["request_id"] = request_id
        headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(status_code=500, content=content, headers=headers)


def log_unhandled_exception(request: Request, exc: BaseException) -> None:
    logger.exception(
        "unhandled_error request_id=%s method=%s path=%s error_type=%s error=%s",
        get_request_id(request),
        request.method,
        request.url.path,
        type(exc).__name__,
        sanitize_log_text(exc),
    )
