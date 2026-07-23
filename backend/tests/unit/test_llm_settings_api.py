"""Tests for UI-editable LLM settings persistence."""

from __future__ import annotations

from pathlib import Path

import app.llm_settings as llm_settings
from app.llm_settings import LlmSettingsUpdate, clear_overrides, to_view, update_overrides


def test_update_and_reset_llm_settings(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "llm_settings.json"
    monkeypatch.setattr(llm_settings, "SETTINGS_PATH", path)

    clear_overrides()
    view = update_overrides(
        LlmSettingsUpdate(
            provider="openai",
            model="gpt-4o-mini",
            openai_api_key="sk-test-key-123456",
        )
    )
    assert view.provider == "openai"
    assert view.model == "gpt-4o-mini"
    assert view.is_hosted is True
    assert view.openai_api_key_set is True
    assert view.openai_api_key_preview is not None
    assert "sk-t" in (view.openai_api_key_preview or "")

    # Empty key leaves existing
    view2 = update_overrides(LlmSettingsUpdate(openai_api_key=""))
    assert view2.openai_api_key_set is True

    # "-" clears key
    view3 = update_overrides(LlmSettingsUpdate(openai_api_key="-"))
    assert view3.openai_api_key_set is False

    reset = clear_overrides()
    assert not path.exists()
    assert reset.provider in {"ollama", "openai", "anthropic", "gemini", "fallback"}


def test_settings_endpoints(client, tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "llm_settings.json"
    monkeypatch.setattr(llm_settings, "SETTINGS_PATH", path)

    got = client.get("/settings/llm")
    assert got.status_code == 200
    body = got.json()
    assert "providers" in body
    assert "model_presets" in body

    put = client.put(
        "/settings/llm",
        json={"provider": "fallback", "model": "deterministic-fallback"},
    )
    assert put.status_code == 200
    assert put.json()["provider"] == "fallback"

    health = client.get("/health").json()
    assert health["llm_provider"] == "fallback"
    assert health["llm_hosted"] is False

    deleted = client.delete("/settings/llm")
    assert deleted.status_code == 200
