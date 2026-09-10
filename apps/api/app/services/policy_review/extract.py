"""Extract a policy identifier from free-text chat input."""

from __future__ import annotations

import re

POLICY_ID_PATTERN = re.compile(r"\b(POL-\d+)\b", flags=re.IGNORECASE)


def extract_policy_id(message: str) -> str | None:
    if not message or not message.strip():
        return None
    match = POLICY_ID_PATTERN.search(message)
    if not match:
        return None
    return match.group(1).upper()
