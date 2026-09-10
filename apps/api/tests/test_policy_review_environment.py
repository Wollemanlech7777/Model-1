"""Phase 3: Environment → factory → policy_review wiring (no JOB_STORE.reset)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import DecisionOutcome
from app.services.adapters import build_adapters
from app.services.job_store import InMemoryJobStore
from app.services.policy_review.demo_environment import (
    clear_demo_environment_id_cache,
    get_demo_environment_id,
)
from app.services.policy_review.runtime import create_policy_review_orchestrator
from integrations.crm.simulated import SimulatedCRMAdapter
from integrations.email.simulated import SimulatedEmailAdapter
from integrations.legacy.simulated import SimulatedLegacyAdapter
from integrations.portal.simulated import SimulatedPortalAdapter
from integrations.simulated_world import WORLD


@pytest.fixture(autouse=True)
def _reset_world_and_demo_cache() -> None:
    WORLD.reset()
    clear_demo_environment_id_cache()
    yield
    WORLD.reset()
    clear_demo_environment_id_cache()


def test_default_uses_demo_environment_when_available() -> None:
    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")

    orch = create_policy_review_orchestrator(
        store=InMemoryJobStore(),
        skip_interpretation=True,
        world=WORLD,
    )
    assert isinstance(orch.crm, SimulatedCRMAdapter)
    assert isinstance(orch.legacy, SimulatedLegacyAdapter)
    assert isinstance(orch.email, SimulatedEmailAdapter)
    assert isinstance(orch.portal, SimulatedPortalAdapter)

    # Same adapters as build_adapters(demo)
    bundle = build_adapters(demo_id, world=WORLD)
    assert type(orch.crm) is type(bundle.crm)


def test_explicit_demo_environment_id() -> None:
    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")

    orch = create_policy_review_orchestrator(
        environment_id=demo_id,
        store=InMemoryJobStore(),
        skip_interpretation=True,
        world=WORLD,
    )
    assert isinstance(orch.crm, SimulatedCRMAdapter)
    review = orch.run_from_message("Revisa la póliza POL-2831")
    execute = orch.run_from_message("Revisa la póliza POL-48291")
    fail = orch.run_from_message("Revisa la póliza POL-77102")
    assert review["decision"] == DecisionOutcome.REVIEW.value
    assert execute["decision"] == DecisionOutcome.EXECUTE.value
    assert fail["decision"] == DecisionOutcome.FAIL.value
    assert execute["crm_write"]["performed"] is True
    assert review["crm_write"]["performed"] is False
    assert fail["crm_write"]["performed"] is False
    assert len(WORLD.crm_activities) == 1


def test_three_policies_via_runtime_default() -> None:
    orch = create_policy_review_orchestrator(
        store=InMemoryJobStore(),
        skip_interpretation=True,
        world=WORLD,
    )
    review = orch.run_from_message("Revisa la póliza POL-2831")
    execute = orch.run_from_message("Revisa la póliza POL-48291")
    fail = orch.run_from_message("Revisa la póliza POL-77102")
    assert review["decision"] == DecisionOutcome.REVIEW.value
    assert execute["decision"] == DecisionOutcome.EXECUTE.value
    assert fail["decision"] == DecisionOutcome.FAIL.value
    assert execute["crm_write"]["performed"] is True
    assert review["crm_write"]["performed"] is False
    assert fail["crm_write"]["performed"] is False
    assert len(WORLD.crm_activities) == 1

    demo_id = get_demo_environment_id()
    if demo_id is not None:
        assert review.get("environment_id") == demo_id
        assert execute.get("environment_id") == demo_id
        assert fail.get("environment_id") == demo_id


def test_persists_demo_environment_id_without_explicit_arg() -> None:
    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")

    store = InMemoryJobStore()
    orch = create_policy_review_orchestrator(
        store=store,
        skip_interpretation=True,
        world=WORLD,
    )
    assert orch.environment_id == demo_id
    result = orch.run_from_message("Revisa la póliza POL-2831")
    assert result["environment_id"] == demo_id
    loaded = store.get(result["id"])
    assert loaded is not None
    assert loaded["environment_id"] == demo_id


def test_persists_explicit_demo_environment_id() -> None:
    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")

    store = InMemoryJobStore()
    orch = create_policy_review_orchestrator(
        environment_id=demo_id,
        store=store,
        skip_interpretation=True,
        world=WORLD,
    )
    result = orch.run_from_message("Revisa la póliza POL-48291")
    assert result["decision"] == DecisionOutcome.EXECUTE.value
    assert result["environment_id"] == demo_id
    assert result["crm_write"]["performed"] is True
    loaded = store.get(result["id"])
    assert loaded is not None
    assert loaded["environment_id"] == demo_id


def test_postgres_job_row_stores_demo_environment_id() -> None:
    """Write one job via PostgresJobStore; do not delete (no reset)."""
    from sqlalchemy import text

    from app.db.session import get_session_factory
    from app.services.job_store import JOB_STORE, PostgresJobStore

    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")
    if not isinstance(JOB_STORE, PostgresJobStore):
        pytest.skip("PostgresJobStore not active")

    orch = create_policy_review_orchestrator(
        store=JOB_STORE,
        skip_interpretation=True,
        world=WORLD,
    )
    result = orch.run_from_message("Revisa la póliza POL-2831")
    assert result["decision"] == DecisionOutcome.REVIEW.value
    assert result["environment_id"] == demo_id

    session = get_session_factory()()
    try:
        env = session.execute(
            text("SELECT environment_id::text FROM jobs WHERE id = CAST(:id AS uuid)"),
            {"id": result["id"]},
        ).scalar()
    finally:
        session.close()
    assert env == demo_id


def test_fallback_when_demo_environment_unavailable() -> None:
    with patch(
        "app.services.policy_review.runtime.get_demo_environment_id",
        return_value=None,
    ):
        orch = create_policy_review_orchestrator(
            store=InMemoryJobStore(),
            skip_interpretation=True,
            world=WORLD,
        )
    assert orch.environment_id is None
    assert isinstance(orch.crm, SimulatedCRMAdapter)
    assert isinstance(orch.legacy, SimulatedLegacyAdapter)
    result = orch.run_from_message("Revisa la póliza POL-48291")
    assert result["decision"] == DecisionOutcome.EXECUTE.value
    assert result["crm_write"]["performed"] is True
    assert "environment_id" not in result or result.get("environment_id") is None


def test_post_policy_review_without_environment_id() -> None:
    """HTTP contract: body with only message still works (UI unchanged)."""
    client = TestClient(app)
    # Avoid live Gemini in this path by patching orchestrator factory's skip — use runtime unit
    # path instead for decisions; here only assert route accepts the payload shape.
    with patch(
        "app.routes.jobs.create_policy_review_orchestrator",
    ) as factory:
        store = InMemoryJobStore()
        factory.return_value = create_policy_review_orchestrator(
            store=store,
            skip_interpretation=True,
            world=WORLD,
        )
        # Re-bind so factory mock still builds real orch when called
        def _make(**kwargs):
            return create_policy_review_orchestrator(
                environment_id=kwargs.get("environment_id"),
                store=InMemoryJobStore(),
                skip_interpretation=True,
                world=WORLD,
            )

        factory.side_effect = _make
        response = client.post(
            "/jobs/policy-review",
            json={"message": "Revisa la póliza POL-2831"},
        )
    assert response.status_code == 200
    assert response.json()["decision"] == DecisionOutcome.REVIEW.value
    factory.assert_called_once()
    assert factory.call_args.kwargs.get("environment_id") is None


def test_post_policy_review_with_demo_environment_id() -> None:
    demo_id = get_demo_environment_id()
    if demo_id is None:
        pytest.skip("Demo Environment not seeded")

    client = TestClient(app)

    def _make(**kwargs):
        return create_policy_review_orchestrator(
            environment_id=kwargs.get("environment_id"),
            store=InMemoryJobStore(),
            skip_interpretation=True,
            world=WORLD,
        )

    with patch("app.routes.jobs.create_policy_review_orchestrator", side_effect=_make) as factory:
        response = client.post(
            "/jobs/policy-review",
            json={"message": "Revisa la póliza POL-48291", "environment_id": demo_id},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == DecisionOutcome.EXECUTE.value
    assert body["crm_write"]["performed"] is True
    factory.assert_called_once()
    assert factory.call_args.kwargs.get("environment_id") == demo_id
