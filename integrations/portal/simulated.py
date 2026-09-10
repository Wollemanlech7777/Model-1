"""Simulated HTML portal adapter."""

from __future__ import annotations

import re
from typing import Any

from integrations.base import AdapterHealth, AdapterResult
from integrations.portal.interface import PortalAdapter
from integrations.simulated_world import WORLD, SimulatedWorld


class SimulatedPortalAdapter(PortalAdapter):
    def __init__(self, world: SimulatedWorld | None = None) -> None:
        self.world = world or WORLD

    def healthcheck(self) -> AdapterHealth:
        return AdapterHealth(ok=True, message="simulated portal ok")

    def discover(self) -> AdapterResult:
        return AdapterResult(success=True, data={"capabilities": ["fetch_page", "extract_structured"]})

    def fetch_page(self, path_or_url: str) -> AdapterResult:
        match = re.search(r"(POL-\d+)", path_or_url, flags=re.IGNORECASE)
        if not match:
            return AdapterResult(
                success=False,
                error_code="400",
                error_message="policy id missing from portal path",
            )
        policy_id = match.group(1).upper()
        fixture = self.world.get_fixture(policy_id)
        if fixture is None or fixture.portal_status is None:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"portal page not found:{policy_id}",
            )

        html = (
            f"<html><body>"
            f"<h1>Policy {policy_id}</h1>"
            f'<div class="status" data-status="{fixture.portal_status}">'
            f"Current Policy State: {fixture.portal_status}"
            f"</div></body></html>"
        )
        return AdapterResult(
            success=True,
            data={"policy_id": policy_id, "http_status": 200, "html": html},
        )

    def extract_structured(self, html: str, hints: dict[str, Any] | None = None) -> AdapterResult:
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
