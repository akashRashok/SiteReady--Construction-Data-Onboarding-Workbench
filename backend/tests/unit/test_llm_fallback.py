"""Unit tests for LLM validation and fallback."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.llm import FallbackAdapter, FuzzyExplanation, deterministic_fuzzy_explanation
from app.models import (
    EntityRecord,
    EntityType,
    FuzzyCandidate,
    FuzzyEvidence,
    IdConfidence,
    ImportRun,
    ReviewStatus,
    RunStatus,
)


def test_fuzzy_explanation_schema():
    cand = FuzzyCandidate(
        entity_type=EntityType.WORKER,
        entity_id_a="a",
        entity_id_b="b",
        score=92.0,
        evidence=FuzzyEvidence(notes=["Same company"], conflicting_fields=["email"]),
    )
    data = deterministic_fuzzy_explanation(cand)
    parsed = FuzzyExplanation.model_validate(data)
    assert parsed.match_strength in {"strong", "moderate", "weak"}


def test_fallback_adapter_summary():
    adapter = FallbackAdapter()
    now = datetime.now(timezone.utc)
    run = ImportRun(
        id="r1",
        name="Demo",
        status=RunStatus.REVIEW_PENDING,
        reference_date=date(2025, 6, 15),
        created_at=now,
        updated_at=now,
        llm_provider="fallback",
        llm_model="deterministic-fallback",
    )
    entity = EntityRecord(
        id="co_1",
        run_id="r1",
        entity_type=EntityType.COMPANY,
        data={
            "id": "co_1",
            "company_name": "Apex",
            "canonical_name": "apex",
            "abn": None,
            "role": "subcontractor",
            "review_status": "approved",
            "source_rows": [2],
        },
        parent_id=None,
        id_confidence=IdConfidence.MEDIUM,
        review_status=ReviewStatus.APPROVED,
        source_rows=[2],
        created_at=now,
        updated_at=now,
    )
    text = adapter.draft_implementation_summary(run, [entity], [], [])
    assert "Independent demo. Synthetic data." in text
    assert "Entities processed: 1" in text
