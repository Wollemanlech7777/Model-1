"""Customer / Environment / Connector schema tests — do not wipe jobs or CRM."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine, get_session_factory
from app.models.enums import ConnectorType, EnvironmentStatus
from app.models.orm import ConnectorORM, CustomerORM, EnvironmentORM


def _db_available() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _schema_ready() -> bool:
    if not _db_available():
        return False
    try:
        session = get_session_factory()()
        try:
            session.execute(text("SELECT 1 FROM customers LIMIT 1"))
            session.execute(
                text(
                    "SELECT 1 FROM pg_constraint WHERE conname = 'uq_connectors_env_type' LIMIT 1"
                )
            )
            return True
        finally:
            session.close()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _schema_ready(),
    reason="customers schema / uq_connectors_env_type not available (run alembic upgrade)",
)


SIMULATED_CONFIG = {"adapter": "simulated", "world": "default"}


@pytest.fixture
def session_factory():
    return get_session_factory()


def test_create_customer_environment_and_four_connectors(session_factory) -> None:
    session = session_factory()
    customer_id = uuid4()
    env_id = uuid4()
    try:
        customer = CustomerORM(
            id=customer_id,
            name=f"Test Customer {customer_id.hex[:8]}",
            external_ref=f"test:customer:{customer_id}",
        )
        session.add(customer)
        session.flush()

        environment = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Test Env {env_id.hex[:8]}",
            status=EnvironmentStatus.DRAFT.value,
        )
        session.add(environment)
        session.flush()

        for ctype in ConnectorType:
            session.add(
                ConnectorORM(
                    id=uuid4(),
                    environment=environment,
                    connector_type=ctype.value,
                    name=f"{ctype.value}-conn",
                    config=dict(SIMULATED_CONFIG),
                )
            )
        session.commit()

        loaded_env = session.get(EnvironmentORM, env_id)
        assert loaded_env is not None
        assert loaded_env.customer_id == customer_id
        connectors = session.scalars(
            select(ConnectorORM).where(ConnectorORM.environment_id == env_id)
        ).all()
        assert len(connectors) == 4
        assert {c.connector_type for c in connectors} == {c.value for c in ConnectorType}
        assert all(c.config == SIMULATED_CONFIG for c in connectors)
    finally:
        # Cleanup only this customer tree (CASCADE env + connectors). Never jobs/CRM.
        session.rollback()
        cust = session.get(CustomerORM, customer_id)
        if cust is not None:
            session.delete(cust)
            session.commit()
        session.close()


def test_duplicate_connector_type_same_environment_rejected(session_factory) -> None:
    session = session_factory()
    customer_id = uuid4()
    env_id = uuid4()
    try:
        customer = CustomerORM(id=customer_id, name=f"Dup Cust {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        environment = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Dup Env {env_id.hex[:8]}",
            status=EnvironmentStatus.DRAFT.value,
        )
        session.add(environment)
        session.flush()
        session.add(
            ConnectorORM(
                id=uuid4(),
                environment=environment,
                connector_type=ConnectorType.CRM.value,
                name="crm-a",
                config=dict(SIMULATED_CONFIG),
            )
        )
        session.commit()

        session.add(
            ConnectorORM(
                id=uuid4(),
                environment_id=env_id,
                connector_type=ConnectorType.CRM.value,
                name="crm-b",
                config=dict(SIMULATED_CONFIG),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        cust = session.get(CustomerORM, customer_id)
        if cust is not None:
            session.delete(cust)
            session.commit()
        session.close()


def test_same_connector_type_allowed_across_environments(session_factory) -> None:
    session = session_factory()
    customer_id = uuid4()
    env_a = uuid4()
    env_b = uuid4()
    try:
        customer = CustomerORM(id=customer_id, name=f"Multi Env {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        environments = []
        for eid, label in ((env_a, "A"), (env_b, "B")):
            env = EnvironmentORM(
                id=eid,
                customer=customer,
                name=f"Env {label} {eid.hex[:8]}",
                status=EnvironmentStatus.DRAFT.value,
            )
            session.add(env)
            environments.append(env)
        session.flush()
        for env in environments:
            session.add(
                ConnectorORM(
                    id=uuid4(),
                    environment=env,
                    connector_type=ConnectorType.EMAIL.value,
                    name="email",
                    config=dict(SIMULATED_CONFIG),
                )
            )
        session.commit()

        rows = session.scalars(
            select(ConnectorORM).where(
                ConnectorORM.environment_id.in_([env_a, env_b]),
                ConnectorORM.connector_type == ConnectorType.EMAIL.value,
            )
        ).all()
        assert len(rows) == 2
    finally:
        cust = session.get(CustomerORM, customer_id)
        if cust is not None:
            session.delete(cust)
            session.commit()
        session.close()
