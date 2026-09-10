"""Simulated email inbox adapter."""

from __future__ import annotations

from typing import Any

from integrations.base import AdapterHealth, AdapterResult
from integrations.email.interface import EmailAdapter
from integrations.simulated_world import WORLD, SimulatedWorld


class SimulatedEmailAdapter(EmailAdapter):
    def __init__(self, world: SimulatedWorld | None = None) -> None:
        self.world = world or WORLD

    def healthcheck(self) -> AdapterHealth:
        return AdapterHealth(ok=True, message="simulated email ok")

    def discover(self) -> AdapterResult:
        return AdapterResult(success=True, data={"capabilities": ["list_messages", "get_message"]})

    def list_messages(self, query: dict[str, Any] | None = None) -> AdapterResult:
        query = query or {}
        policy_id = str(query.get("policy_id", "")).upper()
        fixture = self.world.get_fixture(policy_id)
        if fixture is None or fixture.email_status is None:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"no email for:{policy_id}",
            )
        message_id = f"email-{policy_id}"
        return AdapterResult(
            success=True,
            data={
                "messages": [
                    {
                        "id": message_id,
                        "subject": f"Policy update {policy_id}",
                        "status_signal": fixture.email_status,
                    }
                ]
            },
        )

    def get_message(self, message_id: str) -> AdapterResult:
        policy_id = message_id.replace("email-", "").upper()
        fixture = self.world.get_fixture(policy_id)
        if fixture is None or fixture.email_status is None:
            return AdapterResult(
                success=False,
                error_code="404",
                error_message=f"message not found:{message_id}",
            )
        return AdapterResult(
            success=True,
            data={
                "id": message_id,
                "policy_id": policy_id,
                "status": fixture.email_status,
                "body": fixture.email_snippet,
            },
        )
