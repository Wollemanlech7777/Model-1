"""Real CyberNotes MTPL portal adapter — preserves SimulatedPortalAdapter contracts."""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import get_settings
from integrations.base import AdapterHealth, AdapterResult
from integrations.portal.interface import PortalAdapter

_STATUS_MAP = {
    "active": "ACTIVE",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
}


def _normalize_portal_status(raw: Any) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    if key in _STATUS_MAP:
        return _STATUS_MAP[key]
    return str(raw).strip().upper()


def _synthetic_portal_html(*, policy_id: str, status: str, payload: dict[str, Any]) -> str:
    """HTML shaped for the existing extract_structured regex contract."""
    product = payload.get("productCode") or ""
    reg = payload.get("regNumber") or ""
    return (
        f"<html><body>"
        f"<h1>Policy {policy_id}</h1>"
        f'<div class="status" data-status="{status}">'
        f"Current Policy State: {status}"
        f"</div>"
        f'<div class="meta" data-product="{product}" data-reg="{reg}"></div>'
        f"</body></html>"
    )


def _extract_internal_policy_id(path_or_url: str) -> str | None:
    match = re.search(r"(POL-\d+)", path_or_url, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


class RealPortalAdapter(PortalAdapter):
    """CyberNotes MTPL → internal portal AdapterResult (html + status)."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = dict(config or {})
        settings = get_settings()
        self.base_url = str(
            self.config.get("base_url") or settings.cybernotes_base_url
        ).rstrip("/")
        self.client_id = self.config.get("client_id") or settings.cybernotes_client_id
        self.client_secret = (
            self.config.get("client_secret") or settings.cybernotes_client_secret
        )
        self.policy_id_map: dict[str, str] = {
            str(k).upper(): str(v)
            for k, v in dict(self.config.get("policy_id_map") or {}).items()
        }
        timeout = float(
            self.config.get("timeout_seconds")
            or settings.cybernotes_timeout_seconds
            or 20.0
        )
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self._access_token: str | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def healthcheck(self) -> AdapterHealth:
        if not self.client_id or not self.client_secret:
            return AdapterHealth(
                ok=False,
                message="cybernotes credentials missing (CYBERNOTES_CLIENT_ID / SECRET)",
            )
        return AdapterHealth(ok=True, message="cybernotes portal configured")

    def discover(self) -> AdapterResult:
        return AdapterResult(
            success=True,
            data={
                "capabilities": ["fetch_page", "extract_structured"],
                "provider": "cybernotes_mtpl",
                "base_url": self.base_url,
            },
        )

    def _authenticate(self) -> AdapterResult:
        if not self.client_id or not self.client_secret:
            return AdapterResult(
                success=False,
                error_code="401",
                error_message="cybernotes credentials not configured",
            )
        try:
            response = self._client.post(
                f"{self.base_url}/auth/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        except httpx.TimeoutException as exc:
            return AdapterResult(
                success=False,
                error_code="timeout",
                error_message=f"cybernotes auth timeout: {exc}",
            )
        except httpx.HTTPError as exc:
            return AdapterResult(
                success=False,
                error_code="network_error",
                error_message=f"cybernotes auth network error: {exc}",
            )

        if response.status_code in {401, 403}:
            return AdapterResult(
                success=False,
                error_code=str(response.status_code),
                error_message="cybernotes authentication failed",
                raw=response.text,
            )
        if response.status_code == 429:
            return AdapterResult(
                success=False,
                error_code="429",
                error_message="cybernotes auth rate limited",
                raw=response.text,
            )
        if response.status_code >= 500:
            return AdapterResult(
                success=False,
                error_code=str(response.status_code),
                error_message="cybernotes auth upstream failure",
                raw=response.text,
            )
        if response.status_code != 200:
            return AdapterResult(
                success=False,
                error_code=str(response.status_code),
                error_message=f"cybernotes auth unexpected status {response.status_code}",
                raw=response.text,
            )

        try:
            payload = response.json()
        except ValueError:
            return AdapterResult(
                success=False,
                error_code="parse_error",
                error_message="cybernotes auth response not JSON",
                raw=response.text,
            )

        token = payload.get("access_token")
        if not token:
            return AdapterResult(
                success=False,
                error_code="401",
                error_message="cybernotes auth missing access_token",
                raw=payload,
            )
        self._access_token = str(token)
        return AdapterResult(success=True, data={"token_type": payload.get("token_type")})

    def _ensure_token(self) -> AdapterResult:
        if self._access_token:
            return AdapterResult(success=True, data={})
        return self._authenticate()

    def _map_policy_id(self, internal_policy_id: str) -> AdapterResult:
        external = self.policy_id_map.get(internal_policy_id.upper())
        if not external:
            return AdapterResult(
                success=False,
                error_code="400",
                error_message=(
                    f"no policy_id_map entry for {internal_policy_id}; "
                    "configure connector.config.policy_id_map"
                ),
            )
        return AdapterResult(success=True, data={"external_id": external})

    def fetch_page(self, path_or_url: str) -> AdapterResult:
        internal_id = _extract_internal_policy_id(path_or_url)
        if not internal_id:
            return AdapterResult(
                success=False,
                error_code="400",
                error_message="policy id missing from portal path",
            )

        mapped = self._map_policy_id(internal_id)
        if not mapped.success:
            return mapped
        external_id = str(mapped.data["external_id"])

        auth = self._ensure_token()
        if not auth.success:
            return auth

        try:
            response = self._client.get(
                f"{self.base_url}/policies/{external_id}",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.TimeoutException as exc:
            return AdapterResult(
                success=False,
                error_code="timeout",
                error_message=f"cybernotes policy timeout: {exc}",
            )
        except httpx.HTTPError as exc:
            return AdapterResult(
                success=False,
                error_code="network_error",
                error_message=f"cybernotes policy network error: {exc}",
            )

        if response.status_code == 401:
            # One retry after re-auth (expired token).
            self._access_token = None
            auth_retry = self._authenticate()
            if not auth_retry.success:
                return AdapterResult(
                    success=False,
                    error_code="401",
                    error_message="cybernotes authentication failure",
                    raw=response.text,
                )
            try:
                response = self._client.get(
                    f"{self.base_url}/policies/{external_id}",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
            except httpx.HTTPError as exc:
                return AdapterResult(
                    success=False,
                    error_code="network_error",
                    error_message=f"cybernotes policy network error: {exc}",
                )

        if response.status_code == 401:
            return AdapterResult(
                success=False,
                error_code="401",
                error_message="cybernotes authentication failure",
                raw=response.text,
            )
        if response.status_code == 403:
            return AdapterResult(
                success=False,
                error_code="403",
                error_message="cybernotes insufficient scope/permission",
                raw=response.text,
            )
        if response.status_code == 404:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"portal page not found:{internal_id}",
                raw=response.text,
            )
        if response.status_code == 409:
            return AdapterResult(
                success=False,
                error_code="409",
                error_message="cybernotes policy conflict",
                raw=response.text,
            )
        if response.status_code == 429:
            return AdapterResult(
                success=False,
                error_code="429",
                error_message="cybernotes rate limited",
                raw=response.text,
            )
        if response.status_code >= 500:
            return AdapterResult(
                success=False,
                error_code=str(response.status_code),
                error_message="cybernotes upstream failure",
                raw=response.text,
            )
        if response.status_code != 200:
            return AdapterResult(
                success=False,
                error_code=str(response.status_code),
                error_message=f"cybernotes unexpected status {response.status_code}",
                raw=response.text,
            )

        try:
            payload = response.json()
        except ValueError:
            return AdapterResult(
                success=False,
                error_code="parse_error",
                error_message="cybernotes policy response not JSON",
                raw=response.text,
            )

        status = _normalize_portal_status(payload.get("status"))
        if not status:
            return AdapterResult(
                success=False,
                error_code="parse_error",
                error_message="cybernotes policy missing status",
                raw=payload,
            )

        html = _synthetic_portal_html(
            policy_id=internal_id,
            status=status,
            payload=payload if isinstance(payload, dict) else {},
        )
        return AdapterResult(
            success=True,
            data={
                "policy_id": internal_id,
                "http_status": 200,
                "html": html,
                "external_id": external_id,
                "raw_status": payload.get("status"),
            },
            raw=payload,
        )

    def extract_structured(self, html: str, hints: dict[str, Any] | None = None) -> AdapterResult:
        # Same contract as SimulatedPortalAdapter — no orchestrator changes.
        status_match = re.search(r'data-status="([A-Z]+)"', html)
        policy_match = re.search(r"(POL-\d+)", html, flags=re.IGNORECASE)
        if not status_match or not policy_match:
            return AdapterResult(
                success=False,
                error_code="parse_error",
                error_message="expected portal structure unavailable",
            )
        return AdapterResult(
            success=True,
            data={
                "policy_id": policy_match.group(1).upper(),
                "status": status_match.group(1),
            },
        )
