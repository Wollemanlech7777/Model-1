"""Idempotent demo Customer / Environment / Connectors seed.

Does not touch jobs, crm_activities, or policy_review.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.enums import ConnectorStatus, ConnectorType, EnvironmentStatus
from app.models.orm import ConnectorORM, CustomerORM, EnvironmentORM

DEMO_CUSTOMER_NAME = "Demo Customer"
DEMO_CUSTOMER_REF = "demo:customer"
DEMO_ENVIRONMENT_NAME = "Demo Environment"
DEMO_CONNECTOR_CONFIG: dict[str, Any] = {"adapter": "simulated", "world": "default"}
DEMO_CONNECTOR_TYPES: tuple[ConnectorType, ...] = (
    ConnectorType.CRM,
    ConnectorType.LEGACY,
    ConnectorType.EMAIL,
    ConnectorType.PORTAL,
)


def seed_demo_environment() -> dict[str, Any]:
    """Ensure demo customer + environment + 4 simulated connectors exist."""
    session = get_session_factory()()
    try:
        customer = session.scalar(
            select(CustomerORM).where(CustomerORM.external_ref == DEMO_CUSTOMER_REF)
        )
        if customer is None:
            customer = CustomerORM(
                id=uuid4(),
                name=DEMO_CUSTOMER_NAME,
                external_ref=DEMO_CUSTOMER_REF,
            )
            session.add(customer)
            session.flush()

        environment = session.scalar(
            select(EnvironmentORM).where(
                EnvironmentORM.customer_id == customer.id,
                EnvironmentORM.name == DEMO_ENVIRONMENT_NAME,
            )
        )
        if environment is None:
            environment = EnvironmentORM(
                id=uuid4(),
                customer=customer,
                name=DEMO_ENVIRONMENT_NAME,
                status=EnvironmentStatus.READY.value,
                description="Seeded demo environment for Site Companion",
            )
            session.add(environment)
            session.flush()

        connectors: list[ConnectorORM] = []
        for ctype in DEMO_CONNECTOR_TYPES:
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
                    name=f"Demo {ctype.value.upper()}",
                    status=ConnectorStatus.CONNECTED.value,
                    config=dict(DEMO_CONNECTOR_CONFIG),
                )
                session.add(row)
                session.flush()
            else:
                row.config = dict(DEMO_CONNECTOR_CONFIG)
                row.status = ConnectorStatus.CONNECTED.value
            connectors.append(row)

        session.commit()
        return {
            "customer_id": str(customer.id),
            "environment_id": str(environment.id),
            "connector_ids": {c.connector_type: str(c.id) for c in connectors},
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    result = seed_demo_environment()
    print(result)
