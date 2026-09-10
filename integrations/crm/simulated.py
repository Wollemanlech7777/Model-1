"""Simulated CRM REST adapter."""

from __future__ import annotations

from typing import Any

from integrations.base import AdapterHealth, AdapterResult
from integrations.crm.interface import CRMAdapter
from integrations.simulated_world import WORLD, SimulatedWorld


class SimulatedCRMAdapter(CRMAdapter):
    def __init__(self, world: SimulatedWorld | None = None) -> None:
        self.world = world or WORLD

    def healthcheck(self) -> AdapterHealth:
        return AdapterHealth(ok=True, message="simulated crm ok")

    def discover(self) -> AdapterResult:
        return AdapterResult(success=True, data={"capabilities": ["get_record", "create_activity"]})

    def get_record(self, record_type: str, record_id: str) -> AdapterResult:
        if record_type != "policy":
            return AdapterResult(
                success=False,
                error_code="400",
                error_message=f"unsupported record_type:{record_type}",
            )

        fixture = self.world.get_fixture(record_id)
        if fixture is None:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"policy not found:{record_id}",
            )

        if fixture.crm_auth_error:
            return AdapterResult(
                success=False,
                error_code=fixture.crm_auth_error,
                error_message="Unauthorized",
                data={"policy_id": record_id.upper()},
            )

        return AdapterResult(
            success=True,
            data={
                "policy_id": record_id.upper(),
                "status": fixture.crm_status,
                "http_status": 200,
            },
        )

    def create_activity(self, payload: dict[str, Any]) -> AdapterResult:
        activity = {
            "id": f"act-{len(self.world.crm_activities) + 1}",
            **payload,
        }
        self.world.crm_activities.append(activity)
        return AdapterResult(success=True, data=activity)
