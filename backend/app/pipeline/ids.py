"""Stable deterministic ID generation."""

from __future__ import annotations

import hashlib

from app.models import IdConfidence


def _hash_key(parts: list[str]) -> str:
    material = "|".join(parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return digest


def company_id(canonical_name: str, abn: str | None) -> tuple[str, IdConfidence]:
    parts = [canonical_name]
    confidence = IdConfidence.MEDIUM
    if abn:
        parts.append(abn)
        confidence = IdConfidence.HIGH
    elif not canonical_name:
        confidence = IdConfidence.LOW
    return f"co_{_hash_key(parts)}", confidence


def worker_id(
    full_name: str,
    company_id_value: str,
    email: str | None,
) -> tuple[str, IdConfidence]:
    parts = [full_name.lower(), company_id_value]
    confidence = IdConfidence.MEDIUM
    if email:
        parts.append(email.lower())
        confidence = IdConfidence.HIGH
    elif not full_name or not company_id_value:
        confidence = IdConfidence.LOW
    return f"wk_{_hash_key(parts)}", confidence


def certification_id(
    worker_id_value: str,
    cert_type: str,
    cert_number: str,
) -> tuple[str, IdConfidence]:
    normalised_number = cert_number.strip().upper()
    parts = [worker_id_value, cert_type, normalised_number]
    confidence = IdConfidence.HIGH if normalised_number else IdConfidence.LOW
    return f"ct_{_hash_key(parts)}", confidence
