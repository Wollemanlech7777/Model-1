"""Natural-language presentation helpers for chat (no operational authority)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


_SOURCE_LABELS = {
    "crm": "CRM",
    "legacy": "Legacy",
    "email": "Email",
    "portal": "Portal",
}

_STATUS_LABELS = {
    "ACTIVE": "ACTIVA",
    "CANCELLED": "CANCELADA",
    "PENDING": "PENDIENTE",
    "EXPIRED": "VENCIDA",
}


def status_label(status: str) -> str:
    key = str(status).upper()
    return _STATUS_LABELS.get(key, key)


def source_label(key: str) -> str:
    return _SOURCE_LABELS.get(key.lower(), key.upper())


def format_sources_by_status(sources: dict[str, Any]) -> str:
    """Group sources by status into Spanish prose."""
    groups: dict[str, list[str]] = defaultdict(list)
    for key, status in (sources or {}).items():
        if status is None:
            continue
        groups[status_label(status)].append(source_label(key))

    if not groups:
        return "No hay estados de fuente disponibles."

    parts: list[str] = []
    for status, names in sorted(groups.items()):
        if len(names) == 1:
            parts.append(f"{names[0]} indica que la póliza está {status}")
        elif len(names) == 2:
            parts.append(f"{names[0]} y {names[1]} indican que la póliza está {status}")
        else:
            head = ", ".join(names[:-1])
            parts.append(f"{head} y {names[-1]} indican que la póliza está {status}")
    if len(parts) == 1:
        return parts[0] + "."
    return ", mientras que ".join(parts) + "."


def describe_conflict(sources: dict[str, Any]) -> str:
    text = format_sources_by_status(sources)
    if "mientras que" in text:
        return text
    return (
        "Las fuentes consultadas no están completamente alineadas. "
        + text
    )


def describe_why_no_crm_write(job: dict[str, Any]) -> str:
    decision = str(job.get("decision") or "").lower()
    sources = job.get("sources") or {}
    if decision == "review":
        return (
            "No actualicé el CRM porque encontré información contradictoria entre las fuentes. "
            "La política requiere revisión manual antes de realizar cambios."
        )
    if decision == "fail":
        return (
            "No actualicé el CRM porque la consulta falló por un problema de autorización (401). "
            "Detuve el proceso y no realicé cambios."
        )
    crm_write = job.get("crm_write") or {}
    if crm_write.get("performed"):
        return (
            "Sí registré una actividad en el CRM porque todas las fuentes coincidieron "
            "y la verificación se completó correctamente."
        )
    return "No se realizaron cambios en el CRM en este job."


def describe_what_happened(job: dict[str, Any]) -> str:
    decision = str(job.get("decision") or "").lower()
    sources = job.get("sources") or {}
    policy_id = job.get("policy_id") or "la póliza"

    if decision == "review":
        return (
            f"Encontré una discrepancia entre los sistemas conectados al revisar {policy_id}, "
            "así que detuve la actualización para evitar modificar información incorrecta."
        )
    if decision == "execute":
        return (
            f"Las cuatro fuentes confirmaron el mismo estado para {policy_id} "
            "y registré la actividad de verificación en el CRM."
        )
    if decision == "fail":
        return (
            f"No pude completar la revisión de {policy_id} porque el CRM rechazó la consulta "
            "por un error de autorización (401). Detuve el proceso y no realicé cambios."
        )
    return f"Completé la revisión de {policy_id} con el resultado disponible en la evidencia."


def describe_execute_success(job: dict[str, Any]) -> str:
    sources = job.get("sources") or {}
    raw = next(iter({str(v).upper() for v in sources.values() if v}), "ACTIVE")
    status = status_label(raw)
    return (
        f"Las cuatro fuentes confirmaron que la póliza está {status} "
        "y registré la actividad de verificación en el CRM."
    )


def looks_like_internal_leak(text: str) -> bool:
    markers = (
        "decision_not_execute",
        "conflict:policy_status",
        "allow_external_write",
        "crm_write=",
        "{'crm'",
        '{"crm"',
        "IntegrationFailure",
        "checks_passed",
        "missing_policy_id",
    )
    lower = text.lower()
    return any(m.lower() in lower for m in markers) or ("{" in text and "}" in text and "crm" in lower)
