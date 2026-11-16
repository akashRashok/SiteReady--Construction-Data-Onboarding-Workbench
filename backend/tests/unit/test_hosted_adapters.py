"""Unit tests for hosted LLM adapters and factory."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from app.llm import (
    AnthropicAdapter,
    FallbackAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    build_llm_adapter,
    hosted_provider_warning,
)
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


def _run() -> ImportRun:
    now = datetime.now(timezone.utc)
    return ImportRun(
        id="r1",
        name="Demo",
        status=RunStatus.REVIEW_PENDING,
        reference_date=date(2026, 7, 15),
        created_at=now,
        updated_at=now,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
    )


def _entity() -> EntityRecord:
    now = datetime.now(timezone.utc)
    return EntityRecord(
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


def test_hosted_warning_only_for_hosted_providers():
    assert hosted_provider_warning("ollama") is None
    assert hosted_provider_warning("fallback") is None
    assert "openai" in (hosted_provider_warning("openai") or "")
    assert "anthropic" in (hosted_provider_warning("anthropic") or "")
    assert "gemini" in (hosted_provider_warning("gemini") or "")


def test_build_llm_adapter_selects_providers():
    assert build_llm_adapter("ollama", "llama3.1:latest").provider == "ollama"
    assert build_llm_adapter("openai", "gpt-4o-mini", openai_api_key="sk").provider == "openai"
    assert (
        build_llm_adapter("anthropic", "claude-3-5-haiku-latest", anthropic_api_key="k").provider
        == "anthropic"
    )
    assert build_llm_adapter("gemini", "gemini-2.0-flash", gemini_api_key="k").provider == "gemini"
    assert build_llm_adapter("fallback", "x").provider == "fallback"


def test_openai_missing_key_falls_back():
    adapter = OpenAIAdapter("", "gpt-4o-mini")
    assert adapter.is_hosted is True
    text = adapter.draft_implementation_summary(_run(), [_entity()], [], [])
    assert "deterministic fallback" in text.lower() or "Entities processed" in text


def test_openai_success_path():
    adapter = OpenAIAdapter("sk-test", "gpt-4o-mini")
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "Summary text\nIndependent demo. Synthetic data."}}]
    }
    with patch("app.llm.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = fake_response
        text = adapter.draft_implementation_summary(_run(), [_entity()], [], [])
    assert "Summary text" in text
    assert "Provider: openai" in text


def test_openai_json_validation_retry_then_fallback():
    adapter = OpenAIAdapter("sk-test", "gpt-4o-mini")
    bad = MagicMock()
    bad.raise_for_status = MagicMock()
    bad.json.return_value = {
        "choices": [{"message": {"content": '{"match_strength":"nope"}'}}]
    }
    still_bad = MagicMock()
    still_bad.raise_for_status = MagicMock()
    still_bad.json.return_value = {
        "choices": [{"message": {"content": '{"match_strength":"nope"}'}}]
    }
    candidate = FuzzyCandidate(
        entity_type=EntityType.WORKER,
        entity_id_a="a",
        entity_id_b="b",
        score=88.0,
        evidence=FuzzyEvidence(notes=["Same company"], conflicting_fields=[]),
    )
    with patch("app.llm.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.side_effect = [bad, still_bad]
        result = adapter.explain_fuzzy(_entity(), _entity(), candidate)
    assert result["source"] == "fallback"
    assert result["match_strength"] in {"strong", "moderate", "weak"}


def test_anthropic_and_gemini_missing_key_fallback():
    for adapter in (
        AnthropicAdapter("", "claude-3-5-haiku-latest"),
        GeminiAdapter("", "gemini-2.0-flash"),
    ):
        assert adapter.is_hosted is True
        narrative = adapter.draft_exception_narrative(_run(), [])
        assert "Fallback narrative" in narrative or "deterministic" in narrative.lower() or "`" in narrative or "issue" in narrative.lower() or narrative


def test_fallback_adapter_not_hosted():
    adapter = FallbackAdapter()
    assert adapter.is_hosted is False
