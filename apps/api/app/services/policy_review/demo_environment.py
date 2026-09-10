"""Resolve the seeded Demo Environment id (read-only)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.orm import CustomerORM, EnvironmentORM
from app.services.seed_demo_environment import DEMO_CUSTOMER_REF, DEMO_ENVIRONMENT_NAME


@lru_cache(maxsize=1)
def get_demo_environment_id() -> str | None:
    """Return Demo Environment UUID string, or None if seed is missing / DB down."""
    try:
        session = get_session_factory()()
        try:
            env = session.scalar(
                select(EnvironmentORM)
                .join(CustomerORM, EnvironmentORM.customer_id == CustomerORM.id)
                .where(
                    CustomerORM.external_ref == DEMO_CUSTOMER_REF,
                    EnvironmentORM.name == DEMO_ENVIRONMENT_NAME,
                )
            )
            return str(env.id) if env is not None else None
        finally:
            session.close()
    except Exception:
        return None


def clear_demo_environment_id_cache() -> None:
    get_demo_environment_id.cache_clear()
