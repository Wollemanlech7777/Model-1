"""Typed bundle of integration adapters for a customer environment."""

from __future__ import annotations

from dataclasses import dataclass

from integrations.crm.interface import CRMAdapter
from integrations.email.interface import EmailAdapter
from integrations.legacy.interface import LegacyAdapter
from integrations.portal.interface import PortalAdapter


@dataclass(frozen=True)
class AdapterBundle:
    crm: CRMAdapter
    legacy: LegacyAdapter
    email: EmailAdapter
    portal: PortalAdapter
