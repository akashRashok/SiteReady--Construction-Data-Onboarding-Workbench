"""Email and phone normalisation (PRD section 11)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import phonenumbers

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class NormResult:
    is_valid: bool
    normalised: str | None
    raw: str


def normalise_email(raw: str | None) -> NormResult:
    text = (raw or "").strip()
    if not text:
        return NormResult(False, None, raw or "")
    candidate = text.lower()
    if _EMAIL_RE.match(candidate):
        return NormResult(True, candidate, raw or "")
    return NormResult(False, None, raw or "")


def normalise_phone(raw: str | None, region: str = "AU") -> NormResult:
    text = (raw or "").strip()
    if not text:
        return NormResult(False, None, raw or "")
    try:
        parsed = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return NormResult(False, None, raw or "")
    if phonenumbers.is_valid_number(parsed):
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return NormResult(True, e164, raw or "")
    return NormResult(False, None, raw or "")
