"""Idempotent CyberNotes sandbox Customer / Environment / Connectors seed.

Does not touch Demo Environment, jobs, crm_activities, or policy_review.
Credentials stay in env vars (CYBERNOTES_CLIENT_ID / SECRET) — never stored here.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.enums import ConnectorStatus, ConnectorType, EnvironmentStatus
from app.models.orm import ConnectorORM, CustomerORM, EnvironmentORM

SANDBOX_CUSTOMER_NAME = "CyberNotes Sandbox Customer"
SANDBOX_CUSTOMER_REF = "cybernotes:sandbox"
SANDBOX_ENVIRONMENT_NAME = "CyberNotes Sandbox"
# Stable ID shared with apps/web POLICY_REVIEW_ENVIRONMENT_ID — never randomize.
SANDBOX_ENVIRONMENT_ID = UUID("2f46645e-35ff-4865-b7ed-88285c96d25a")

SIMULATED_CONNECTOR_CONFIG: dict[str, Any] = {"adapter": "simulated", "world": "default"}
PORTAL_REAL_CONFIG: dict[str, Any] = {
    "adapter": "real",
    "base_url": "https://api.cybernotes.it/mtpl/v1",
    "policy_id_map": {
        "POL-48291": "pol-5fa50ab9",
    },
}

_CONNECTOR_SPECS: tuple[tuple[ConnectorType, dict[str, Any], str], ...] = (
    (ConnectorType.CRM, SIMULATED_CONNECTOR_CONFIG, "Sandbox CRM"),
    (ConnectorType.LEGACY, SIMULATED_CONNECTOR_CONFIG, "Sandbox Legacy"),
    (ConnectorType.EMAIL, SIMULATED_CONNECTOR_CONFIG, "Sandbox Email"),
    (ConnectorType.PORTAL, PORTAL_REAL_CONFIG, "Sandbox Portal (CyberNotes)"),
)


def seed_cybernotes_sandbox() -> dict[str, Any]:
    """Ensure CyberNotes sandbox customer + environment + connectors exist."""
    session = get_session_factory()()
    try:
        customer = session.scalar(
            select(CustomerORM).where(CustomerORM.external_ref == SANDBOX_CUSTOMER_REF)
        )
        customer_created = False
        if customer is None:
            customer = CustomerORM(
                id=uuid4(),
                name=SANDBOX_CUSTOMER_NAME,
                external_ref=SANDBOX_CUSTOMER_REF,
            )
            session.add(customer)
            session.flush()
            customer_created = True

        # Prefer fixed UUID (UI contract); fall back to name so re-seeds stay idempotent.
        environment = session.get(EnvironmentORM, SANDBOX_ENVIRONMENT_ID)
        if environment is None:
            environment = session.scalar(
                select(EnvironmentORM).where(
                    EnvironmentORM.customer_id == customer.id,
                    EnvironmentORM.name == SANDBOX_ENVIRONMENT_NAME,
                )
            )
        environment_created = False
        if environment is None:
            environment = EnvironmentORM(
                id=SANDBOX_ENVIRONMENT_ID,
                customer=customer,
                name=SANDBOX_ENVIRONMENT_NAME,
                status=EnvironmentStatus.READY.value,
                description="Sandbox environment for CyberNotes MTPL real portal adapter",
            )
            session.add(environment)
            session.flush()
            environment_created = True

        connectors_out: dict[str, Any] = {}
        for ctype, config, name in _CONNECTOR_SPECS:
            desired = deepcopy(config)
            row = session.scalar(
                select(ConnectorORM).where(
                    ConnectorORM.environment_id == environment.id,
                    ConnectorORM.connector_type == ctype.value,
                )
            )
            if row is None:
                row = ConnectorORM(
                    id=uuid4(),
                    environment=environment,
                    connector_type=ctype.value,
                    name=name,
                    status=ConnectorStatus.CONNECTED.value,
                    config=desired,
                )
                session.add(row)
                session.flush()
                action = "created"
            else:
                row.name = name
                row.config = desired
                row.status = ConnectorStatus.CONNECTED.value
                action = "reused"
            connectors_out[ctype.value] = {
                "id": str(row.id),
                "action": action,
                "adapter": desired.get("adapter"),
                "config": desired,
            }

        session.commit()
        return {
            "customer_id": str(customer.id),
            "customer_external_ref": SANDBOX_CUSTOMER_REF,
            "customer_action": "created" if customer_created else "reused",
            "environment_id": str(environment.id),
            "environment_name": SANDBOX_ENVIRONMENT_NAME,
            "environment_action": "created" if environment_created else "reused",
            "connectors": connectors_out,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    result = seed_cybernotes_sandbox()
    # Never print secrets (none are stored in connector config).
    print(
        {
            "customer_id": result["customer_id"],
            "customer_action": result["customer_action"],
            "environment_id": result["environment_id"],
            "environment_action": result["environment_action"],
            "connectors": {
                k: {
                    "id": v["id"],
                    "action": v["action"],
                    "adapter": v["adapter"],
                    "config": v["config"],
                }
                for k, v in result["connectors"].items()
            },
        }
    )
