"""Email inbox adapter interface."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from integrations.base import AdapterResult, IntegrationAdapter


class EmailAdapter(IntegrationAdapter):
    name = "email"

    @abstractmethod
    def list_messages(self, query: dict[str, Any] | None = None) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def get_message(self, message_id: str) -> AdapterResult:
        """Return unstructured message body/metadata for later interpretation."""
        raise NotImplementedError
