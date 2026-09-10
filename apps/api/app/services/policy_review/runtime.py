"""Construct a PolicyReviewOrchestrator bound to an Environment's adapters."""

from __future__ import annotations

from uuid import UUID

from app.db.session import get_session_factory
from app.models.orm import EnvironmentORM
from app.services.adapters import build_adapters
from app.services.gemini.client import GeminiClient
from app.services.job_store import JobStore
from app.services.policy_review.demo_environment import get_demo_environment_id
from app.services.policy_review.orchestrator import PolicyReviewOrchestrator
from integrations.simulated_world import SimulatedWorld


def _persistable_environment_id(value: str | None) -> str | None:
    """Return value only if it references an existing environments row (safe FK)."""
    if not value:
        return None
    try:
        uid = UUID(str(value))
    except (ValueError, TypeError):
        return None
    session = get_session_factory()()
    try:
        row = session.get(EnvironmentORM, uid)
        return str(row.id) if row is not None else None
    except Exception:
        return None
    finally:
        session.close()


def create_policy_review_orchestrator(
    *,
    environment_id: str | None = None,
    store: JobStore | None = None,
    world: SimulatedWorld | None = None,
    gemini_client: GeminiClient | None = None,
    skip_interpretation: bool = False,
) -> PolicyReviewOrchestrator:
    """Resolve environment → adapters → orchestrator.

    When ``environment_id`` is omitted, use the seeded Demo Environment.
    If that is unavailable, ``build_adapters(None)`` yields simulated adapters
    (same behavior as before Phase 3). Persistable ``environment_id`` is only
    set when the environment row exists.
    """
    resolved_id = environment_id if environment_id is not None else get_demo_environment_id()
    bundle = build_adapters(resolved_id, world=world)
    persist_env_id = _persistable_environment_id(resolved_id)
    return PolicyReviewOrchestrator(
        world=world,
        store=store,
        gemini_client=gemini_client,
        skip_interpretation=skip_interpretation,
        environment_id=persist_env_id,
        crm=bundle.crm,
        legacy=bundle.legacy,
        email=bundle.email,
        portal=bundle.portal,
    )
