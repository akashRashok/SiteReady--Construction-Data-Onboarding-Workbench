"""FastAPI dependency wiring with runtime-reloadable LLM settings."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.llm import build_llm_adapter
from app.llm_settings import effective_llm_values
from app.repository.sqlite import SqliteRepository
from app.services import WorkbenchService

_service: WorkbenchService | None = None


@lru_cache
def get_repository() -> SqliteRepository:
    settings = get_settings()
    return SqliteRepository(
        db_path=settings.database_file,
        schema_path=settings.schema_file,
        expected_version=settings.schema_version,
    )


def _build_service() -> WorkbenchService:
    settings = get_settings()
    repo = get_repository()
    vals = effective_llm_values(settings)
    llm = build_llm_adapter(
        vals["provider"],
        vals["model"],
        ollama_base_url=vals["ollama_base_url"],
        openai_api_key=vals["openai_api_key"],
        openai_base_url=vals["openai_base_url"],
        anthropic_api_key=vals["anthropic_api_key"],
        anthropic_base_url=vals["anthropic_base_url"],
        gemini_api_key=vals["gemini_api_key"],
        gemini_base_url=vals["gemini_base_url"],
    )
    return WorkbenchService(repo=repo, settings=settings, llm_adapter=llm)


def get_service() -> WorkbenchService:
    global _service
    if _service is None:
        _service = _build_service()
    return _service


def reload_service() -> WorkbenchService:
    """Rebuild service after LLM settings change."""
    global _service
    _service = _build_service()
    return _service


def get_app_settings() -> Settings:
    return get_settings()


def get_effective_llm() -> dict[str, str]:
    return effective_llm_values(get_settings())
