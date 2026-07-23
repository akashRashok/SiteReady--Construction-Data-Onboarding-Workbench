"""Deterministic enum alias resolution (PRD section 11)."""

from __future__ import annotations

from dataclasses import dataclass

from ...models.enums import CertType, CompanyRole, Trade
from .text import collapse_whitespace

_TRADE_ALIASES: dict[str, Trade] = {
    "carpenter": Trade.CARPENTER,
    "chippy": Trade.CARPENTER,
    "chippie": Trade.CARPENTER,
    "electrician": Trade.ELECTRICIAN,
    "sparky": Trade.ELECTRICIAN,
    "sparkie": Trade.ELECTRICIAN,
    "plumber": Trade.PLUMBER,
    "plumbing": Trade.PLUMBER,
    "concreter": Trade.CONCRETER,
    "concrete": Trade.CONCRETER,
    "concretor": Trade.CONCRETER,
    "steelfixer": Trade.STEELFIXER,
    "steel fixer": Trade.STEELFIXER,
    "rebar": Trade.STEELFIXER,
    "crane operator": Trade.CRANE_OPERATOR,
    "crane": Trade.CRANE_OPERATOR,
    "dogger": Trade.CRANE_OPERATOR,
    "scaffolder": Trade.SCAFFOLDER,
    "scaffold": Trade.SCAFFOLDER,
    "scaffie": Trade.SCAFFOLDER,
    "labourer": Trade.LABOURER,
    "labour": Trade.LABOURER,
    "laborer": Trade.LABOURER,
    "site supervisor": Trade.SITE_SUPERVISOR,
    "supervisor": Trade.SITE_SUPERVISOR,
    "foreman": Trade.SITE_SUPERVISOR,
    "traffic controller": Trade.TRAFFIC_CONTROLLER,
    "traffic control": Trade.TRAFFIC_CONTROLLER,
    "tc": Trade.TRAFFIC_CONTROLLER,
}

_CERT_ALIASES: dict[str, CertType] = {
    "white card": CertType.WHITE_CARD,
    "whitecard": CertType.WHITE_CARD,
    "construction induction": CertType.WHITE_CARD,
    "cic": CertType.WHITE_CARD,
    "hrwl": CertType.HRWL,
    "high risk work licence": CertType.HRWL,
    "high risk work license": CertType.HRWL,
    "working at heights": CertType.WORKING_AT_HEIGHTS,
    "work at heights": CertType.WORKING_AT_HEIGHTS,
    "heights": CertType.WORKING_AT_HEIGHTS,
    "wah": CertType.WORKING_AT_HEIGHTS,
    "first aid": CertType.FIRST_AID,
    "firstaid": CertType.FIRST_AID,
    "cpr": CertType.FIRST_AID,
    "asbestos awareness": CertType.ASBESTOS_AWARENESS,
    "asbestos": CertType.ASBESTOS_AWARENESS,
    "traffic management": CertType.TRAFFIC_MANAGEMENT,
    "tmp": CertType.TRAFFIC_MANAGEMENT,
    "ewp": CertType.EWP,
    "elevated work platform": CertType.EWP,
    "boom lift": CertType.EWP,
}

_ROLE_ALIASES: dict[str, CompanyRole] = {
    "head contractor": CompanyRole.HEAD_CONTRACTOR,
    "head": CompanyRole.HEAD_CONTRACTOR,
    "principal": CompanyRole.HEAD_CONTRACTOR,
    "principal contractor": CompanyRole.HEAD_CONTRACTOR,
    "main contractor": CompanyRole.HEAD_CONTRACTOR,
    "builder": CompanyRole.HEAD_CONTRACTOR,
    "subcontractor": CompanyRole.SUBCONTRACTOR,
    "subbie": CompanyRole.SUBCONTRACTOR,
    "sub": CompanyRole.SUBCONTRACTOR,
    "sub contractor": CompanyRole.SUBCONTRACTOR,
    "trade": CompanyRole.SUBCONTRACTOR,
}


@dataclass(frozen=True)
class TradeResult:
    value: Trade
    is_known: bool
    raw: str


@dataclass(frozen=True)
class CertResult:
    value: CertType
    is_known: bool
    raw: str


def _key(value: str | None) -> str:
    return collapse_whitespace(value).lower()


def resolve_trade(raw: str | None) -> TradeResult:
    key = _key(raw)
    if key in _TRADE_ALIASES:
        return TradeResult(_TRADE_ALIASES[key], True, raw or "")
    return TradeResult(Trade.OTHER, False, raw or "")


def resolve_cert_type(raw: str | None) -> CertResult:
    key = _key(raw)
    if key in _CERT_ALIASES:
        return CertResult(_CERT_ALIASES[key], True, raw or "")
    return CertResult(CertType.OTHER, False, raw or "")


def resolve_role(raw: str | None) -> CompanyRole:
    return _ROLE_ALIASES.get(_key(raw), CompanyRole.SUBCONTRACTOR)
