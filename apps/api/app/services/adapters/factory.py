"""Build integration adapters from Environment connectors (factory + registry)."""

from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.enums import ConnectorType
from app.models.orm import ConnectorORM, EnvironmentORM
from app.services.adapters.bundle import AdapterBundle
from integrations.crm.simulated import SimulatedCRMAdapter
from integrations.email.simulated import SimulatedEmailAdapter
from integrations.legacy.simulated import SimulatedLegacyAdapter
from integrations.portal.real import RealPortalAdapter
from integrations.portal.simulated import SimulatedPortalAdapter
from integrations.simulated_world import WORLD, SimulatedWorld

AdapterFactory = Callable[[dict[str, Any], SimulatedWorld], Any]

# (connector_type, adapter_key) → factory(config, world) -> adapter instance
ADAPTER_REGISTRY: dict[tuple[str, str], AdapterFactory] = {
    ("crm", "simulated"): lambda _config, world: SimulatedCRMAdapter(world),
    ("legacy", "simulated"): lambda _config, world: SimulatedLegacyAdapter(world),
    ("email", "simulated"): lambda _config, world: SimulatedEmailAdapter(world),
    ("portal", "simulated"): lambda _config, world: SimulatedPortalAdapter(world),
    ("portal", "real"): lambda config, _world: RealPortalAdapter(config),
}

_REQUIRED_TYPES: tuple[str, ...] = (
    ConnectorType.CRM.value,
    ConnectorType.LEGACY.value,
    ConnectorType.EMAIL.value,
    ConnectorType.PORTAL.value,
)


class UnknownAdapterError(ValueError):
    """Raised when a connector.config adapter key is not registered."""


def _simulated_bundle(world: SimulatedWorld) -> AdapterBundle:
    return AdapterBundle(
        crm=SimulatedCRMAdapter(world),
        legacy=SimulatedLegacyAdapter(world),
        email=SimulatedEmailAdapter(world),
        portal=SimulatedPortalAdapter(world),
    )


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def build_adapters(
    environment_id: str | UUID | None = None,
    *,
    world: SimulatedWorld | None = None,
) -> AdapterBundle:
    """Resolve adapters for an environment; default / missing → all simulated."""
    demo_world = world or WORLD
    if environment_id is None:
        return _simulated_bundle(demo_world)

    try:
        env_uuid = _as_uuid(environment_id)
    except (ValueError, TypeError):
        return _simulated_bundle(demo_world)

    session = get_session_factory()()
    try:
        environment = session.get(EnvironmentORM, env_uuid)
        if environment is None:
            return _simulated_bundle(demo_world)

        connectors = session.scalars(
            select(ConnectorORM).where(ConnectorORM.environment_id == env_uuid)
        ).all()
        if not connectors:
            return _simulated_bundle(demo_world)

        by_type: dict[str, ConnectorORM] = {c.connector_type: c for c in connectors}
        built: dict[str, Any] = {}

        for ctype in _REQUIRED_TYPES:
            row = by_type.get(ctype)
            if row is None:
                key = "simulated"
                config: dict[str, Any] = {}
            else:
                config = dict(row.config or {})
                key = str(config.get("adapter") or "simulated")

            factory = ADAPTER_REGISTRY.get((ctype, key))
            if factory is None:
                raise UnknownAdapterError(
                    f"Unknown adapter '{key}' for connector_type '{ctype}'. "
                    f"Registered keys for this type: "
                    f"{sorted({k for (t, k) in ADAPTER_REGISTRY if t == ctype}) or 'none'}"
                )
            built[ctype] = factory(config, demo_world)

        return AdapterBundle(
            crm=built[ConnectorType.CRM.value],
            legacy=built[ConnectorType.LEGACY.value],
            email=built[ConnectorType.EMAIL.value],
            portal=built[ConnectorType.PORTAL.value],
        )
    finally:
        session.close()
