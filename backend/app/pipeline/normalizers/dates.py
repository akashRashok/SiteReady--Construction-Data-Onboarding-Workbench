"""Deterministic date parsing (PRD section 11).

Supported formats: YYYY-MM-DD, DD/MM/YYYY (day-first), and DD-MMM-YY / DD-MMM-YYYY.
Ambiguous numeric dates (both components 1-12 and unequal) are flagged for a human,
never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class DateStatus(str, Enum):
    VALID = "valid"
    EMPTY = "empty"
    AMBIGUOUS = "ambiguous"
    IMPOSSIBLE = "impossible"
    UNPARSEABLE = "unparseable"


@dataclass(frozen=True)
class DateResult:
    status: DateStatus
    value: date | None
    raw: str

    @property
    def iso(self) -> str | None:
        return self.value.isoformat() if self.value else None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _expand_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year <= 68 else 1900 + year
    return year


def parse_date(raw: str | None) -> DateResult:
    text = (raw or "").strip()
    if not text:
        return DateResult(DateStatus.EMPTY, None, raw or "")

    # ISO: YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        parsed = _safe_date(y, mo, d)
        return DateResult(
            DateStatus.VALID if parsed else DateStatus.IMPOSSIBLE, parsed, text
        )

    # DD-MMM-YY or DD-MMM-YYYY (month name is unambiguous)
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{2,4})", text)
    if m:
        d = int(m.group(1))
        mon = _MONTHS.get(m.group(2).lower())
        y = _expand_year(int(m.group(3)))
        if mon is None:
            return DateResult(DateStatus.UNPARSEABLE, None, text)
        parsed = _safe_date(y, mon, d)
        return DateResult(
            DateStatus.VALID if parsed else DateStatus.IMPOSSIBLE, parsed, text
        )

    # Numeric slash/dash: interpret day-first
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        y = _expand_year(int(m.group(3)))
        # Both plausible as month -> genuinely ambiguous, needs a human.
        if a <= 12 and b <= 12 and a != b:
            return DateResult(DateStatus.AMBIGUOUS, None, text)
        # Day-first canonical interpretation.
        parsed = _safe_date(y, b, a)
        if parsed:
            return DateResult(DateStatus.VALID, parsed, text)
        return DateResult(DateStatus.IMPOSSIBLE, None, text)

    return DateResult(DateStatus.UNPARSEABLE, None, text)
