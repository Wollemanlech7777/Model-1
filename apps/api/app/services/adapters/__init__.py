"""Adapter factory / registry for environment-scoped integrations."""

from app.services.adapters.bundle import AdapterBundle
from app.services.adapters.factory import (
    ADAPTER_REGISTRY,
    UnknownAdapterError,
    build_adapters,
)

__all__ = [
    "ADAPTER_REGISTRY",
    "AdapterBundle",
    "UnknownAdapterError",
    "build_adapters",
]
