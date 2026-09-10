"""Simulated legacy tabular adapter."""

from __future__ import annotations

from typing import Any

from integrations.base import AdapterHealth, AdapterResult
from integrations.legacy.interface import LegacyAdapter
from integrations.simulated_world import WORLD, SimulatedWorld


class SimulatedLegacyAdapter(LegacyAdapter):
    def __init__(self, world: SimulatedWorld | None = None) -> None:
        self.world = world or WORLD

    def healthcheck(self) -> AdapterHealth:
        return AdapterHealth(ok=True, message="simulated legacy ok")

    def discover(self) -> AdapterResult:
        return AdapterResult(success=True, data={"capabilities": ["fetch_rows", "find_candidates"]})

    def fetch_rows(self, query: dict[str, Any] | None = None) -> AdapterResult:
        query = query or {}
        policy_id = str(query.get("policy_id", "")).upper()
        fixture = self.world.get_fixture(policy_id)
        if fixture is None or fixture.legacy_status is None:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"legacy row not found:{policy_id}",
            )
        row = {
            "policy_no": policy_id,
            "customer_name": "Demo Customer",
            "status": fixture.legacy_status,
        }
        return AdapterResult(success=True, data={"rows": [row], "match": "exact"})

    def find_candidates(self, identity_hints: dict[str, Any]) -> AdapterResult:
        return self.fetch_rows({"policy_id": identity_hints.get("policy_id")})
