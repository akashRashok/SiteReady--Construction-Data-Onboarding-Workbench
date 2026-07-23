"""Column profiling and mapping proposals."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models import (
    ColumnMapping,
    EntityType,
    MappingConfidence,
    MappingMethod,
)

# Exact header matches and aliases -> (entity, field)
HEADER_ALIASES: dict[str, tuple[EntityType, str]] = {
    "company name": (EntityType.COMPANY, "company_name"),
    "company": (EntityType.COMPANY, "company_name"),
    "employer": (EntityType.COMPANY, "company_name"),
    "org name": (EntityType.COMPANY, "company_name"),
    "organisation": (EntityType.COMPANY, "company_name"),
    "organization": (EntityType.COMPANY, "company_name"),
    "abn": (EntityType.COMPANY, "abn"),
    "australian business number": (EntityType.COMPANY, "abn"),
    "company abn": (EntityType.COMPANY, "abn"),
    "role": (EntityType.COMPANY, "role"),
    "company role": (EntityType.COMPANY, "role"),
    "contractor type": (EntityType.COMPANY, "role"),
    "worker name": (EntityType.WORKER, "full_name"),
    "full name": (EntityType.WORKER, "full_name"),
    "name": (EntityType.WORKER, "full_name"),
    "employee name": (EntityType.WORKER, "full_name"),
    "trade": (EntityType.WORKER, "trade"),
    "trade type": (EntityType.WORKER, "trade"),
    "occupation": (EntityType.WORKER, "trade"),
    "email": (EntityType.WORKER, "email"),
    "email address": (EntityType.WORKER, "email"),
    "worker email": (EntityType.WORKER, "email"),
    "phone": (EntityType.WORKER, "phone"),
    "mobile": (EntityType.WORKER, "phone"),
    "phone number": (EntityType.WORKER, "phone"),
    "contact number": (EntityType.WORKER, "phone"),
    "cert type": (EntityType.CERTIFICATION, "cert_type"),
    "certification type": (EntityType.CERTIFICATION, "cert_type"),
    "certificate type": (EntityType.CERTIFICATION, "cert_type"),
    "licence type": (EntityType.CERTIFICATION, "cert_type"),
    "license type": (EntityType.CERTIFICATION, "cert_type"),
    "cert number": (EntityType.CERTIFICATION, "cert_number"),
    "certification number": (EntityType.CERTIFICATION, "cert_number"),
    "certificate number": (EntityType.CERTIFICATION, "cert_number"),
    "licence number": (EntityType.CERTIFICATION, "cert_number"),
    "license number": (EntityType.CERTIFICATION, "cert_number"),
    "issue date": (EntityType.CERTIFICATION, "issue_date"),
    "date issued": (EntityType.CERTIFICATION, "issue_date"),
    "issued": (EntityType.CERTIFICATION, "issue_date"),
    "expiry date": (EntityType.CERTIFICATION, "expiry_date"),
    "expiry": (EntityType.CERTIFICATION, "expiry_date"),
    "expires": (EntityType.CERTIFICATION, "expiry_date"),
    "expiration date": (EntityType.CERTIFICATION, "expiry_date"),
}

EXACT_HEADERS: dict[str, tuple[EntityType, str]] = {
    "company_name": (EntityType.COMPANY, "company_name"),
    "abn": (EntityType.COMPANY, "abn"),
    "role": (EntityType.COMPANY, "role"),
    "full_name": (EntityType.WORKER, "full_name"),
    "trade": (EntityType.WORKER, "trade"),
    "email": (EntityType.WORKER, "email"),
    "phone": (EntityType.WORKER, "phone"),
    "cert_type": (EntityType.CERTIFICATION, "cert_type"),
    "cert_number": (EntityType.CERTIFICATION, "cert_number"),
    "issue_date": (EntityType.CERTIFICATION, "issue_date"),
    "expiry_date": (EntityType.CERTIFICATION, "expiry_date"),
}


def _samples(values: list[str], n: int = 3) -> list[str]:
    out: list[str] = []
    for v in values:
        if v and v not in out:
            out.append(v)
        if len(out) >= n:
            break
    return out


def _heuristic_guess(header: str, samples: list[str]) -> tuple[EntityType, str, MappingConfidence] | None:
    lower = header.lower()
    joined = " ".join(samples).lower()
    if "abn" in lower or (all(s.replace(" ", "").isdigit() and len(s.replace(" ", "")) == 11 for s in samples if s)):
        return EntityType.COMPANY, "abn", MappingConfidence.MEDIUM
    if "@" in joined:
        return EntityType.WORKER, "email", MappingConfidence.MEDIUM
    if any(tok in lower for tok in ("phone", "mobile", "tel")):
        return EntityType.WORKER, "phone", MappingConfidence.LOW
    if any(tok in lower for tok in ("expir", "expiry")):
        return EntityType.CERTIFICATION, "expiry_date", MappingConfidence.LOW
    if "issue" in lower and "date" in lower:
        return EntityType.CERTIFICATION, "issue_date", MappingConfidence.LOW
    if any(tok in lower for tok in ("cert", "licence", "license")) and any(
        tok in lower for tok in ("num", "no", "#")
    ):
        return EntityType.CERTIFICATION, "cert_number", MappingConfidence.LOW
    if any(tok in lower for tok in ("cert", "licence", "license", "card")):
        return EntityType.CERTIFICATION, "cert_type", MappingConfidence.LOW
    if any(tok in lower for tok in ("worker", "employee", "person")) and "name" in lower:
        return EntityType.WORKER, "full_name", MappingConfidence.LOW
    if "trade" in lower or "occupation" in lower:
        return EntityType.WORKER, "trade", MappingConfidence.LOW
    if any(tok in lower for tok in ("company", "employer", "org")):
        return EntityType.COMPANY, "company_name", MappingConfidence.LOW
    return None


def profile_columns(
    headers: list[str],
    source_rows: list[dict[str, Any]],
) -> list[ColumnMapping]:
    column_values: dict[str, list[str]] = defaultdict(list)
    for row in source_rows:
        for h in headers:
            val = row.get(h)
            if val is None:
                continue
            text = str(val).strip()
            if text and h in column_values or text:
                column_values[h].append(text)

    mappings: list[ColumnMapping] = []
    for header in headers:
        samples = _samples(column_values.get(header, []))
        key = header.strip().lower()
        normalised_key = key.replace(" ", "_")

        if normalised_key in EXACT_HEADERS:
            entity, field = EXACT_HEADERS[normalised_key]
            mappings.append(
                ColumnMapping(
                    source_column=header,
                    target_entity=entity,
                    target_field=field,
                    method=MappingMethod.EXACT_HEADER,
                    confidence=MappingConfidence.HIGH,
                    sample_values=samples,
                    confirmed=True,
                )
            )
            continue

        if key in HEADER_ALIASES:
            entity, field = HEADER_ALIASES[key]
            mappings.append(
                ColumnMapping(
                    source_column=header,
                    target_entity=entity,
                    target_field=field,
                    method=MappingMethod.ALIAS_DICTIONARY,
                    confidence=MappingConfidence.HIGH,
                    sample_values=samples,
                    confirmed=True,
                )
            )
            continue

        guess = _heuristic_guess(header, samples)
        if guess:
            entity, field, confidence = guess
            mappings.append(
                ColumnMapping(
                    source_column=header,
                    target_entity=entity,
                    target_field=field,
                    method=MappingMethod.HEURISTIC,
                    confidence=confidence,
                    sample_values=samples,
                    confirmed=confidence != MappingConfidence.LOW,
                )
            )
        else:
            mappings.append(
                ColumnMapping(
                    source_column=header,
                    target_entity=None,
                    target_field=None,
                    method=MappingMethod.UNMAPPED,
                    confidence=MappingConfidence.LOW,
                    sample_values=samples,
                    confirmed=False,
                )
            )
    return mappings


def mappings_ready(mappings: list[ColumnMapping]) -> bool:
    """Low-confidence mappings must be confirmed before processing."""
    for m in mappings:
        if m.confidence == MappingConfidence.LOW and not m.confirmed:
            return False
        if m.method == MappingMethod.UNMAPPED and not m.confirmed:
            # Unmapped may be confirmed as intentionally ignored
            return False
    return True
