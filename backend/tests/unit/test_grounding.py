"""The model may only restate numbers and facts present in its structured input."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.llm import ChatAdapterBase
from app.llm.grounding import check_grounded
from app.models import (
    EntityRecord,
    EntityType,
    IdConfidence,
    ImportRun,
    IssueRecord,
    ReviewStatus,
    RunStatus,
    Severity,
)

PAYLOAD = {
    "run_name": "Harbour demo",
    "reference_date": "2026-07-15",
    "entity_total": 37,
    "import_ready": 30,
    "excluded": 7,
    "errors": 0,
    "warnings": 0,
    "issue_counts_by_rule": {"transform_phone": 13, "exact_duplicate_collapse": 11},
}

GOOD = "Entities processed: 37. Import-ready: 30. Excluded: 7. Phone transforms: 13."


def test_grounded_text_passes():
    assert check_grounded(GOOD, PAYLOAD) == []


def test_original_summary_slip_is_rejected():
    bad = "Successfully imported 37 entities with no errors."
    problems = check_grounded(bad, PAYLOAD)
    assert any("claim" in p for p in problems)


def test_invented_and_derived_numbers_are_rejected():
    problems = check_grounded("There were 44 entities and 3 duplicates.", PAYLOAD)
    assert any("44" in p and "3" in p for p in problems)


def test_praise_is_rejected():
    assert check_grounded("No errors or warnings, which is good!", PAYLOAD)


def test_markdown_list_markers_are_not_numbers():
    text = "1. **Phones**: 13 transforms\n2. **Duplicates**: 11 collapses"
    assert check_grounded(text, PAYLOAD) == []


class ScriptedAdapter(ChatAdapterBase):
    provider = "scripted"
    model = "test"

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def _chat_text(self, system: str, user: str) -> str | None:
        self.calls += 1
        return self.replies.pop(0) if self.replies else None


def _run_and_entity():
    now = datetime.now(timezone.utc)
    run = ImportRun(
        id="r1",
        name="Demo",
        status=RunStatus.REVIEW_PENDING,
        reference_date=date(2026, 7, 15),
        created_at=now,
        updated_at=now,
        llm_provider="scripted",
        llm_model="test",
    )
    entity = EntityRecord(
        id="co_1",
        run_id="r1",
        entity_type=EntityType.COMPANY,
        data={"id": "co_1", "company_name": "Apex", "review_status": "approved", "source_rows": [2]},
        parent_id=None,
        id_confidence=IdConfidence.MEDIUM,
        review_status=ReviewStatus.APPROVED,
        source_rows=[2],
        created_at=now,
        updated_at=now,
    )
    return run, entity


def test_summary_retries_once_then_uses_grounded_draft():
    run, entity = _run_and_entity()
    adapter = ScriptedAdapter(
        ["Successfully imported 1 entities.", "Entities processed: 1. Import-ready: 0."]
    )
    text = adapter.draft_implementation_summary(run, [entity], [], [])
    assert adapter.calls == 2
    assert "Successfully" not in text
    assert "Entities processed: 1" in text


def test_summary_falls_back_to_template_when_both_drafts_are_bad():
    run, entity = _run_and_entity()
    adapter = ScriptedAdapter(["Successfully imported 99 entities."] * 2)
    text = adapter.draft_implementation_summary(run, [entity], [], [])
    assert adapter.calls == 2
    assert "deterministic fallback template" in text
    assert "99" not in text


def test_narrative_falls_back_when_ungrounded():
    run, _ = _run_and_entity()
    now = datetime.now(timezone.utc)
    issue = IssueRecord(
        run_id="r1",
        rule_id="transform_phone",
        severity=Severity.INFO,
        entity_type=EntityType.WORKER,
        entity_id="w1",
        source_rows=[2],
        field="phone",
        raw_value="0412 345 678",
        normalised_value="+61412345678",
        message="Normalised phone",
        import_consequence="None",
        created_at=now,
    )
    adapter = ScriptedAdapter(["There were 13 problems, which is good!"] * 2)
    text = adapter.draft_exception_narrative(run, [issue])
    assert "transform_phone" in text and "good" not in text
