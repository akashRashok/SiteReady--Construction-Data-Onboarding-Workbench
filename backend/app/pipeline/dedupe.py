"""Exact duplicate collapse and fuzzy candidate scoring."""

from __future__ import annotations

from datetime import datetime, timezone

from rapidfuzz import fuzz

from app.models import (
    EntityRecord,
    EntityType,
    FuzzyCandidate,
    FuzzyEvidence,
    IssueRecord,
    Severity,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def collapse_exact_duplicates(
    run_id: str,
    entities: list[EntityRecord],
) -> tuple[list[EntityRecord], list[IssueRecord]]:
    """Exact duplicates already share stable IDs; enrich lineage and emit info events."""
    now = _utcnow()
    issues: list[IssueRecord] = []
    for entity in entities:
        rows = sorted(set(entity.source_rows))
        entity.source_rows = rows
        entity.data["source_rows"] = rows
        count = len(rows)
        entity.data["duplicate_count"] = count
        if count > 1:
            entity.data["duplicate_source_rows"] = rows[1:]
            issues.append(
                IssueRecord(
                    run_id=run_id,
                    rule_id="exact_duplicate_collapse",
                    severity=Severity.INFO,
                    entity_type=entity.entity_type,
                    entity_id=entity.id,
                    source_rows=rows,
                    field=None,
                    raw_value=None,
                    normalised_value=str(count),
                    message=(
                        f"Collapsed {count} exact-duplicate source rows into one "
                        f"{entity.entity_type.value} record"
                    ),
                    import_consequence="Single canonical record retained with full lineage",
                    created_at=now,
                )
            )
    return entities, issues


def _worker_block_key(data: dict) -> str:
    name = (data.get("full_name") or "").lower().strip()
    parts = name.split()
    last = parts[-1] if parts else ""
    return f"{data.get('company_id')}|{last[:1]}"


def score_fuzzy_candidates(
    run_id: str,
    entities: list[EntityRecord],
    name_threshold: float = 80.0,
) -> list[FuzzyCandidate]:
    """Deterministic RapidFuzz candidates with blocking rules. Never auto-merges."""
    candidates: list[FuzzyCandidate] = []
    workers = [e for e in entities if e.entity_type == EntityType.WORKER]
    companies = [e for e in entities if e.entity_type == EntityType.COMPANY]
    certs = [e for e in entities if e.entity_type == EntityType.CERTIFICATION]
    certs_by_worker: dict[str, list[EntityRecord]] = {}
    for c in certs:
        certs_by_worker.setdefault(c.data.get("worker_id", ""), []).append(c)

    # Worker fuzzy: same company block + last-name initial, or high name similarity
    seen_pairs: set[tuple[str, str]] = set()
    for i, a in enumerate(workers):
        for b in workers[i + 1 :]:
            pair = tuple(sorted((a.id, b.id)))
            if pair in seen_pairs:
                continue
            same_company = a.data.get("company_id") == b.data.get("company_id")
            name_sim = float(
                fuzz.token_sort_ratio(
                    a.data.get("full_name") or "",
                    b.data.get("full_name") or "",
                )
            )
            block_match = _worker_block_key(a.data) == _worker_block_key(b.data)
            email_match = bool(
                a.data.get("email")
                and a.data.get("email") == b.data.get("email")
            )
            phone_match = bool(
                a.data.get("phone")
                and a.data.get("phone") == b.data.get("phone")
            )
            a_certs = {c.data.get("cert_number") for c in certs_by_worker.get(a.id, [])}
            b_certs = {c.data.get("cert_number") for c in certs_by_worker.get(b.id, [])}
            cert_overlap = bool(a_certs & b_certs - {None, ""})

            conflicting: list[str] = []
            if a.data.get("email") and b.data.get("email") and not email_match:
                conflicting.append("email")
            if a.data.get("phone") and b.data.get("phone") and not phone_match:
                conflicting.append("phone")
            if a.data.get("trade") != b.data.get("trade"):
                conflicting.append("trade")

            should_surface = (
                (same_company and name_sim >= name_threshold)
                or (block_match and name_sim >= name_threshold)
                or email_match
                or phone_match
                or (cert_overlap and name_sim >= 70)
            )
            if not should_surface:
                continue

            seen_pairs.add(pair)
            score = name_sim
            if email_match:
                score = max(score, 95.0)
            if phone_match:
                score = max(score, 92.0)
            notes = []
            if same_company:
                notes.append("Same company")
            if email_match:
                notes.append("Matching email")
            if phone_match:
                notes.append("Matching phone")
            if cert_overlap:
                notes.append("Overlapping certification number")

            candidates.append(
                FuzzyCandidate(
                    entity_type=EntityType.WORKER,
                    entity_id_a=a.id,
                    entity_id_b=b.id,
                    score=round(score, 2),
                    evidence=FuzzyEvidence(
                        name_similarity=round(name_sim, 2),
                        same_company=same_company,
                        matching_email=email_match,
                        matching_phone=phone_match,
                        matching_cert_number=cert_overlap,
                        conflicting_fields=conflicting,
                        notes=notes,
                    ),
                )
            )

    # Company fuzzy: canonical name similarity / ABN
    seen_co: set[tuple[str, str]] = set()
    for i, a in enumerate(companies):
        for b in companies[i + 1 :]:
            pair = tuple(sorted((a.id, b.id)))
            if pair in seen_co:
                continue
            name_sim = float(
                fuzz.token_sort_ratio(
                    a.data.get("canonical_name") or "",
                    b.data.get("canonical_name") or "",
                )
            )
            abn_match = bool(a.data.get("abn") and a.data.get("abn") == b.data.get("abn"))
            conflicting: list[str] = []
            if a.data.get("abn") and b.data.get("abn") and not abn_match:
                conflicting.append("abn")
            if name_sim < 85 and not abn_match:
                continue
            seen_co.add(pair)
            notes = []
            if name_sim >= 85:
                notes.append("Similar canonical company name")
            if abn_match:
                notes.append("Matching ABN")
            if (
                a.data.get("company_name", "").lower() != b.data.get("company_name", "").lower()
                and name_sim >= 85
            ):
                notes.append("Legal suffix or punctuation difference likely")
            candidates.append(
                FuzzyCandidate(
                    entity_type=EntityType.COMPANY,
                    entity_id_a=a.id,
                    entity_id_b=b.id,
                    score=round(100.0 if abn_match else name_sim, 2),
                    evidence=FuzzyEvidence(
                        name_similarity=round(name_sim, 2),
                        matching_abn=abn_match,
                        conflicting_fields=conflicting,
                        notes=notes,
                    ),
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
