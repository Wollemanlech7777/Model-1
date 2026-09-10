"""Integration adapter interfaces — no concrete demo implementations yet."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterHealth:
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    raw: Any = None


class IntegrationAdapter(ABC):
    """Base contract for all customer-system adapters."""

    name: str

    @abstractmethod
    def healthcheck(self) -> AdapterHealth:
        raise NotImplementedError

    @abstractmethod
    def discover(self) -> AdapterResult:
        """Probe capabilities / schema without mutating external state."""
        raise NotImplementedError
