"""Adapter factory / registry tests — no production endpoint wiring."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.db.session import get_engine, get_session_factory
from app.models.enums import ConnectorType, DecisionOutcome, EnvironmentStatus
from app.models.orm import ConnectorORM, CustomerORM, EnvironmentORM
from app.services.adapters import UnknownAdapterError, build_adapters
from app.services.job_store import InMemoryJobStore
from app.services.policy_review.orchestrator import PolicyReviewOrchestrator
from app.services.seed_demo_environment import DEMO_CUSTOMER_REF, DEMO_ENVIRONMENT_NAME
from integrations.crm.simulated import SimulatedCRMAdapter
from integrations.email.simulated import SimulatedEmailAdapter
from integrations.legacy.simulated import SimulatedLegacyAdapter
from integrations.portal.simulated import SimulatedPortalAdapter
from integrations.simulated_world import WORLD


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _customers_ready() -> bool:
    if not _db_available():
        return False
    try:
        session = get_session_factory()()
        try:
            session.execute(text("SELECT 1 FROM customers LIMIT 1"))
            return True
        finally:
            session.close()
    except Exception:
        return False


pytestmark_db = pytest.mark.skipif(
    not _customers_ready(),
    reason="customers schema not available",
)


def _delete_customer(customer_id) -> None:
    session = get_session_factory()()
    try:
        cust = session.get(CustomerORM, customer_id)
        if cust is not None:
            session.delete(cust)
            session.commit()
    finally:
        session.close()


@pytestmark_db
def test_build_adapters_demo_environment_all_simulated() -> None:
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
        assert env is not None, "Demo Environment seed missing — run seed_demo_environment"
        env_id = env.id
    finally:
        session.close()

    bundle = build_adapters(env_id)
    assert isinstance(bundle.crm, SimulatedCRMAdapter)
    assert isinstance(bundle.legacy, SimulatedLegacyAdapter)
    assert isinstance(bundle.email, SimulatedEmailAdapter)
    assert isinstance(bundle.portal, SimulatedPortalAdapter)


@pytestmark_db
def test_build_adapters_missing_adapter_key_defaults_simulated() -> None:
    customer_id = uuid4()
    env_id = uuid4()
    session = get_session_factory()()
    try:
        customer = CustomerORM(id=customer_id, name=f"Factory Cust {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        env = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Factory Env {env_id.hex[:8]}",
            status=EnvironmentStatus.DRAFT.value,
        )
        session.add(env)
        session.flush()
        for ctype in ConnectorType:
            session.add(
                ConnectorORM(
                    id=uuid4(),
                    environment=env,
                    connector_type=ctype.value,
                    name=ctype.value,
                    config={},  # no "adapter" key
                )
            )
        session.commit()
    finally:
        session.close()

    try:
        bundle = build_adapters(env_id)
        assert isinstance(bundle.crm, SimulatedCRMAdapter)
        assert isinstance(bundle.legacy, SimulatedLegacyAdapter)
        assert isinstance(bundle.email, SimulatedEmailAdapter)
        assert isinstance(bundle.portal, SimulatedPortalAdapter)
    finally:
        _delete_customer(customer_id)


@pytestmark_db
def test_build_adapters_environment_without_connectors_falls_back() -> None:
    customer_id = uuid4()
    env_id = uuid4()
    session = get_session_factory()()
    try:
        customer = CustomerORM(id=customer_id, name=f"Empty Env Cust {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        session.add(
            EnvironmentORM(
                id=env_id,
                customer=customer,
                name=f"Empty Env {env_id.hex[:8]}",
                status=EnvironmentStatus.DRAFT.value,
            )
        )
        session.commit()
    finally:
        session.close()

    try:
        bundle = build_adapters(env_id)
        assert isinstance(bundle.crm, SimulatedCRMAdapter)
        assert isinstance(bundle.legacy, SimulatedLegacyAdapter)
        assert isinstance(bundle.email, SimulatedEmailAdapter)
        assert isinstance(bundle.portal, SimulatedPortalAdapter)
    finally:
        _delete_customer(customer_id)


@pytestmark_db
def test_build_adapters_unknown_adapter_raises() -> None:
    customer_id = uuid4()
    env_id = uuid4()
    session = get_session_factory()()
    try:
        customer = CustomerORM(id=customer_id, name=f"Unknown Adpt {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        env = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Unknown Env {env_id.hex[:8]}",
            status=EnvironmentStatus.DRAFT.value,
        )
        session.add(env)
        session.flush()
        session.add(
            ConnectorORM(
                id=uuid4(),
                environment=env,
                connector_type=ConnectorType.CRM.value,
                name="crm",
                config={"adapter": "not-a-real-adapter"},
            )
        )
        session.commit()
    finally:
        session.close()

    try:
        with pytest.raises(UnknownAdapterError, match="not-a-real-adapter"):
            build_adapters(env_id)
    finally:
        _delete_customer(customer_id)


def test_build_adapters_none_environment_id_simulated() -> None:
    bundle = build_adapters(None)
    assert isinstance(bundle.crm, SimulatedCRMAdapter)
    assert isinstance(bundle.legacy, SimulatedLegacyAdapter)
    assert isinstance(bundle.email, SimulatedEmailAdapter)
    assert isinstance(bundle.portal, SimulatedPortalAdapter)


def test_orchestrator_without_injection_regression() -> None:
    WORLD.reset()
    store = InMemoryJobStore()
    orch = PolicyReviewOrchestrator(store=store, skip_interpretation=True)
    assert isinstance(orch.crm, SimulatedCRMAdapter)
    assert isinstance(orch.legacy, SimulatedLegacyAdapter)
    assert isinstance(orch.email, SimulatedEmailAdapter)
    assert isinstance(orch.portal, SimulatedPortalAdapter)

    review = orch.run_from_message("Revisa la póliza POL-2831")
    execute = orch.run_from_message("Revisa la póliza POL-48291")
    fail = orch.run_from_message("Revisa la póliza POL-77102")
    assert review["decision"] == DecisionOutcome.REVIEW.value
    assert execute["decision"] == DecisionOutcome.EXECUTE.value
    assert fail["decision"] == DecisionOutcome.FAIL.value
    WORLD.reset()


def test_orchestrator_with_injected_adapters_same_decisions() -> None:
    WORLD.reset()
    store = InMemoryJobStore()
    bundle = build_adapters(None, world=WORLD)
    orch = PolicyReviewOrchestrator(
        store=store,
        skip_interpretation=True,
        world=WORLD,
        crm=bundle.crm,
        legacy=bundle.legacy,
        email=bundle.email,
        portal=bundle.portal,
    )
    assert orch.run_from_message("Revisa la póliza POL-2831")["decision"] == DecisionOutcome.REVIEW.value
    assert orch.run_from_message("Revisa la póliza POL-48291")["decision"] == DecisionOutcome.EXECUTE.value
    assert orch.run_from_message("Revisa la póliza POL-77102")["decision"] == DecisionOutcome.FAIL.value
    WORLD.reset()
