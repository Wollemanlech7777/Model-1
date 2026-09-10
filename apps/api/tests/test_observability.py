"""Phase 6.3 — configuration & observability checks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.errors import REQUEST_ID_HEADER, sanitize_log_text
from app.main import app
from app.middleware import reset_rate_limit_state_for_tests


@pytest.fixture(autouse=True)
def _clean_rate_limit() -> None:
    reset_rate_limit_state_for_tests()
    yield
    reset_rate_limit_state_for_tests()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_settings_dev_defaults() -> None:
    settings = Settings(
        environment="development",
        enable_demo_reset=None,
        gemini_api_key=None,
        cybernotes_client_secret=None,
    )
    assert settings.environment == "development"
    assert settings.is_production() is False
    assert settings.demo_reset_allowed() is True
    assert settings.cybernotes_timeout_seconds > 0
    assert settings.gemini_timeout_seconds > 0
    assert settings.rate_limit_policy_review_per_minute >= 0
    assert "http://localhost:3000" in settings.cors_origin_list()


def test_settings_production_disables_demo_reset_by_default() -> None:
    settings = Settings(
        environment="production",
        enable_demo_reset=None,
    )
    assert settings.is_production() is True
    assert settings.demo_reset_allowed() is False


def test_settings_cors_and_rate_limit_configurable() -> None:
    settings = Settings(
        cors_origins="http://localhost:3000",
        rate_limit_policy_review_per_minute=12,
    )
    assert settings.cors_origin_list() == ["http://localhost:3000"]
    assert settings.rate_limit_policy_review_per_minute == 12


def test_request_id_generated_and_returned(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER)
    assert len(response.headers[REQUEST_ID_HEADER]) >= 8


def test_request_id_propagated_from_client(client: TestClient) -> None:
    rid = "client-corr-12345"
    response = client.get("/health", headers={REQUEST_ID_HEADER: rid})
    assert response.headers.get(REQUEST_ID_HEADER) == rid


def test_error_response_includes_request_id_not_secrets(client: TestClient) -> None:
    response = client.post(
        "/jobs/policy-review",
        json={"message": "Revisa la póliza POL-2831", "environment_id": str(uuid4())},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "environment not found"
    assert body["request_id"]
    assert response.headers.get(REQUEST_ID_HEADER) == body["request_id"]
    assert "traceback" not in response.text.lower()
    assert "password" not in response.text.lower()


def test_sanitize_redacts_secrets() -> None:
    raw = (
        "fail DATABASE_URL=postgresql+psycopg://u:p@host/db "
        "Authorization: Bearer tokensecret "
        "client_secret=abc123 GEMINI_API_KEY=xyz"
    )
    cleaned = sanitize_log_text(raw, max_len=500)
    assert "tokensecret" not in cleaned
    assert "abc123" not in cleaned
    assert "postgresql+psycopg://u:p@" not in cleaned
    assert "[REDACTED]" in cleaned


def test_demo_reset_blocked_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENABLE_DEMO_RESET", raising=False)
    get_settings.cache_clear()
    try:
        response = client.post("/crm/reset-demo")
        assert response.status_code == 404
        assert response.json()["detail"] == "not found"
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        get_settings.cache_clear()


def test_policy_review_logs_job_correlation(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    fake = MagicMock()
    fake.run_from_message.return_value = {
        "id": str(uuid4()),
        "status": "completed",
        "workflow_key": "policy_review",
        "policy_id": "POL-48291",
        "input_message": "Revisa la póliza POL-48291",
        "decision": "execute",
        "allow_external_write": True,
        "avatar_state": "proud",
        "running_avatar_state": "working",
        "crm_write": {"attempted": True, "performed": True, "skipped": False},
        "sources": {},
        "timeline": [],
        "evidence": [
            {
                "id": "e1",
                "source": "portal",
                "result": "error",
                "relevant_data": {},
                "errors": ["timeout: cybernotes policy timeout"],
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "progress": [],
        "assistant_summary": "ok",
        "reasons": [],
        "facts": {},
        "interpretation": None,
        "interpretation_source": None,
        "presentation": None,
    }
    with patch("app.routes.jobs.create_policy_review_orchestrator", return_value=fake):
        with caplog.at_level("INFO", logger="app.api"):
            response = client.post(
                "/jobs/policy-review",
                json={"message": "Revisa la póliza POL-48291"},
                headers={REQUEST_ID_HEADER: "obs-test-rid"},
            )
    assert response.status_code == 200
    joined = "\n".join(caplog.messages)
    assert "policy_review_complete" in joined
    assert "obs-test-rid" in joined
    assert fake.run_from_message.return_value["id"] in joined
    assert "policy_review_integration_issue" in joined
    assert "timeout" in joined.lower()
    assert "Bearer" not in joined
