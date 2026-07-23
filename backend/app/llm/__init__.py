"""LLM adapter protocol and provider implementations.

Deterministic fallback on any failure. Hosted providers are opt-in via LLM_PROVIDER.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.models import (
    DecisionRecord,
    EntityRecord,
    FuzzyCandidate,
    ImportRun,
    IssueRecord,
    Severity,
)
from app.pipeline.export import is_import_ready

HOSTED_PROVIDERS = frozenset({"openai", "anthropic", "gemini"})


class FuzzyExplanation(BaseModel):
    match_strength: str = Field(pattern="^(strong|moderate|weak)$")
    supporting_evidence: list[str]
    conflicting_evidence: list[str]
    recommended_human_check: str


class LLMAdapter(Protocol):
    provider: str
    model: str

    @property
    def is_hosted(self) -> bool: ...

    def draft_implementation_summary(
        self,
        run: ImportRun,
        entities: list[EntityRecord],
        issues: list[IssueRecord],
        decisions: list[DecisionRecord],
    ) -> str: ...

    def draft_exception_narrative(
        self,
        run: ImportRun,
        issues: list[IssueRecord],
    ) -> str: ...

    def explain_fuzzy(
        self,
        entity_a: EntityRecord,
        entity_b: EntityRecord,
        candidate: FuzzyCandidate,
    ) -> dict[str, Any]: ...


def _counts_payload(
    run: ImportRun,
    entities: list[EntityRecord],
    issues: list[IssueRecord],
    decisions: list[DecisionRecord],
) -> dict[str, Any]:
    by_id = {e.id: e for e in entities}
    ready = sum(1 for e in entities if is_import_ready(e, by_id))
    return {
        "run_name": run.name,
        "reference_date": run.reference_date.isoformat(),
        "entity_total": len(entities),
        "import_ready": ready,
        "excluded": len(entities) - ready,
        "errors": sum(1 for i in issues if i.severity == Severity.ERROR),
        "warnings": sum(1 for i in issues if i.severity == Severity.WARNING),
        "decisions": len(decisions),
        "issue_counts_by_rule": _rule_counts(issues),
    }


def _rule_counts(issues: list[IssueRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for i in issues:
        counts[i.rule_id] = counts.get(i.rule_id, 0) + 1
    return counts


def deterministic_implementation_summary(payload: dict[str, Any], provider: str, model: str) -> str:
    return "\n".join(
        [
            "# Implementation Summary",
            "",
            "> Independent demo. Synthetic data.",
            "",
            f"Onboarding run **{payload['run_name']}** "
            f"(reference date {payload['reference_date']}) is complete.",
            "",
            "## Counts (deterministic)",
            "",
            f"- Entities processed: {payload['entity_total']}",
            f"- Import-ready: {payload['import_ready']}",
            f"- Excluded: {payload['excluded']}",
            f"- Validation errors: {payload['errors']}",
            f"- Validation warnings: {payload['warnings']}",
            f"- Human decisions recorded: {payload['decisions']}",
            "",
            "AI drafting used the deterministic fallback template. "
            "No figures were invented.",
            "",
            "---",
            f"Provider: {provider} / Model: {model}",
            "",
        ]
    )


def deterministic_exception_narrative(payload: dict[str, Any], provider: str, model: str) -> str:
    lines = [
        "The following issue categories were detected by deterministic rules:",
        "",
    ]
    for rule, count in sorted(payload.get("issue_counts_by_rule", {}).items()):
        lines.append(f"- `{rule}`: {count}")
    lines.extend(
        [
            "",
            f"(Fallback narrative — provider {provider} / model {model})",
        ]
    )
    return "\n".join(lines)


def deterministic_fuzzy_explanation(candidate: FuzzyCandidate) -> dict[str, Any]:
    supporting = list(candidate.evidence.notes)
    conflicting = list(candidate.evidence.conflicting_fields)
    if candidate.score >= 90:
        strength = "strong"
    elif candidate.score >= 80:
        strength = "moderate"
    else:
        strength = "weak"
    payload = FuzzyExplanation(
        match_strength=strength,
        supporting_evidence=supporting or ["Deterministic similarity evidence only"],
        conflicting_evidence=conflicting or [],
        recommended_human_check=(
            "Compare source rows and contact fields before merging or keeping separate."
        ),
    ).model_dump()
    payload["source"] = "fallback"
    return payload


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


class ChatAdapterBase:
    """Shared advisory drafting. Subclasses implement _chat_text / _chat_json."""

    provider: str
    model: str

    @property
    def is_hosted(self) -> bool:
        return self.provider in HOSTED_PROVIDERS

    def _chat_text(self, system: str, user: str) -> str | None:
        raise NotImplementedError

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def draft_implementation_summary(
        self,
        run: ImportRun,
        entities: list[EntityRecord],
        issues: list[IssueRecord],
        decisions: list[DecisionRecord],
    ) -> str:
        payload = _counts_payload(run, entities, issues, decisions)
        system = (
            "You draft a short customer-facing implementation summary. "
            "Use ONLY the numbers provided. Never invent figures. "
            "Return plain Markdown. Mention Independent demo. Synthetic data."
        )
        text = self._chat_text(system, json.dumps(payload))
        if not text:
            return deterministic_implementation_summary(payload, self.provider, self.model)
        if "Independent demo" not in text:
            text = "> Independent demo. Synthetic data.\n\n" + text
        text += f"\n\n---\nProvider: {self.provider} / Model: {self.model}\n"
        return text

    def draft_exception_narrative(
        self,
        run: ImportRun,
        issues: list[IssueRecord],
    ) -> str:
        payload = {
            "run_name": run.name,
            "issue_counts_by_rule": _rule_counts(issues),
            "errors": sum(1 for i in issues if i.severity == Severity.ERROR),
            "warnings": sum(1 for i in issues if i.severity == Severity.WARNING),
        }
        system = (
            "Summarise the exception categories in plain English. "
            "Do not invent counts; use only provided counts."
        )
        text = self._chat_text(system, json.dumps(payload))
        if not text:
            return deterministic_exception_narrative(payload, self.provider, self.model)
        return text

    def explain_fuzzy(
        self,
        entity_a: EntityRecord,
        entity_b: EntityRecord,
        candidate: FuzzyCandidate,
    ) -> dict[str, Any]:
        system = (
            "You explain fuzzy duplicate evidence for a human reviewer. "
            "Never decide identity. Return JSON with keys: match_strength "
            "(strong|moderate|weak), supporting_evidence, conflicting_evidence, "
            "recommended_human_check."
        )
        user = json.dumps(
            {
                "entity_a": entity_a.data,
                "entity_b": entity_b.data,
                "score": candidate.score,
                "evidence": candidate.evidence.model_dump(),
            }
        )
        raw = self._chat_json(system, user)
        if raw is None:
            return deterministic_fuzzy_explanation(candidate)
        try:
            data = FuzzyExplanation.model_validate(raw).model_dump()
            data["source"] = "llm"
            return data
        except ValidationError as exc:
            retry_user = user + f"\n\nPrevious output failed validation: {exc}. Fix the JSON."
            raw2 = self._chat_json(system, retry_user)
            if raw2 is None:
                return deterministic_fuzzy_explanation(candidate)
            try:
                data = FuzzyExplanation.model_validate(raw2).model_dump()
                data["source"] = "llm"
                return data
            except ValidationError:
                return deterministic_fuzzy_explanation(candidate)


class OllamaAdapter(ChatAdapterBase):
    """Local Ollama adapter. Never authoritative for decisions or counts."""

    def __init__(self, base_url: str, model: str) -> None:
        self.provider = "ollama"
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        if not self._available():
            return None
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(f"{self.base_url}/api/chat", json=payload)
                r.raise_for_status()
                content = r.json().get("message", {}).get("content", "")
                return _extract_json_object(content)
        except Exception:
            return None

    def _chat_text(self, system: str, user: str) -> str | None:
        if not self._available():
            return None
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(f"{self.base_url}/api/chat", json=payload)
                r.raise_for_status()
                return r.json().get("message", {}).get("content")
        except Exception:
            return None


class OpenAIAdapter(ChatAdapterBase):
    """Hosted OpenAI Chat Completions. Opt-in only."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.provider = "openai"
        self.model = model
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat(self, system: str, user: str, *, json_mode: bool) -> str | None:
        if not self.api_key:
            return None
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
                r.raise_for_status()
                choices = r.json().get("choices") or []
                if not choices:
                    return None
                return choices[0].get("message", {}).get("content")
        except Exception:
            return None

    def _chat_text(self, system: str, user: str) -> str | None:
        return self._chat(system, user, json_mode=False)

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        content = self._chat(system, user, json_mode=True)
        if not content:
            return None
        return _extract_json_object(content)


class AnthropicAdapter(ChatAdapterBase):
    """Hosted Anthropic Messages API. Opt-in only."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self.provider = "anthropic"
        self.model = model
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")

    def _chat(self, system: str, user: str) -> str | None:
        if not self.api_key:
            return None
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{self.base_url}/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                blocks = r.json().get("content") or []
                texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
                return "\n".join(texts).strip() or None
        except Exception:
            return None

    def _chat_text(self, system: str, user: str) -> str | None:
        return self._chat(system, user)

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        json_system = system + " Respond with a single JSON object only."
        content = self._chat(json_system, user)
        if not content:
            return None
        return _extract_json_object(content)


class GeminiAdapter(ChatAdapterBase):
    """Hosted Google Gemini generateContent API. Opt-in only."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self.provider = "gemini"
        self.model = model
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")

    def _chat(self, system: str, user: str, *, json_mode: bool) -> str | None:
        if not self.api_key:
            return None
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = f"{self.base_url}/models/{self.model}:generateContent"
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, params={"key": self.api_key}, json=body)
                r.raise_for_status()
                candidates = r.json().get("candidates") or []
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts") or []
                texts = [p.get("text", "") for p in parts if "text" in p]
                return "\n".join(texts).strip() or None
        except Exception:
            return None

    def _chat_text(self, system: str, user: str) -> str | None:
        return self._chat(system, user, json_mode=False)

    def _chat_json(self, system: str, user: str) -> dict[str, Any] | None:
        content = self._chat(system, user, json_mode=True)
        if not content:
            return None
        return _extract_json_object(content)


class FallbackAdapter:
    """Always uses deterministic templates."""

    def __init__(self, model: str = "deterministic-fallback", provider: str = "fallback") -> None:
        self.provider = provider
        self.model = model

    @property
    def is_hosted(self) -> bool:
        return False

    def draft_implementation_summary(
        self,
        run: ImportRun,
        entities: list[EntityRecord],
        issues: list[IssueRecord],
        decisions: list[DecisionRecord],
    ) -> str:
        payload = _counts_payload(run, entities, issues, decisions)
        return deterministic_implementation_summary(payload, self.provider, self.model)

    def draft_exception_narrative(
        self,
        run: ImportRun,
        issues: list[IssueRecord],
    ) -> str:
        payload = {
            "run_name": run.name,
            "issue_counts_by_rule": _rule_counts(issues),
        }
        return deterministic_exception_narrative(payload, self.provider, self.model)

    def explain_fuzzy(
        self,
        entity_a: EntityRecord,
        entity_b: EntityRecord,
        candidate: FuzzyCandidate,
    ) -> dict[str, Any]:
        return deterministic_fuzzy_explanation(candidate)


def hosted_provider_warning(provider: str) -> str | None:
    if provider not in HOSTED_PROVIDERS:
        return None
    return (
        f"Hosted provider active ({provider}): prompts leave this machine. "
        "This is an explicit configuration change, not the default."
    )


def build_llm_adapter(
    provider: str,
    model: str,
    *,
    ollama_base_url: str = "http://localhost:11434",
    openai_api_key: str = "",
    openai_base_url: str = "https://api.openai.com/v1",
    anthropic_api_key: str = "",
    anthropic_base_url: str = "https://api.anthropic.com",
    gemini_api_key: str = "",
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta",
) -> LLMAdapter:
    key = provider.strip().lower()
    if key == "ollama":
        return OllamaAdapter(ollama_base_url, model)
    if key == "openai":
        return OpenAIAdapter(openai_api_key, model, openai_base_url)
    if key == "anthropic":
        return AnthropicAdapter(anthropic_api_key, model, anthropic_base_url)
    if key == "gemini":
        return GeminiAdapter(gemini_api_key, model, gemini_base_url)
    if key in {"fallback", "none", "off"}:
        return FallbackAdapter(model=model)
    return FallbackAdapter(model=model, provider=key or "fallback")
