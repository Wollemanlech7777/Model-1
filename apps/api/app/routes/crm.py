from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.job_store import JOB_STORE
from integrations.simulated_world import WORLD

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/activities")
def list_crm_activities() -> dict:
    """List persisted CRM activities (PostgreSQL source of truth)."""
    return {"activities": JOB_STORE.list_crm_activities()}


@router.post("/reset-demo")
def reset_demo_world() -> dict:
    """Reset simulated systems + clear persisted CRM activities (local demo only)."""
    if not get_settings().demo_reset_allowed():
        # Hide endpoint in production until auth is in place.
        raise HTTPException(status_code=404, detail="not found")
    WORLD.reset()
    JOB_STORE.clear_crm_activities()
    return {"ok": True, "activities": 0}
