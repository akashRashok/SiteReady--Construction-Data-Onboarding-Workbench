"""Deterministic grounding checks for advisory LLM text.

The model may only restate facts that are present in its structured input. These checks
run in ordinary code after every draft, so a bad draft is rejected instead of shipped:

* every number in the text must appear in the structured payload (no new or derived figures)
* the text must not claim an action that did not happen (this tool exports files, it never
  imports into a target system) or add praise
"""

from __future__ import annotations

import re
from typing import Any

_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?!\w)")
_LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*+]\s+)?\d+[.)]\s+")
_CLAIM_WORDS = re.compile(
    r"\b(successful(?:ly)?|imported|migrated|congratulations|good|great|excellent|"
    r"perfect|flawless)\b",
    re.IGNORECASE,
)


def _normalise(token: str) -> str:
    token = token.replace(",", "")
    if "." in token:
        return token.rstrip("0").rstrip(".") or "0"
    return str(int(token))


def _numbers_in(text: str) -> set[str]:
    return {_normalise(m) for m in _NUMBER.findall(text)}


def allowed_numbers(payload: Any) -> set[str]:
    """Every number that appears anywhere in the structured input."""
    found: set[str] = set()
    if isinstance(payload, bool):
        return found
    if isinstance(payload, (int, float)):
        return {_normalise(str(payload))}
    if isinstance(payload, str):
        return _numbers_in(payload)
    if isinstance(payload, dict):
        for key, value in payload.items():
            found |= _numbers_in(str(key))
            found |= allowed_numbers(value)
    elif isinstance(payload, (list, tuple, set)):
        for value in payload:
            found |= allowed_numbers(value)
    return found


def check_grounded(text: str, payload: dict[str, Any]) -> list[str]:
    """Return a list of problems; an empty list means the draft is acceptable."""
    problems: list[str] = []
    allowed = allowed_numbers(payload)
    body = _LIST_MARKER.sub("", text)
    unknown = sorted({n for n in _numbers_in(body) if n not in allowed})
    if unknown:
        problems.append("numbers not present in the input: " + ", ".join(unknown))
    words = sorted({m.group(0).lower() for m in _CLAIM_WORDS.finditer(body)})
    if words:
        problems.append("unsupported claim or praise wording: " + ", ".join(words))
    return problems
