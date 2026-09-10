"""HTML portal adapter interface (scraping as integration, not product goal)."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from integrations.base import AdapterResult, IntegrationAdapter


class PortalAdapter(IntegrationAdapter):
    name = "portal"

    @abstractmethod
    def fetch_page(self, path_or_url: str) -> AdapterResult:
        raise NotImplementedError

    @abstractmethod
    def extract_structured(self, html: str, hints: dict[str, Any] | None = None) -> AdapterResult:
        """Parse HTML into structured fields; fail safely if contract missing."""
        raise NotImplementedError
