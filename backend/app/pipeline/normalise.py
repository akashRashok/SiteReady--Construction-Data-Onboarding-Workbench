"""Deterministic normalisation helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import phonenumbers
from dateutil import parser as date_parser

from app.models import CertType, CompanyRole, Trade

ABN_WEIGHTS = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

LEGAL_SUFFIXES = (
    r"\bpty\b",
    r"\bltd\b",
    r"\blimited\b",
    r"\bproprietary\b",
    r"\binc\b",
    r"\bincorporated\b",
    r"\bco\b",
    r"\bcompany\b",
    r"\bplc\b",
)

TRADE_ALIASES: dict[str, Trade] = {
    "carpenter": Trade.CARPENTER,
    "chippy": Trade.CARPENTER,
    "electrician": Trade.ELECTRICIAN,
    "sparky": Trade.ELECTRICIAN,
    "plumber": Trade.PLUMBER,
    "concreter": Trade.CONCRETER,
    "concrete": Trade.CONCRETER,
    "steelfixer": Trade.STEELFIXER,
    "steel fixer": Trade.STEELFIXER,
    "crane operator": Trade.CRANE_OPERATOR,
    "crane_operator": Trade.CRANE_OPERATOR,
    "crane": Trade.CRANE_OPERATOR,
    "scaffolder": Trade.SCAFFOLDER,
    "scaffold": Trade.SCAFFOLDER,
    "labourer": Trade.LABOURER,
    "laborer": Trade.LABOURER,
    "site supervisor": Trade.SITE_SUPERVISOR,
    "site_supervisor": Trade.SITE_SUPERVISOR,
    "supervisor": Trade.SITE_SUPERVISOR,
    "traffic controller": Trade.TRAFFIC_CONTROLLER,
    "traffic_controller": Trade.TRAFFIC_CONTROLLER,
    "traffic": Trade.TRAFFIC_CONTROLLER,
    "other": Trade.OTHER,
}

CERT_ALIASES: dict[str, CertType] = {
    "white card": CertType.WHITE_CARD,
    "white_card": CertType.WHITE_CARD,
    "whitecard": CertType.WHITE_CARD,
    "hrwl": CertType.HRWL,
    "high risk work licence": CertType.HRWL,
    "high risk work license": CertType.HRWL,
    "working at heights": CertType.WORKING_AT_HEIGHTS,
    "working_at_heights": CertType.WORKING_AT_HEIGHTS,
    "wah": CertType.WORKING_AT_HEIGHTS,
    "first aid": CertType.FIRST_AID,
    "first_aid": CertType.FIRST_AID,
    "asbestos awareness": CertType.ASBESTOS_AWARENESS,
    "asbestos_awareness": CertType.ASBESTOS_AWARENESS,
    "traffic management": CertType.TRAFFIC_MANAGEMENT,
    "traffic_management": CertType.TRAFFIC_MANAGEMENT,
    "ewp": CertType.EWP,
    "elevated work platform": CertType.EWP,
    "other": CertType.OTHER,
}

ROLE_ALIASES: dict[str, CompanyRole] = {
    "head contractor": CompanyRole.HEAD_CONTRACTOR,
    "head_contractor": CompanyRole.HEAD_CONTRACTOR,
    "principal contractor": CompanyRole.HEAD_CONTRACTOR,
    "gc": CompanyRole.HEAD_CONTRACTOR,
    "subcontractor": CompanyRole.SUBCONTRACTOR,
    "subbie": CompanyRole.SUBCONTRACTOR,
    "sub": CompanyRole.SUBCONTRACTOR,
}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def title_case_name(value: str) -> str:
    return collapse_whitespace(value).title()


def canonical_company_name(value: str) -> str:
    text = collapse_whitespace(value).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    for suffix in LEGAL_SUFFIXES:
        text = re.sub(suffix, " ", text)
    return collapse_whitespace(text)


def validate_abn(raw: str | None) -> tuple[str | None, str | None]:
    """Return (canonical_abn_or_none, error_message_or_none)."""
    if raw is None or str(raw).strip() == "":
        return None, None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) != 11:
        return None, f"ABN must be 11 digits, got {len(digits)}"
    weighted = [int(digits[0]) - 1] + [int(d) for d in digits[1:]]
    total = sum(d * w for d, w in zip(weighted, ABN_WEIGHTS, strict=True))
    if total % 89 != 0:
        return None, "ABN checksum failed"
    return digits, None


def validate_email(raw: str | None) -> tuple[str | None, str | None]:
    if raw is None or str(raw).strip() == "":
        return None, None
    value = collapse_whitespace(str(raw)).lower()
    if not EMAIL_RE.match(value):
        return None, "Invalid email format"
    return value, None


def normalise_phone(raw: str | None, region: str = "AU") -> tuple[str | None, str | None]:
    if raw is None or str(raw).strip() == "":
        return None, None
    text = str(raw).strip()
    try:
        parsed = phonenumbers.parse(text, region)
        if not phonenumbers.is_possible_number(parsed):
            return None, "Phone number not possible"
        if not phonenumbers.is_valid_number(parsed):
            return None, "Phone number not valid"
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164), None
    except phonenumbers.NumberParseException as exc:
        return None, f"Phone parse error: {exc}"


def map_trade(raw: str | None) -> tuple[Trade, bool]:
    """Return (trade, used_alias_or_known). False means unknown -> other."""
    if raw is None or str(raw).strip() == "":
        return Trade.OTHER, False
    key = collapse_whitespace(str(raw)).lower()
    if key in TRADE_ALIASES:
        return TRADE_ALIASES[key], True
    return Trade.OTHER, False


def map_cert_type(raw: str | None) -> tuple[CertType, bool]:
    if raw is None or str(raw).strip() == "":
        return CertType.OTHER, False
    key = collapse_whitespace(str(raw)).lower()
    if key in CERT_ALIASES:
        return CERT_ALIASES[key], True
    return CertType.OTHER, False


def map_role(raw: str | None) -> CompanyRole:
    if raw is None or str(raw).strip() == "":
        return CompanyRole.SUBCONTRACTOR
    key = collapse_whitespace(str(raw)).lower()
    return ROLE_ALIASES.get(key, CompanyRole.SUBCONTRACTOR)


def parse_date_value(raw: str | None) -> tuple[date | None, str | None]:
    """Parse supported date formats. Returns (date, error)."""
    if raw is None or str(raw).strip() == "":
        return None, None
    text = collapse_whitespace(str(raw))

    # ISO first — unambiguous
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), None
    except ValueError:
        pass

    # Slash dates: flag ambiguity when both day and month are plausible
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if slash_match:
        a, b, year = (
            int(slash_match.group(1)),
            int(slash_match.group(2)),
            int(slash_match.group(3)),
        )
        if a <= 12 and b <= 12 and a != b:
            return None, f"Ambiguous date '{text}' (could be DD/MM or MM/DD)"
        try:
            # AU convention DD/MM/YYYY when unambiguous
            return date(year, b, a), None
        except ValueError:
            return None, f"Unparseable date '{text}'"

    slash_match_yy = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", text)
    if slash_match_yy:
        a, b, yy = (
            int(slash_match_yy.group(1)),
            int(slash_match_yy.group(2)),
            int(slash_match_yy.group(3)),
        )
        if a <= 12 and b <= 12 and a != b:
            return None, f"Ambiguous date '{text}' (could be DD/MM or MM/DD)"
        year = 2000 + yy if yy < 70 else 1900 + yy
        try:
            return date(year, b, a), None
        except ValueError:
            return None, f"Unparseable date '{text}'"

    # DD-MMM-YY / DD-MMM-YYYY
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date(), None
        except ValueError:
            continue

    try:
        parsed = date_parser.parse(text, dayfirst=True, yearfirst=False, fuzzy=False)
        return parsed.date(), None
    except (ValueError, OverflowError, TypeError):
        return None, f"Unparseable date '{text}'"


def to_iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None
