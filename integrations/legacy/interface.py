"""Legacy tabular / database adapter interface."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from integrations.base import AdapterResult, IntegrationAdapter


class LegacyAdapter(IntegrationAdapter):
    name = "legacy"

    @abstractmethod
    def fetch_rows(self, query: dict[str, Any] | None = None) -> AdapterResult:
        """Return messy tabular rows for normalization / matching."""
        raise NotImplementedError

    @abstractmethod
    def find_candidates(self, identity_hints: dict[str, Any]) -> AdapterResult:
        """Return zero or more candidate matches for an identity hint set."""
        raise NotImplementedError
