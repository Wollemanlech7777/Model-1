from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db.session import get_session_factory

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: process is up. No DB or external calls."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    """Readiness: app can serve traffic (DB reachable). No workflow execution."""
    session = get_session_factory()()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    finally:
        session.close()
    return {"status": "ready"}
