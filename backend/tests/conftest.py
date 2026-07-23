"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings, get_settings
from app.deps import get_repository
from app.llm import FallbackAdapter
from app.main import create_app
from app.repository.sqlite import SqliteRepository
from app.workbench_service import WorkbenchService
import app.deps as deps
import app.llm_settings as llm_settings


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def fixtures_dir(project_root: Path) -> Path:
    return project_root / "fixtures"


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "test.db"),
        upload_dir=str(tmp_path / "uploads"),
        output_dir=str(tmp_path / "outputs"),
        llm_provider="fallback",
        llm_model="deterministic-fallback",
        schema_version="1",
    )


@pytest.fixture
def repo(tmp_settings: Settings, project_root: Path) -> SqliteRepository:
    return SqliteRepository(
        db_path=Path(tmp_settings.database_path),
        schema_path=project_root / "backend" / "schema.sql",
        expected_version="1",
    )


@pytest.fixture
def service(repo: SqliteRepository, tmp_settings: Settings) -> WorkbenchService:
    return WorkbenchService(
        repo=repo,
        settings=tmp_settings,
        llm_adapter=FallbackAdapter(),
    )


@pytest.fixture
def client(repo: SqliteRepository, tmp_settings: Settings, service: WorkbenchService, tmp_path: Path):
    get_settings.cache_clear()
    get_repository.cache_clear()
    deps._service = None
    llm_settings.SETTINGS_PATH = tmp_path / "llm_settings.json"

    app = create_app()

    deps.get_settings = lambda: tmp_settings  # type: ignore[assignment]
    deps.get_repository = lambda: repo  # type: ignore[assignment]
    deps.get_service = lambda: service  # type: ignore[assignment]
    deps.get_effective_llm = lambda: {  # type: ignore[assignment]
        "provider": tmp_settings.llm_provider,
        "model": tmp_settings.llm_model,
        "ollama_base_url": tmp_settings.ollama_base_url,
        "openai_api_key": tmp_settings.openai_api_key,
        "openai_base_url": tmp_settings.openai_base_url,
        "anthropic_api_key": tmp_settings.anthropic_api_key,
        "anthropic_base_url": tmp_settings.anthropic_base_url,
        "gemini_api_key": tmp_settings.gemini_api_key,
        "gemini_base_url": tmp_settings.gemini_base_url,
    }
    deps.reload_service = lambda: service  # type: ignore[assignment]

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_repository.cache_clear()
    deps._service = None


@pytest.fixture
def conn(repo: SqliteRepository):
    return repo._connect()
