from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import (
    REQUEST_ID_HEADER,
    get_request_id,
    log_unhandled_exception,
    resolve_request_id,
    safe_internal_error_response,
    sanitize_log_text,
)
from app.middleware import PolicyReviewRateLimitMiddleware
from app.routes.crm import router as crm_router
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app.api")

app = FastAPI(title=settings.app_name, version="0.2.0")

# Last added = outermost. Rate limit first, then CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", REQUEST_ID_HEADER],
    expose_headers=[REQUEST_ID_HEADER],
)
app.add_middleware(PolicyReviewRateLimitMiddleware)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(crm_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = resolve_request_id(request)
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = get_request_id(request)
    detail = exc.detail
    if isinstance(detail, str):
        detail = sanitize_log_text(detail, max_len=300)
    headers = {REQUEST_ID_HEADER: request_id}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "request_id": request_id},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = get_request_id(request)
    # Keep FastAPI-compatible shape; do not echo raw body (may contain secrets).
    safe_errors = []
    for err in exc.errors():
        safe_errors.append(
            {
                "type": err.get("type"),
                "loc": err.get("loc"),
                "msg": sanitize_log_text(err.get("msg"), max_len=200),
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors, "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id(request)
    log_unhandled_exception(request, exc)
    return safe_internal_error_response(request_id=request_id)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "policy_review_v1",
        "workflow": "policy_review",
        "environment": settings.environment,
    }
