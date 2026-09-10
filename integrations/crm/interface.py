"""CRM REST adapter interface."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from integrations.base import AdapterResult, IntegrationAdapter


class CRMAdapter(IntegrationAdapter):
    name = "crm"

    @abstractmethod
    def get_record(self, record_type: str, record_id: str) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def create_activity(self, payload: dict[str, Any]) -> AdapterResult:
        """Write path — must only be called when decision.allow_external_write is True."""
        raise NotImplementedError
