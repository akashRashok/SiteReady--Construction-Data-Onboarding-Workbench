"""Split denormalised rows into canonical entities with normalisation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.models import (
    CertType,
    ColumnMapping,
    EntityRecord,
    EntityType,
    IdConfidence,
    IssueRecord,
    ReviewStatus,
    Severity,
)
from app.pipeline import ids
from app.pipeline.normalise import (
    as_str,
    canonical_company_name,
    collapse_whitespace,
    map_cert_type,
    map_role,
    map_trade,
    normalise_phone,
    parse_date_value,
    title_case_name,
    to_iso_date,
    validate_abn,
    validate_email,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _mapped_value(
    raw: dict[str, Any],
    mappings: list[ColumnMapping],
    entity: EntityType,
    field: str,
) -> str | None:
    for m in mappings:
        if m.target_entity == entity and m.target_field == field and m.source_column in raw:
            return as_str(raw.get(m.source_column))
    return None


def _info_issue(
    run_id: str,
    rule_id: str,
    entity_type: EntityType,
    entity_id: str,
    source_rows: list[int],
    field: str,
    raw_value: str | None,
    normalised_value: str | None,
    message: str,
    now: datetime,
) -> IssueRecord:
    return IssueRecord(
        run_id=run_id,
        rule_id=rule_id,
        severity=Severity.INFO,
        entity_type=entity_type,
        entity_id=entity_id,
        source_rows=source_rows,
        field=field,
        raw_value=raw_value,
        normalised_value=normalised_value,
        message=message,
        import_consequence="Transformation logged; no exclusion",
        created_at=now,
    )


def split_and_normalise(
    run_id: str,
    source_rows: list[dict[str, Any]],
    row_numbers: list[int],
    mappings: list[ColumnMapping],
    reference_date: date,
) -> tuple[list[EntityRecord], list[IssueRecord]]:
    """Derive Company, Worker, Certification entities and transformation issues."""
    now = _utcnow()
    issues: list[IssueRecord] = []

    # Accumulators keyed by stable id
    companies: dict[str, dict[str, Any]] = {}
    workers: dict[str, dict[str, Any]] = {}
    certifications: dict[str, dict[str, Any]] = {}
    company_conf: dict[str, IdConfidence] = {}
    worker_conf: dict[str, IdConfidence] = {}
    cert_conf: dict[str, IdConfidence] = {}

    for raw, row_num in zip(source_rows, row_numbers, strict=True):
        raw_company = _mapped_value(raw, mappings, EntityType.COMPANY, "company_name")
        raw_abn = _mapped_value(raw, mappings, EntityType.COMPANY, "abn")
        raw_role = _mapped_value(raw, mappings, EntityType.COMPANY, "role")
        raw_worker = _mapped_value(raw, mappings, EntityType.WORKER, "full_name")
        raw_trade = _mapped_value(raw, mappings, EntityType.WORKER, "trade")
        raw_email = _mapped_value(raw, mappings, EntityType.WORKER, "email")
        raw_phone = _mapped_value(raw, mappings, EntityType.WORKER, "phone")
        raw_cert_type = _mapped_value(raw, mappings, EntityType.CERTIFICATION, "cert_type")
        raw_cert_number = _mapped_value(raw, mappings, EntityType.CERTIFICATION, "cert_number")
        raw_issue = _mapped_value(raw, mappings, EntityType.CERTIFICATION, "issue_date")
        raw_expiry = _mapped_value(raw, mappings, EntityType.CERTIFICATION, "expiry_date")

        company_name = collapse_whitespace(raw_company) if raw_company else ""
        canon = canonical_company_name(company_name) if company_name else ""
        abn, abn_err = validate_abn(raw_abn)
        role = map_role(raw_role)
        cid, c_conf = ids.company_id(canon or company_name.lower(), abn)

        if cid not in companies:
            companies[cid] = {
                "id": cid,
                "company_name": company_name,
                "canonical_name": canon,
                "abn": abn,
                "role": role.value,
                "review_status": ReviewStatus.PENDING_REVIEW.value,
                "source_rows": [],
                "id_confidence": c_conf.value,
                "raw_abn": raw_abn,
                "abn_error": abn_err,
                "duplicate_source_rows": [],
                "duplicate_count": 1,
            }
            company_conf[cid] = c_conf
            if raw_company and company_name != raw_company:
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_company_name",
                        EntityType.COMPANY,
                        cid,
                        [row_num],
                        "company_name",
                        raw_company,
                        company_name,
                        "Collapsed whitespace in company name",
                        now,
                    )
                )
            if abn and raw_abn and abn != raw_abn.replace(" ", ""):
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_abn",
                        EntityType.COMPANY,
                        cid,
                        [row_num],
                        "abn",
                        raw_abn,
                        abn,
                        "Normalised ABN digits",
                        now,
                    )
                )
        companies[cid]["source_rows"].append(row_num)

        full_name = title_case_name(raw_worker) if raw_worker else ""
        trade, trade_known = map_trade(raw_trade)
        email, email_err = validate_email(raw_email)
        phone, phone_err = normalise_phone(raw_phone)
        wid, w_conf = ids.worker_id(full_name, cid, email)

        if wid not in workers:
            workers[wid] = {
                "id": wid,
                "full_name": full_name,
                "trade": trade.value,
                "email": email,
                "phone": phone,
                "company_id": cid,
                "review_status": ReviewStatus.PENDING_REVIEW.value,
                "source_rows": [],
                "id_confidence": w_conf.value,
                "raw_email": raw_email,
                "email_error": email_err,
                "raw_phone": raw_phone,
                "phone_error": phone_err,
                "raw_trade": raw_trade,
                "trade_known": trade_known,
                "duplicate_source_rows": [],
                "duplicate_count": 1,
            }
            worker_conf[wid] = w_conf
            if raw_worker and full_name != collapse_whitespace(raw_worker):
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_worker_name",
                        EntityType.WORKER,
                        wid,
                        [row_num],
                        "full_name",
                        raw_worker,
                        full_name,
                        "Normalised worker name casing/whitespace",
                        now,
                    )
                )
            if phone and raw_phone and phone != raw_phone:
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_phone",
                        EntityType.WORKER,
                        wid,
                        [row_num],
                        "phone",
                        raw_phone,
                        phone,
                        "Normalised phone to E.164",
                        now,
                    )
                )
            if email and raw_email and email != raw_email.strip().lower():
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_email",
                        EntityType.WORKER,
                        wid,
                        [row_num],
                        "email",
                        raw_email,
                        email,
                        "Normalised email",
                        now,
                    )
                )
            if raw_trade and trade_known and trade.value != collapse_whitespace(raw_trade).lower():
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_trade_alias",
                        EntityType.WORKER,
                        wid,
                        [row_num],
                        "trade",
                        raw_trade,
                        trade.value,
                        f"Mapped trade alias '{raw_trade}' to '{trade.value}'",
                        now,
                    )
                )
        workers[wid]["source_rows"].append(row_num)

        cert_type, cert_known = map_cert_type(raw_cert_type)
        cert_number = collapse_whitespace(raw_cert_number) if raw_cert_number else ""
        issue_date, issue_err = parse_date_value(raw_issue)
        expiry_date, expiry_err = parse_date_value(raw_expiry)
        ctid, ct_conf = ids.certification_id(wid, cert_type.value, cert_number or f"missing:{row_num}")

        if ctid not in certifications:
            certifications[ctid] = {
                "id": ctid,
                "worker_id": wid,
                "cert_type": cert_type.value,
                "cert_number": cert_number,
                "issue_date": to_iso_date(issue_date),
                "expiry_date": to_iso_date(expiry_date),
                "review_status": ReviewStatus.PENDING_REVIEW.value,
                "source_rows": [],
                "id_confidence": ct_conf.value,
                "raw_cert_type": raw_cert_type,
                "cert_known": cert_known,
                "raw_issue_date": raw_issue,
                "issue_error": issue_err,
                "parsed_issue": issue_date,
                "raw_expiry_date": raw_expiry,
                "expiry_error": expiry_err,
                "parsed_expiry": expiry_date,
                "duplicate_source_rows": [],
                "duplicate_count": 1,
            }
            cert_conf[ctid] = ct_conf
            if raw_issue and issue_date and to_iso_date(issue_date) != raw_issue:
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_issue_date",
                        EntityType.CERTIFICATION,
                        ctid,
                        [row_num],
                        "issue_date",
                        raw_issue,
                        to_iso_date(issue_date),
                        "Parsed issue date to ISO",
                        now,
                    )
                )
            if raw_expiry and expiry_date and to_iso_date(expiry_date) != raw_expiry:
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_expiry_date",
                        EntityType.CERTIFICATION,
                        ctid,
                        [row_num],
                        "expiry_date",
                        raw_expiry,
                        to_iso_date(expiry_date),
                        "Parsed expiry date to ISO",
                        now,
                    )
                )
            if raw_cert_type and cert_known and cert_type.value != collapse_whitespace(raw_cert_type).lower().replace(" ", "_"):
                issues.append(
                    _info_issue(
                        run_id,
                        "transform_cert_alias",
                        EntityType.CERTIFICATION,
                        ctid,
                        [row_num],
                        "cert_type",
                        raw_cert_type,
                        cert_type.value,
                        f"Mapped cert alias '{raw_cert_type}' to '{cert_type.value}'",
                        now,
                    )
                )
        certifications[ctid]["source_rows"].append(row_num)

    entities: list[EntityRecord] = []
    for cid, data in companies.items():
        entities.append(
            EntityRecord(
                id=cid,
                run_id=run_id,
                entity_type=EntityType.COMPANY,
                data=data,
                parent_id=None,
                id_confidence=company_conf[cid],
                review_status=ReviewStatus.PENDING_REVIEW,
                source_rows=sorted(set(data["source_rows"])),
                created_at=now,
                updated_at=now,
            )
        )
    for wid, data in workers.items():
        entities.append(
            EntityRecord(
                id=wid,
                run_id=run_id,
                entity_type=EntityType.WORKER,
                data=data,
                parent_id=data["company_id"],
                id_confidence=worker_conf[wid],
                review_status=ReviewStatus.PENDING_REVIEW,
                source_rows=sorted(set(data["source_rows"])),
                created_at=now,
                updated_at=now,
            )
        )
    for ctid, data in certifications.items():
        entities.append(
            EntityRecord(
                id=ctid,
                run_id=run_id,
                entity_type=EntityType.CERTIFICATION,
                data=data,
                parent_id=data["worker_id"],
                id_confidence=cert_conf[ctid],
                review_status=ReviewStatus.PENDING_REVIEW,
                source_rows=sorted(set(data["source_rows"])),
                created_at=now,
                updated_at=now,
            )
        )

    # Attach reference_date for validate stage consumers via issues context only
    _ = reference_date
    return entities, issues
