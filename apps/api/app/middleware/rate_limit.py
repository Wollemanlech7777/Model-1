"""Simple in-process rate limiting (no external infrastructure)."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings
from app.errors import client_identity


class _SlidingWindowCounter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_seconds
            # Drop expired timestamps in place.
            keep = [ts for ts in bucket if ts >= cutoff]
            if len(keep) >= limit:
                self._hits[key] = keep
                return False
            keep.append(now)
            self._hits[key] = keep
            return True


_POLICY_REVIEW_COUNTER = _SlidingWindowCounter()


class PolicyReviewRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limit POST /jobs/policy-review only. Disabled when limit <= 0."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "POST" and request.url.path.rstrip("/") == "/jobs/policy-review":
            settings = get_settings()
            limit = int(settings.rate_limit_policy_review_per_minute)
            if limit > 0:
                key = f"policy-review:{client_identity(request)}"
                if not _POLICY_REVIEW_COUNTER.allow(key, limit=limit, window_seconds=60.0):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "rate limit exceeded"},
                        headers={"Retry-After": "60"},
                    )
        return await call_next(request)


def reset_rate_limit_state_for_tests() -> None:
    """Clear in-memory counters (tests only)."""
    with _POLICY_REVIEW_COUNTER._lock:
        _POLICY_REVIEW_COUNTER._hits.clear()
