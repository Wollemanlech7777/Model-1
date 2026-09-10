"""Shared simulated customer-like systems for the policy-review demo.

Synthetic data only — not real broker/carrier systems.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyFixture:
    crm_status: str | None = None
    crm_auth_error: str | None = None  # e.g. "401"
    legacy_status: str | None = None
    email_status: str | None = None
    email_snippet: str | None = None
    portal_status: str | None = None


# Demo cases required by the product brief.
POLICY_FIXTURES: dict[str, PolicyFixture] = {
    "POL-2831": PolicyFixture(
        crm_status="ACTIVE",
        legacy_status="ACTIVE",
        email_status="CANCELLED",
        email_snippet="Notice: policy POL-2831 appears CANCELLED per carrier email.",
        portal_status="CANCELLED",
    ),
    "POL-48291": PolicyFixture(
        crm_status="ACTIVE",
        legacy_status="ACTIVE",
        email_status="ACTIVE",
        email_snippet="Payment confirmed. Policy POL-48291 remains ACTIVE.",
        portal_status="ACTIVE",
    ),
    "POL-77102": PolicyFixture(
        crm_auth_error="401",
        legacy_status="ACTIVE",
        email_status="ACTIVE",
        email_snippet="Routine notice for POL-77102.",
        portal_status="ACTIVE",
    ),
}


@dataclass
class SimulatedWorld:
    """In-memory stand-ins for CRM / legacy / email / portal."""

    fixtures: dict[str, PolicyFixture] = field(default_factory=lambda: deepcopy(POLICY_FIXTURES))
    crm_activities: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.fixtures = deepcopy(POLICY_FIXTURES)
        self.crm_activities.clear()

    def get_fixture(self, policy_id: str) -> PolicyFixture | None:
        return self.fixtures.get(policy_id.upper())


# Process-wide demo world (tests can call reset()).
WORLD = SimulatedWorld()
