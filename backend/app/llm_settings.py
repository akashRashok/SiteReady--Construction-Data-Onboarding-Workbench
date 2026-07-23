"""Persisted LLM settings overrides (editable from the UI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import PROJECT_ROOT, Settings, get_settings
from app.llm import HOSTED_PROVIDERS, hosted_provider_warning

SETTINGS_PATH = PROJECT_ROOT / "data" / "llm_settings.json"

PROVIDERS = ("ollama", "openai", "anthropic", "gemini", "fallback")

MODEL_PRESETS: dict[str, list[str]] = {
    "ollama": ["llama3.1:latest", "qwen2.5:7b", "mistral:latest", "llama3.2:latest"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "o4-mini"],
    "anthropic": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-sonnet-4-0"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    "fallback": ["deterministic-fallback"],
}


class LlmSettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    ollama_base_url: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    gemini_api_key: str | None = None
    gemini_base_url: str | None = None


class LlmSettingsView(BaseModel):
    provider: str
    model: str
    is_hosted: bool
    warning: str | None = None
    ollama_base_url: str
    openai_base_url: str
    anthropic_base_url: str
    gemini_base_url: str
    openai_api_key_set: bool
    anthropic_api_key_set: bool
    gemini_api_key_set: bool
    # Masked previews only — never return full secrets
    openai_api_key_preview: str | None = None
    anthropic_api_key_preview: str | None = None
    gemini_api_key_preview: str | None = None
    providers: list[str] = Field(default_factory=lambda: list(PROVIDERS))
    model_presets: dict[str, list[str]] = Field(default_factory=lambda: MODEL_PRESETS)
    notice: str = "Independent demo. Synthetic data."


def _mask_key(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if len(text) <= 8:
        return "••••" + text[-2:]
    return text[:4] + "••••" + text[-4:]


def _load_file() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_file(data: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_overrides() -> dict[str, Any]:
    return _load_file()


def effective_llm_values(settings: Settings | None = None) -> dict[str, str]:
    base = settings or get_settings()
    overrides = _load_file()

    def pick(key: str, default: str) -> str:
        raw = overrides.get(key)
        if raw is None:
            return default
        return str(raw)

    provider = pick("provider", base.llm_provider).strip().lower() or "ollama"
    if provider not in PROVIDERS:
        provider = "ollama"

    return {
        "provider": provider,
        "model": pick("model", base.llm_model).strip() or base.llm_model,
        "ollama_base_url": pick("ollama_base_url", base.ollama_base_url),
        "openai_api_key": pick("openai_api_key", base.openai_api_key),
        "openai_base_url": pick("openai_base_url", base.openai_base_url),
        "anthropic_api_key": pick("anthropic_api_key", base.anthropic_api_key),
        "anthropic_base_url": pick("anthropic_base_url", base.anthropic_base_url),
        "gemini_api_key": pick("gemini_api_key", base.gemini_api_key),
        "gemini_base_url": pick("gemini_base_url", base.gemini_base_url),
    }


def to_view(values: dict[str, str] | None = None) -> LlmSettingsView:
    vals = values or effective_llm_values()
    provider = vals["provider"]
    return LlmSettingsView(
        provider=provider,
        model=vals["model"],
        is_hosted=provider in HOSTED_PROVIDERS,
        warning=hosted_provider_warning(provider),
        ollama_base_url=vals["ollama_base_url"],
        openai_base_url=vals["openai_base_url"],
        anthropic_base_url=vals["anthropic_base_url"],
        gemini_base_url=vals["gemini_base_url"],
        openai_api_key_set=bool(vals["openai_api_key"].strip()),
        anthropic_api_key_set=bool(vals["anthropic_api_key"].strip()),
        gemini_api_key_set=bool(vals["gemini_api_key"].strip()),
        openai_api_key_preview=_mask_key(vals["openai_api_key"]),
        anthropic_api_key_preview=_mask_key(vals["anthropic_api_key"]),
        gemini_api_key_preview=_mask_key(vals["gemini_api_key"]),
    )


def update_overrides(patch: LlmSettingsUpdate) -> LlmSettingsView:
    current = _load_file()
    data = patch.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str):
            # Empty API key fields mean "leave unchanged" except explicit clear token
            if key.endswith("_api_key") and value == "":
                continue
            if key.endswith("_api_key") and value.strip() == "-":
                current[key] = ""
                continue
            current[key] = value.strip() if key == "provider" else value
        else:
            current[key] = value
    if "provider" in current:
        current["provider"] = str(current["provider"]).strip().lower()
        if current["provider"] not in PROVIDERS:
            raise ValueError(f"Unsupported provider: {current['provider']}")
    _save_file(current)
    return to_view()


def clear_overrides() -> LlmSettingsView:
    if SETTINGS_PATH.exists():
        SETTINGS_PATH.unlink()
    return to_view()
