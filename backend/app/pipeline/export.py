"""Export generation and exception reporting."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import (
    DecisionRecord,
    EntityRecord,
    EntityType,
    ImportRun,
    IssueRecord,
    ReviewStatus,
    Severity,
)

COMPANY_FIELDS = ["id", "company_name", "canonical_name", "abn", "role", "review_status", "source_rows"]
WORKER_FIELDS = ["id", "full_name", "trade", "email", "phone", "company_id", "review_status", "source_rows"]
CERT_FIELDS = [
    "id",
    "worker_id",
    "cert_type",
    "cert_number",
    "issue_date",
    "expiry_date",
    "review_status",
    "source_rows",
]

EXPORTABLE = {ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_OVERRIDE}
BLOCKED_PARENT = {ReviewStatus.REJECTED, ReviewStatus.EXCLUDED_BY_RULE}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def pending_entities(entities: list[EntityRecord]) -> list[EntityRecord]:
    return [e for e in entities if e.review_status == ReviewStatus.PENDING_REVIEW]


def export_row_for(entity: EntityRecord) -> dict[str, Any]:
    data = entity.data
    if entity.entity_type == EntityType.COMPANY:
        fields = COMPANY_FIELDS
    elif entity.entity_type == EntityType.WORKER:
        fields = WORKER_FIELDS
    else:
        fields = CERT_FIELDS
    row: dict[str, Any] = {}
    for f in fields:
        val = data.get(f, getattr(entity, f, None) if f == "id" else data.get(f))
        if f == "id":
            val = entity.id
        if f == "review_status":
            val = entity.review_status.value
        if f == "source_rows":
            val = "|".join(str(n) for n in entity.source_rows)
        row[f] = "" if val is None else val
    return row


def exclusion_reasons(
    entity: EntityRecord,
    entities_by_id: dict[str, EntityRecord],
    issues: list[IssueRecord],
) -> list[str]:
    reasons: list[str] = []
    if entity.review_status == ReviewStatus.REJECTED:
        reasons.append("Rejected by human decision")
    if entity.review_status == ReviewStatus.EXCLUDED_BY_RULE:
        reasons.append("Excluded by validation rule")
    if entity.review_status == ReviewStatus.PENDING_REVIEW:
        reasons.append("Still pending review")

    entity_errors = [
        i
        for i in issues
        if i.entity_id == entity.id and i.severity == Severity.ERROR
    ]
    if entity.review_status not in EXPORTABLE:
        for err in entity_errors:
            reasons.append(f"{err.rule_id}: {err.message}")

    # Parent blocking
    if entity.entity_type == EntityType.WORKER:
        parent = entities_by_id.get(entity.data.get("company_id", ""))
        if parent and parent.review_status in BLOCKED_PARENT:
            reasons.append(
                f"Parent company {parent.id} is {parent.review_status.value}"
            )
    if entity.entity_type == EntityType.CERTIFICATION:
        parent = entities_by_id.get(entity.data.get("worker_id", ""))
        if parent and parent.review_status in BLOCKED_PARENT:
            reasons.append(
                f"Parent worker {parent.id} is {parent.review_status.value}"
            )
        elif parent:
            grand = entities_by_id.get(parent.data.get("company_id", ""))
            if grand and grand.review_status in BLOCKED_PARENT:
                reasons.append(
                    f"Ancestor company {grand.id} is {grand.review_status.value}"
                )
            if parent.review_status not in EXPORTABLE:
                # If worker not exportable for other reasons, block cert
                if parent.review_status == ReviewStatus.REJECTED:
                    reasons.append(f"Parent worker {parent.id} is rejected")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    if not unique:
        unique.append("Not approved for import")
    return unique


def is_import_ready(
    entity: EntityRecord,
    entities_by_id: dict[str, EntityRecord],
) -> bool:
    if entity.review_status not in EXPORTABLE:
        return False
    if entity.entity_type == EntityType.WORKER:
        parent = entities_by_id.get(entity.data.get("company_id", ""))
        if not parent or parent.review_status not in EXPORTABLE:
            return False
    if entity.entity_type == EntityType.CERTIFICATION:
        parent = entities_by_id.get(entity.data.get("worker_id", ""))
        if not parent or parent.review_status not in EXPORTABLE:
            return False
        grand = entities_by_id.get(parent.data.get("company_id", ""))
        if not grand or grand.review_status not in EXPORTABLE:
            return False
    return True


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_exception_report(
    run: ImportRun,
    entities: list[EntityRecord],
    issues: list[IssueRecord],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.rule_id] = counts.get(issue.rule_id, 0) + 1
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_severity[issue.severity.value] = by_severity.get(issue.severity.value, 0) + 1

    return {
        "disclaimer": "Independent demo. Synthetic data.",
        "run_id": run.id,
        "run_name": run.name,
        "reference_date": run.reference_date.isoformat(),
        "status": run.status.value,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "entity_counts": {
            "company": sum(1 for e in entities if e.entity_type == EntityType.COMPANY),
            "worker": sum(1 for e in entities if e.entity_type == EntityType.WORKER),
            "certification": sum(
                1 for e in entities if e.entity_type == EntityType.CERTIFICATION
            ),
        },
        "issue_counts_by_rule": counts,
        "issue_counts_by_severity": by_severity,
        "issues": [i.model_dump(mode="json") for i in issues],
    }


def exception_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Exception Report",
        "",
        "> Independent demo. Synthetic data.",
        "",
        f"- Run: `{report['run_id']}` ({report['run_name']})",
        f"- Reference date: {report['reference_date']}",
        f"- Provider: {report.get('llm_provider') or 'n/a'} / {report.get('llm_model') or 'n/a'}",
        "",
        "## Entity counts",
        "",
    ]
    for k, v in report["entity_counts"].items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Issues by severity", ""])
    for k, v in report["issue_counts_by_severity"].items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Issues by rule", ""])
    for k, v in sorted(report["issue_counts_by_rule"].items()):
        lines.append(f"- `{k}`: {v}")
    lines.extend(
        [
            "",
            "---",
            f"Generated at {_utcnow().isoformat()}. Counts are deterministic.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_audit_log(
    run: ImportRun,
    entities: list[EntityRecord],
    issues: list[IssueRecord],
    decisions: list[DecisionRecord],
) -> dict[str, Any]:
    return {
        "disclaimer": "Independent demo. Synthetic data.",
        "run": run.model_dump(mode="json"),
        "entities": [e.model_dump(mode="json") for e in entities],
        "issues": [i.model_dump(mode="json") for i in issues],
        "decisions": [d.model_dump(mode="json") for d in decisions],
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
    }


def generate_exports(
    run: ImportRun,
    entities: list[EntityRecord],
    issues: list[IssueRecord],
    decisions: list[DecisionRecord],
    output_dir: Path,
    implementation_summary: str | None = None,
) -> dict[str, str]:
    """Write all artifacts. Returns relative path map."""
    run_dir = output_dir / run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    by_id = {e.id: e for e in entities}

    type_fields = {
        EntityType.COMPANY: COMPANY_FIELDS,
        EntityType.WORKER: WORKER_FIELDS,
        EntityType.CERTIFICATION: CERT_FIELDS,
    }
    type_names = {
        EntityType.COMPANY: "companies",
        EntityType.WORKER: "workers",
        EntityType.CERTIFICATION: "certifications",
    }

    paths: dict[str, str] = {}
    for etype, fields in type_fields.items():
        ready_rows: list[dict[str, Any]] = []
        excluded_rows: list[dict[str, Any]] = []
        for entity in entities:
            if entity.entity_type != etype:
                continue
            row = export_row_for(entity)
            if is_import_ready(entity, by_id):
                ready_rows.append(row)
            else:
                reasons = exclusion_reasons(entity, by_id, issues)
                excluded = dict(row)
                excluded["exclusion_reasons"] = " | ".join(reasons)
                excluded_rows.append(excluded)

        name = type_names[etype]
        ready_name = f"{name}_import_ready.csv"
        excl_name = f"{name}_excluded.csv"
        write_csv(run_dir / ready_name, fields, ready_rows)
        write_csv(run_dir / excl_name, fields + ["exclusion_reasons"], excluded_rows)
        paths[ready_name] = f"{run.id}/{ready_name}"
        paths[excl_name] = f"{run.id}/{excl_name}"

    report = build_exception_report(run, entities, issues)
    (run_dir / "exception_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (run_dir / "exception_report.md").write_text(
        exception_report_markdown(report), encoding="utf-8"
    )
    paths["exception_report.json"] = f"{run.id}/exception_report.json"
    paths["exception_report.md"] = f"{run.id}/exception_report.md"

    audit = build_audit_log(run, entities, issues, decisions)
    (run_dir / "audit_log.json").write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8"
    )
    paths["audit_log.json"] = f"{run.id}/audit_log.json"

    summary = implementation_summary or _deterministic_summary(run, entities, issues, decisions, by_id)
    (run_dir / "implementation_summary.md").write_text(summary, encoding="utf-8")
    paths["implementation_summary.md"] = f"{run.id}/implementation_summary.md"

    return paths


def _deterministic_summary(
    run: ImportRun,
    entities: list[EntityRecord],
    issues: list[IssueRecord],
    decisions: list[DecisionRecord],
    by_id: dict[str, EntityRecord],
) -> str:
    ready = sum(1 for e in entities if is_import_ready(e, by_id))
    excluded = len(entities) - ready
    error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)
    lines = [
        "# Implementation Summary",
        "",
        "> Independent demo. Synthetic data.",
        "",
        f"This note summarises onboarding run **{run.name}** "
        f"(reference date {run.reference_date.isoformat()}).",
        "",
        "## Counts (deterministic)",
        "",
        f"- Entities processed: {len(entities)}",
        f"- Import-ready: {ready}",
        f"- Excluded: {excluded}",
        f"- Validation errors: {error_count}",
        f"- Validation warnings: {warning_count}",
        f"- Human decisions recorded: {len(decisions)}",
        "",
        "## Notes",
        "",
        "AI drafting was skipped or unavailable; this template was generated "
        "deterministically from structured pipeline results.",
        "",
        "---",
        f"Provider: {run.llm_provider or 'none'} / Model: {run.llm_model or 'none'}",
    ]
    return "\n".join(lines) + "\n"
