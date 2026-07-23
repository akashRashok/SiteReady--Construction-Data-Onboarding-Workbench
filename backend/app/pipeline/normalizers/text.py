"""Text normalisation helpers."""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_LEGAL_SUFFIXES = [
    "pty ltd",
    "pty. ltd.",
    "pty",
    "ltd",
    "limited",
    "proprietary",
    "incorporated",
    "inc",
    "co",
    "company",
    "group",
    "holdings",
    "services",
    "constructions",
    "construction",
]


def collapse_whitespace(value: str | None) -> str:
    return _WS.sub(" ", (value or "").strip())


def title_case(value: str | None) -> str:
    cleaned = collapse_whitespace(value)
    if not cleaned:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() if part else part for part in cleaned.split(" "))


def canonical_name(value: str | None) -> str:
    """Lowercase, strip legal suffixes and punctuation. Used for matching only."""
    cleaned = collapse_whitespace(value).lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = _WS.sub(" ", cleaned).strip()
    changed = True
    while changed:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            if cleaned.endswith(" " + suffix):
                cleaned = cleaned[: -(len(suffix) + 1)].strip()
                changed = True
            elif cleaned == suffix:
                cleaned = ""
                changed = True
    return _WS.sub(" ", cleaned).strip()


def normalise_cert_number(value: str | None) -> str:
    return re.sub(r"[\s-]", "", (value or "").strip()).upper()
