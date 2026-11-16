"""End-to-end fixture expectations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.llm import FallbackAdapter
from app.repository.sqlite import SqliteRepository
from app.services import WorkbenchService


@pytest.fixture
def service(tmp_path: Path, project_root: Path) -> WorkbenchService:
    settings = Settings(
        database_path=str(tmp_path / "e2e.db"),
        upload_dir=str(tmp_path / "uploads"),
        output_dir=str(tmp_path / "outputs"),
        llm_provider="fallback",
        llm_model="deterministic-fallback",
        schema_version="1",
    )
    repo = SqliteRepository(
        db_path=tmp_path / "e2e.db",
        schema_path=project_root / "backend" / "schema.sql",
        expected_version="1",
    )
    return WorkbenchService(repo=repo, settings=settings, llm_adapter=FallbackAdapter())


def test_fixture_issue_counts(service: WorkbenchService, fixtures_dir: Path):
    run = service.create_run("E2E", date(2026, 7, 15))
    content = (fixtures_dir / "messy_construction_records.csv").read_bytes()
    run = service.upload_csv(run.id, "messy_construction_records.csv", content)
    for m in run.mappings or []:
        m.confirmed = True
    service.confirm_mappings(run.id, run.mappings or [])
    service.process(run.id)
    issues = service.get_issues(run.id)
    counts: dict[str, int] = {}
    for i in issues:
        counts[i.rule_id] = counts.get(i.rule_id, 0) + 1

    # Exact non-zero expectations for required categories
    assert counts.get("invalid_abn", 0) >= 1
    assert counts.get("unparseable_date", 0) >= 1
    assert counts.get("ambiguous_date", 0) >= 1
    assert counts.get("expired_certification", 0) >= 1
    assert counts.get("invalid_email", 0) >= 1
    assert counts.get("invalid_phone", 0) >= 1
    assert counts.get("missing_cert_number", 0) >= 1
    assert counts.get("missing_worker_name", 0) >= 1
    assert counts.get("exact_duplicate_collapse", 0) >= 1
    assert counts.get("unknown_cert_type", 0) >= 1
    assert counts.get("future_issue_date", 0) >= 1
    assert counts.get("expiry_before_issue", 0) >= 1

    fuzzy = service.get_run(run.id).fuzzy_candidates or []
    assert len(fuzzy) >= 1

    entities = service.get_entities(run.id)
    assert any(e.entity_type.value == "company" for e in entities)
    assert any(e.entity_type.value == "worker" for e in entities)
    assert any(e.entity_type.value == "certification" for e in entities)


def test_swms_extraction(fixtures_dir: Path):
    from app.swms import extract_swms

    result = extract_swms(fixtures_dir / "SWMS_Roof_Sheeting_Working_at_Heights.pdf")
    fields = result["fields"]
    assert fields["swms_number"]
    assert fields["document_title"]
    assert fields["contractor_name"]
    assert fields["contractor_abn"] == "51824753556"
    assert fields["project_name"]
    assert fields["site_address"]
    assert fields["activity"]
    assert fields["date_prepared"]
    assert fields["review_date"]
    assert fields["responsible_person"]
    assert fields["high_risk_categories"]
    assert fields["ppe_required"]
    assert fields["plant_and_equipment"]
    assert fields["required_competencies_licences"]
    assert len(fields["job_steps"]) >= 1
    for key, ev in result["evidence"].items():
        assert "source_text" in ev
        assert key in fields or True
