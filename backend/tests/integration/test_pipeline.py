"""Integration tests for repository and full pipeline services."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.llm import FallbackAdapter
from app.models import DecisionRequest, DecisionType, MappingConfidence, ReviewStatus
from app.repository.sqlite import SqliteRepository
from app.services import ServiceError, WorkbenchService


@pytest.fixture
def service(tmp_path: Path, project_root: Path) -> WorkbenchService:
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        upload_dir=str(tmp_path / "uploads"),
        output_dir=str(tmp_path / "outputs"),
        llm_provider="fallback",
        llm_model="deterministic-fallback",
        schema_version="1",
    )
    # Point schema to real schema.sql
    repo = SqliteRepository(
        db_path=tmp_path / "test.db",
        schema_path=project_root / "backend" / "schema.sql",
        expected_version="1",
    )
    return WorkbenchService(
        repo=repo,
        settings=settings,
        llm_adapter=FallbackAdapter(),
    )


def test_create_and_get_run(service: WorkbenchService):
    run = service.create_run("Test Run", date(2026, 7, 15))
    fetched = service.get_run(run.id)
    assert fetched.name == "Test Run"
    assert fetched.status.value == "created"
    assert fetched.reference_date == date(2026, 7, 15)


def test_upload_process_decide_export(
    service: WorkbenchService,
    fixtures_dir: Path,
):
    run = service.create_run("Fixture Run", date(2026, 7, 15))
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()
    run = service.upload_csv(run.id, "messy_construction_records.csv", content)
    assert run.mappings
    assert run.status.value in {"mapping_pending", "ingested"}

    # Confirm all mappings
    for m in run.mappings:
        m.confirmed = True
    run = service.confirm_mappings(run.id, run.mappings)
    run = service.process(run.id)
    assert run.status.value == "review_pending"

    entities = service.get_entities(run.id)
    issues = service.get_issues(run.id)
    assert entities
    assert issues

    rule_ids = {i.rule_id for i in issues}
    for required in [
        "invalid_abn",
        "unparseable_date",
        "ambiguous_date",
        "expired_certification",
        "invalid_email",
        "invalid_phone",
        "missing_cert_number",
        "exact_duplicate_collapse",
        "unknown_cert_type",
        "future_issue_date",
        "expiry_before_issue",
        "missing_worker_name",
    ]:
        assert required in rule_ids, f"Missing rule {required} in {sorted(rule_ids)}"

    # Resolve fuzzy candidates
    decisions = []
    for cand in run.fuzzy_candidates or []:
        decisions.append(
            DecisionRequest(
                entity_id=cand.entity_id_a,
                decision=DecisionType.KEEP_SEPARATE,
                related_entity_id=cand.entity_id_b,
            )
        )

    # Approve or override entities
    for entity in entities:
        errs = [
            i
            for i in issues
            if i.entity_id == entity.id and i.severity.value == "error"
        ]
        if errs:
            decisions.append(
                DecisionRequest(
                    entity_id=entity.id,
                    decision=DecisionType.OVERRIDE,
                    reason="Demo override with documented reason",
                )
            )
        else:
            decisions.append(
                DecisionRequest(entity_id=entity.id, decision=DecisionType.APPROVE)
            )

    service.apply_decisions(run.id, decisions)

    # Reject one company to verify child blocking — pick a clean company if possible
    companies = [e for e in service.get_entities(run.id) if e.entity_type.value == "company"]
    # Re-fetch after decisions; reject Harbour if present
    target = next(
        (c for c in companies if "Harbour" in c.data.get("company_name", "")),
        companies[0],
    )
    service.apply_decisions(
        run.id,
        [
            DecisionRequest(
                entity_id=target.id,
                decision=DecisionType.REJECT,
                reason="Customer asked to exclude",
            )
        ],
    )

    # Ensure no pending
    remaining = [
        e
        for e in service.get_entities(run.id)
        if e.review_status == ReviewStatus.PENDING_REVIEW
    ]
    assert not remaining

    # Unresolved fuzzy should be cleared
    run = service.get_run(run.id)
    assert all(c.resolution for c in (run.fuzzy_candidates or []))

    run = service.export(run.id)
    assert run.status.value == "exported"
    assert "workers_import_ready.csv" in run.artifact_paths
    assert "workers_excluded.csv" in run.artifact_paths

    # CSV headers on row one
    ready = Path(service.settings.output_path) / run.artifact_paths["companies_import_ready.csv"]
    first_line = ready.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("id,")
    assert "Independent demo" not in first_line

    # Parent rejection should appear in excluded children
    excl = (
        Path(service.settings.output_path) / run.artifact_paths["workers_excluded.csv"]
    ).read_text(encoding="utf-8")
    assert "rejected" in excl.lower() or target.id in excl

    audit = service.get_audit(run.id, entities[0].id)
    assert audit.source_rows


def test_export_refuses_pending(service: WorkbenchService, fixtures_dir: Path):
    run = service.create_run("Pending Run", date(2026, 7, 15))
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()
    run = service.upload_csv(run.id, "messy.csv", content)
    for m in run.mappings or []:
        m.confirmed = True
    service.confirm_mappings(run.id, run.mappings or [])
    service.process(run.id)
    with pytest.raises(ServiceError) as exc:
        service.export(run.id)
    assert "pending_review" in exc.value.message


def test_override_requires_reason(service: WorkbenchService, fixtures_dir: Path):
    run = service.create_run("Override Run", date(2026, 7, 15))
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()
    run = service.upload_csv(run.id, "messy.csv", content)
    for m in run.mappings or []:
        m.confirmed = True
    service.confirm_mappings(run.id, run.mappings or [])
    service.process(run.id)
    entities = service.get_entities(run.id)
    issues = service.get_issues(run.id)
    errored = next(
        e
        for e in entities
        if any(i.entity_id == e.id and i.severity.value == "error" for i in issues)
    )
    with pytest.raises(ServiceError):
        service.apply_decisions(
            run.id,
            [DecisionRequest(entity_id=errored.id, decision=DecisionType.OVERRIDE)],
        )


def test_delete_run_removes_artifacts(service: WorkbenchService, fixtures_dir: Path):
    run = service.create_run("Delete Run", date(2026, 7, 15))
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()
    service.upload_csv(run.id, "messy.csv", content)
    upload_dir = Path(service.settings.upload_path) / run.id
    assert upload_dir.exists()
    service.delete_run(run.id)
    assert service.repo.get_run(run.id) is None
    assert not upload_dir.exists()


def test_rerun_stable_ids(service: WorkbenchService, fixtures_dir: Path):
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()

    def run_once() -> set[str]:
        run = service.create_run("ID Run", date(2026, 7, 15))
        run = service.upload_csv(run.id, "messy.csv", content)
        for m in run.mappings or []:
            m.confirmed = True
        service.confirm_mappings(run.id, run.mappings or [])
        service.process(run.id)
        return {e.id for e in service.get_entities(run.id)}

    assert run_once() == run_once()
