"""API hardening tests: CORS, validation, errors, health, rate limit, timeouts config."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.middleware import reset_rate_limit_state_for_tests
from app.models.enums import DecisionOutcome
from app.services.adapters import UnknownAdapterError
from app.services.job_store import InMemoryJobStore
from app.services.policy_review.runtime import create_policy_review_orchestrator
from integrations.simulated_world import WORLD


@pytest.fixture(autouse=True)
def _clean_rate_limit() -> None:
    reset_rate_limit_state_for_tests()
    yield
    reset_rate_limit_state_for_tests()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_liveness(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_readiness(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_cors_local_origin_allowed(client: TestClient) -> None:
    response = client.options(
        "/jobs/policy-review",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_127_origin_allowed(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"


def test_cors_disallowed_origin_no_acao(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


def test_invalid_empty_message(client: TestClient) -> None:
    response = client.post("/jobs/policy-review", json={"message": "   "})
    assert response.status_code == 422


def test_invalid_oversized_message(client: TestClient) -> None:
    response = client.post("/jobs/policy-review", json={"message": "x" * 4001})
    assert response.status_code == 422


def test_invalid_environment_id_format(client: TestClient) -> None:
    response = client.post(
        "/jobs/policy-review",
        json={"message": "Revisa la póliza POL-2831", "environment_id": "not-a-uuid"},
    )
    assert response.status_code == 422
    body = response.text.lower()
    assert "password" not in body
    assert "secret" not in body
    assert "bearer" not in body


def test_missing_environment_returns_404(client: TestClient) -> None:
    missing = str(uuid4())
    response = client.post(
        "/jobs/policy-review",
        json={"message": "Revisa la póliza POL-2831", "environment_id": missing},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "environment not found"
    assert "traceback" not in response.text.lower()


def test_unknown_adapter_returns_400(client: TestClient) -> None:
    with patch(
        "app.routes.jobs.create_policy_review_orchestrator",
        side_effect=UnknownAdapterError("Unknown adapter 'x'"),
    ):
        response = client.post(
            "/jobs/policy-review",
            json={"message": "Revisa la póliza POL-2831"},
        )
    assert response.status_code == 400
    assert "unknown adapter" in response.json()["detail"].lower()
    assert "traceback" not in response.text.lower()


def test_invalid_job_id_uuid(client: TestClient) -> None:
    response = client.get("/jobs/not-a-uuid")
    assert response.status_code == 422


def test_unhandled_error_hides_secrets(client: TestClient) -> None:
    with patch(
        "app.routes.jobs.create_policy_review_orchestrator",
        side_effect=RuntimeError(
            "boom DATABASE_URL=postgresql+psycopg://u:p@host/db "
            "Authorization: Bearer super-secret-token "
            "client_secret=abc123"
        ),
    ):
        response = client.post(
            "/jobs/policy-review",
            json={"message": "Revisa la póliza POL-2831"},
        )
    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"] == "internal server error"
    assert "request_id" in payload
    text = response.text.lower()
    assert "super-secret-token" not in text
    assert "client_secret=abc123" not in text
    assert "postgresql+psycopg://u:p@" not in text
    assert "traceback" not in text


def test_cybernotes_timeout_configured() -> None:
    settings = get_settings()
    assert settings.cybernotes_timeout_seconds > 0
    assert settings.gemini_timeout_seconds > 0


def test_rate_limit_policy_review(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_POLICY_REVIEW_PER_MINUTE", "2")
    get_settings.cache_clear()
    reset_rate_limit_state_for_tests()

    fake_orch = MagicMock()
    fake_orch.run_from_message.return_value = {
        "id": str(uuid4()),
        "status": "completed",
        "workflow_key": "policy_review",
        "policy_id": "POL-2831",
        "input_message": "Revisa la póliza POL-2831",
        "decision": "REVIEW",
        "allow_external_write": False,
        "avatar_state": "confused",
        "running_avatar_state": "working",
        "crm_write": {"attempted": False, "performed": False, "skipped": True},
        "sources": {},
        "timeline": [],
        "evidence": [],
        "progress": [],
        "assistant_summary": "ok",
        "reasons": [],
        "facts": {},
        "interpretation": None,
        "interpretation_source": None,
        "presentation": None,
    }

    try:
        with patch("app.routes.jobs.create_policy_review_orchestrator", return_value=fake_orch):
            r1 = client.post("/jobs/policy-review", json={"message": "Revisa la póliza POL-2831"})
            r2 = client.post("/jobs/policy-review", json={"message": "Revisa la póliza POL-2831"})
            r3 = client.post("/jobs/policy-review", json={"message": "Revisa la póliza POL-2831"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["detail"] == "rate limit exceeded"
    finally:
        monkeypatch.delenv("RATE_LIMIT_POLICY_REVIEW_PER_MINUTE", raising=False)
        get_settings.cache_clear()
        reset_rate_limit_state_for_tests()


def test_policy_review_behavior_still_works(client: TestClient) -> None:
    """Existing contract: message-only body → 200 + decision."""
    WORLD.reset()

    def _make(**kwargs):
        return create_policy_review_orchestrator(
            environment_id=kwargs.get("environment_id"),
            store=InMemoryJobStore(),
            skip_interpretation=True,
            world=WORLD,
        )

    with patch("app.routes.jobs.create_policy_review_orchestrator", side_effect=_make):
        response = client.post(
            "/jobs/policy-review",
            json={"message": "Revisa la póliza POL-2831"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == DecisionOutcome.REVIEW.value
    assert body["policy_id"] == "POL-2831"
    assert "id" in body


def test_cors_settings_reject_star_with_credentials() -> None:
    settings = Settings(
        cors_origins="*",
        cors_allow_credentials=True,
    )
    origins = settings.cors_origin_list()
    assert "*" not in origins
    assert "http://localhost:3000" in origins
