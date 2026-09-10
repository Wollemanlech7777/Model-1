"""RealPortalAdapter + factory registration — HTTP mocked, no live CyberNotes."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.models.enums import ConnectorType, EnvironmentStatus
from app.models.orm import ConnectorORM, CustomerORM, EnvironmentORM
from app.services.adapters import ADAPTER_REGISTRY, build_adapters
from integrations.portal.real import RealPortalAdapter
from integrations.portal.simulated import SimulatedPortalAdapter


def _handler_factory(routes: dict[tuple[str, str], httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method.upper(), request.url.path)
        # Match path suffixes for /policies/{id}
        for (method, path), response in routes.items():
            if method != request.method.upper():
                continue
            if path == request.url.path or request.url.path.endswith(path):
                return response
        return httpx.Response(599, json={"error": f"unmocked {request.method} {request.url.path}"})

    return handler


def _adapter(
    *,
    routes: dict[tuple[str, str], httpx.Response],
    policy_id_map: dict[str, str] | None = None,
    client_id: str = "test-client",
    client_secret: str = "test-secret",
) -> RealPortalAdapter:
    transport = httpx.MockTransport(_handler_factory(routes))
    client = httpx.Client(transport=transport, base_url="https://api.cybernotes.it/mtpl/v1")
    return RealPortalAdapter(
        {
            "base_url": "https://api.cybernotes.it/mtpl/v1",
            "client_id": client_id,
            "client_secret": client_secret,
            "policy_id_map": policy_id_map
            or {
                "POL-48291": "pol-5fa50ab9",
            },
        },
        client=client,
    )


def test_settings_expose_cybernotes_fields() -> None:
    settings = get_settings()
    assert settings.cybernotes_base_url.endswith("/mtpl/v1")
    assert hasattr(settings, "cybernotes_client_id")
    assert hasattr(settings, "cybernotes_client_secret")


def test_token_success_then_policy_active() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer", "expires_in": 3600}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(
                200,
                json={
                    "id": "pol-5fa50ab9",
                    "productCode": "MTPL-STD",
                    "regNumber": "ARTURO-101",
                    "status": "active",
                },
            ),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is True
    assert page.data["policy_id"] == "POL-48291"
    assert page.data["http_status"] == 200
    assert 'data-status="ACTIVE"' in page.data["html"]

    extracted = adapter.extract_structured(page.data["html"])
    assert extracted.success is True
    assert extracted.data["status"] == "ACTIVE"
    assert extracted.data["policy_id"] == "POL-48291"


def test_token_failure() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(401, json={"error": "invalid_client"}),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "401"


def test_policy_404() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(404, json={"error": "not_found"}),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "404"


def test_policy_403() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(403, json={"error": "forbidden"}),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "403"


def test_policy_401_after_token() -> None:
    # Auth succeeds but policy call returns 401 and re-auth also fails → 401
    calls = {"auth": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/auth/token"):
            calls["auth"] += 1
            if calls["auth"] == 1:
                return httpx.Response(
                    200, json={"access_token": "tok", "token_type": "Bearer"}
                )
            return httpx.Response(401, json={"error": "invalid"})
        if request.method == "GET":
            return httpx.Response(401, json={"error": "expired"})
        return httpx.Response(599)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.cybernotes.it/mtpl/v1",
    )
    adapter = RealPortalAdapter(
        {
            "base_url": "https://api.cybernotes.it/mtpl/v1",
            "client_id": "c",
            "client_secret": "s",
            "policy_id_map": {"POL-48291": "pol-5fa50ab9"},
        },
        client=client,
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "401"


def test_policy_429() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(429, json={"error": "rate"}),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "429"


def test_policy_5xx() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(503, text="unavailable"),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "503"


def test_timeout_on_policy() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            )
        raise httpx.ReadTimeout("timed out")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.cybernotes.it/mtpl/v1",
    )
    adapter = RealPortalAdapter(
        {
            "base_url": "https://api.cybernotes.it/mtpl/v1",
            "client_id": "c",
            "client_secret": "s",
            "policy_id_map": {"POL-48291": "pol-5fa50ab9"},
        },
        client=client,
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "timeout"


def test_network_error_on_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.cybernotes.it/mtpl/v1",
    )
    adapter = RealPortalAdapter(
        {
            "base_url": "https://api.cybernotes.it/mtpl/v1",
            "client_id": "c",
            "client_secret": "s",
            "policy_id_map": {"POL-48291": "pol-5fa50ab9"},
        },
        client=client,
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is False
    assert page.error_code == "network_error"


def test_status_cancelled_normalized() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
            ("GET", "/policies/pol-5fa50ab9"): httpx.Response(
                200,
                json={"id": "pol-5fa50ab9", "status": "cancelled"},
            ),
        }
    )
    page = adapter.fetch_page("/policies/POL-48291")
    assert page.success is True
    extracted = adapter.extract_structured(page.data["html"])
    assert extracted.data["status"] == "CANCELLED"


def test_policy_id_mapping_missing() -> None:
    adapter = _adapter(
        routes={
            ("POST", "/auth/token"): httpx.Response(
                200, json={"access_token": "tok", "token_type": "Bearer"}
            ),
        },
        policy_id_map={"POL-48291": "pol-5fa50ab9"},
    )
    page = adapter.fetch_page("/policies/POL-2831")
    assert page.success is False
    assert page.error_code == "400"
    assert "policy_id_map" in (page.error_message or "")


def test_registry_has_portal_real() -> None:
    assert ("portal", "real") in ADAPTER_REGISTRY
    assert ("portal", "simulated") in ADAPTER_REGISTRY


def _db_ready() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM customers LIMIT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_ready(), reason="customers schema not available")
def test_factory_returns_real_portal_adapter() -> None:
    customer_id = uuid4()
    env_id = uuid4()
    session = get_session_factory()()
    try:
        customer = CustomerORM(id=customer_id, name=f"Real Portal {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        env = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Real Env {env_id.hex[:8]}",
            status=EnvironmentStatus.DRAFT.value,
        )
        session.add(env)
        session.flush()
        for ctype in ConnectorType:
            config = {"adapter": "simulated"}
            if ctype == ConnectorType.PORTAL:
                config = {
                    "adapter": "real",
                    "policy_id_map": {"POL-48291": "pol-5fa50ab9"},
                }
            session.add(
                ConnectorORM(
                    id=uuid4(),
                    environment=env,
                    connector_type=ctype.value,
                    name=ctype.value,
                    config=config,
                )
            )
        session.commit()
    finally:
        session.close()

    try:
        bundle = build_adapters(env_id)
        assert isinstance(bundle.portal, RealPortalAdapter)
        from integrations.crm.simulated import SimulatedCRMAdapter

        assert isinstance(bundle.crm, SimulatedCRMAdapter)
    finally:
        session = get_session_factory()()
        try:
            cust = session.get(CustomerORM, customer_id)
            if cust is not None:
                session.delete(cust)
                session.commit()
        finally:
            session.close()


@pytest.mark.skipif(not _db_ready(), reason="customers schema not available")
def test_factory_still_returns_simulated_portal() -> None:
    customer_id = uuid4()
    env_id = uuid4()
    session = get_session_factory()()
    try:
        customer = CustomerORM(id=customer_id, name=f"Sim Portal {customer_id.hex[:8]}")
        session.add(customer)
        session.flush()
        env = EnvironmentORM(
            id=env_id,
            customer=customer,
            name=f"Sim Env {env_id.hex[:8]}",
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
                    config={"adapter": "simulated"},
                )
            )
        session.commit()
    finally:
        session.close()

    try:
        bundle = build_adapters(env_id)
        assert isinstance(bundle.portal, SimulatedPortalAdapter)
    finally:
        session = get_session_factory()()
        try:
            cust = session.get(CustomerORM, customer_id)
            if cust is not None:
                session.delete(cust)
                session.commit()
        finally:
            session.close()


def test_factory_lambda_builds_real_without_db() -> None:
    factory = ADAPTER_REGISTRY[("portal", "real")]
    adapter = factory({"policy_id_map": {"POL-1": "pol-x"}, "client_id": "a", "client_secret": "b"}, None)
    assert isinstance(adapter, RealPortalAdapter)
    sim = ADAPTER_REGISTRY[("portal", "simulated")]({}, None)
    assert isinstance(sim, SimulatedPortalAdapter)
