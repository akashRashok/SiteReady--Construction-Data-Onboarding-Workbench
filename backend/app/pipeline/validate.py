"""Deterministic validation rules (section 11)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models import EntityRecord, EntityType, IssueRecord, ReviewStatus, Severity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _issue(
    run_id: str,
    rule_id: str,
    severity: Severity,
    entity: EntityRecord,
    field: str | None,
    raw_value: str | None,
    normalised_value: str | None,
    message: str,
    consequence: str,
    now: datetime,
) -> IssueRecord:
    return IssueRecord(
        run_id=run_id,
        rule_id=rule_id,
        severity=severity,
        entity_type=entity.entity_type,
        entity_id=entity.id,
        source_rows=entity.source_rows,
        field=field,
        raw_value=raw_value,
        normalised_value=normalised_value,
        message=message,
        import_consequence=consequence,
        created_at=now,
    )


def validate_entities(
    run_id: str,
    entities: list[EntityRecord],
    reference_date: date,
) -> tuple[list[EntityRecord], list[IssueRecord]]:
    now = _utcnow()
    issues: list[IssueRecord] = []
    by_id = {e.id: e for e in entities}
    companies = {e.id: e for e in entities if e.entity_type == EntityType.COMPANY}
    workers = {e.id: e for e in entities if e.entity_type == EntityType.WORKER}

    for entity in entities:
        data = entity.data

        if entity.entity_type == EntityType.COMPANY:
            if not data.get("company_name"):
                issues.append(
                    _issue(
                        run_id,
                        "missing_company_name",
                        Severity.ERROR,
                        entity,
                        "company_name",
                        None,
                        None,
                        "Missing company name",
                        "Excluded unless overridden",
                        now,
                    )
                )
            if data.get("abn_error"):
                issues.append(
                    _issue(
                        run_id,
                        "invalid_abn",
                        Severity.ERROR,
                        entity,
                        "abn",
                        data.get("raw_abn"),
                        None,
                        f"Invalid ABN: {data['abn_error']}",
                        "ABN nullified; excluded unless overridden",
                        now,
                    )
                )

        if entity.entity_type == EntityType.WORKER:
            if not data.get("full_name"):
                issues.append(
                    _issue(
                        run_id,
                        "missing_worker_name",
                        Severity.ERROR,
                        entity,
                        "full_name",
                        None,
                        None,
                        "Missing worker name",
                        "Excluded unless overridden",
                        now,
                    )
                )
            company_id = data.get("company_id")
            if not company_id or company_id not in companies:
                issues.append(
                    _issue(
                        run_id,
                        "missing_company_link",
                        Severity.ERROR,
                        entity,
                        "company_id",
                        company_id,
                        None,
                        "Worker references no canonical company",
                        "Excluded unless overridden",
                        now,
                    )
                )
            if data.get("email_error"):
                issues.append(
                    _issue(
                        run_id,
                        "invalid_email",
                        Severity.WARNING,
                        entity,
                        "email",
                        data.get("raw_email"),
                        None,
                        f"Invalid email: {data['email_error']}",
                        "Email set to null; eligible for approval",
                        now,
                    )
                )
            if data.get("phone_error"):
                issues.append(
                    _issue(
                        run_id,
                        "invalid_phone",
                        Severity.WARNING,
                        entity,
                        "phone",
                        data.get("raw_phone"),
                        None,
                        f"Invalid phone: {data['phone_error']}",
                        "Phone set to null; eligible for approval",
                        now,
                    )
                )
            if data.get("raw_trade") and not data.get("trade_known"):
                issues.append(
                    _issue(
                        run_id,
                        "unknown_trade",
                        Severity.WARNING,
                        entity,
                        "trade",
                        data.get("raw_trade"),
                        "other",
                        f"Unknown trade '{data.get('raw_trade')}' mapped to other",
                        "Canonical value set to other; eligible for approval",
                        now,
                    )
                )

        if entity.entity_type == EntityType.CERTIFICATION:
            if not data.get("cert_number"):
                issues.append(
                    _issue(
                        run_id,
                        "missing_cert_number",
                        Severity.ERROR,
                        entity,
                        "cert_number",
                        None,
                        None,
                        "Missing certification number",
                        "Excluded unless overridden",
                        now,
                    )
                )
            worker_id = data.get("worker_id")
            if not worker_id or worker_id not in workers:
                issues.append(
                    _issue(
                        run_id,
                        "missing_worker_link",
                        Severity.ERROR,
                        entity,
                        "worker_id",
                        worker_id,
                        None,
                        "Certification references no canonical worker",
                        "Excluded unless overridden",
                        now,
                    )
                )
            if data.get("issue_error"):
                rule = (
                    "ambiguous_date"
                    if "Ambiguous" in str(data["issue_error"])
                    else "unparseable_date"
                )
                issues.append(
                    _issue(
                        run_id,
                        rule,
                        Severity.ERROR,
                        entity,
                        "issue_date",
                        data.get("raw_issue_date"),
                        None,
                        data["issue_error"],
                        "Excluded unless overridden",
                        now,
                    )
                )
            if data.get("expiry_error"):
                rule = (
                    "ambiguous_date"
                    if "Ambiguous" in str(data["expiry_error"])
                    else "unparseable_date"
                )
                issues.append(
                    _issue(
                        run_id,
                        rule,
                        Severity.ERROR,
                        entity,
                        "expiry_date",
                        data.get("raw_expiry_date"),
                        None,
                        data["expiry_error"],
                        "Excluded unless overridden",
                        now,
                    )
                )

            parsed_issue = data.get("parsed_issue")
            parsed_expiry = data.get("parsed_expiry")
            if isinstance(parsed_issue, str):
                try:
                    parsed_issue = date.fromisoformat(parsed_issue)
                except ValueError:
                    parsed_issue = None
            if isinstance(parsed_expiry, str):
                try:
                    parsed_expiry = date.fromisoformat(parsed_expiry)
                except ValueError:
                    parsed_expiry = None

            # Prefer ISO fields if parsed_* not present after serialization
            if parsed_issue is None and data.get("issue_date"):
                try:
                    parsed_issue = date.fromisoformat(data["issue_date"])
                except (TypeError, ValueError):
                    parsed_issue = None
            if parsed_expiry is None and data.get("expiry_date"):
                try:
                    parsed_expiry = date.fromisoformat(data["expiry_date"])
                except (TypeError, ValueError):
                    parsed_expiry = None

            if parsed_issue and parsed_issue > reference_date:
                issues.append(
                    _issue(
                        run_id,
                        "future_issue_date",
                        Severity.ERROR,
                        entity,
                        "issue_date",
                        data.get("raw_issue_date"),
                        data.get("issue_date"),
                        f"Issue date {parsed_issue.isoformat()} is after reference date {reference_date.isoformat()}",
                        "Excluded unless overridden",
                        now,
                    )
                )
            if parsed_issue and parsed_expiry and parsed_expiry < parsed_issue:
                issues.append(
                    _issue(
                        run_id,
                        "expiry_before_issue",
                        Severity.ERROR,
                        entity,
                        "expiry_date",
                        data.get("raw_expiry_date"),
                        data.get("expiry_date"),
                        "Expiry date is before issue date",
                        "Excluded unless overridden",
                        now,
                    )
                )
            if parsed_expiry and parsed_expiry < reference_date:
                issues.append(
                    _issue(
                        run_id,
                        "expired_certification",
                        Severity.WARNING,
                        entity,
                        "expiry_date",
                        data.get("raw_expiry_date"),
                        data.get("expiry_date"),
                        f"Certification expired on {parsed_expiry.isoformat()} (reference {reference_date.isoformat()})",
                        "Eligible for approval with warning",
                        now,
                    )
                )
            if data.get("raw_cert_type") and not data.get("cert_known"):
                issues.append(
                    _issue(
                        run_id,
                        "unknown_cert_type",
                        Severity.WARNING,
                        entity,
                        "cert_type",
                        data.get("raw_cert_type"),
                        "other",
                        f"Unknown certification type '{data.get('raw_cert_type')}' mapped to other",
                        "Canonical value set to other; eligible for approval",
                        now,
                    )
                )

    # Mark entities with unresolved errors as still pending (exclusion decided at export)
    error_entities = {
        i.entity_id
        for i in issues
        if i.severity == Severity.ERROR and i.entity_id
    }
    for entity in entities:
        if entity.id in error_entities:
            # Keep pending_review; export/approval rules enforce override
            entity.data["has_errors"] = True
        else:
            entity.data["has_errors"] = False
        # Remove non-serialisable date objects from data before persistence
        for key in ("parsed_issue", "parsed_expiry"):
            val = entity.data.get(key)
            if isinstance(val, date):
                entity.data[key] = val.isoformat()

    return entities, issues
