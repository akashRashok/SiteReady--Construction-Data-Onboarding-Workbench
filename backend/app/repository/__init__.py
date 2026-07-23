"""Repository protocol — the only persistence coupling point."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.models import (
    ColumnMapping,
    DecisionRecord,
    EntityRecord,
    FuzzyCandidate,
    ImportRun,
    IssueRecord,
    RunStatus,
    SourceRow,
)


@runtime_checkable
class Repository(Protocol):
    """Narrow storage interface free of engine-specific types."""

    def create_run(
        self,
        *,
        name: str,
        reference_date: date,
        is_synthetic: bool = True,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> ImportRun: ...

    def get_run(self, run_id: str) -> ImportRun | None: ...

    def list_runs(self) -> list[ImportRun]: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        source_filename: str | None = None,
        source_path: str | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        mappings: list[ColumnMapping] | None = None,
        fuzzy_candidates: list[FuzzyCandidate] | None = None,
        artifact_paths: dict[str, str] | None = None,
    ) -> ImportRun: ...

    def delete_run(self, run_id: str) -> bool: ...

    def add_source_rows(self, rows: list[SourceRow]) -> list[SourceRow]: ...

    def get_source_rows(self, run_id: str) -> list[SourceRow]: ...

    def replace_entities(self, run_id: str, entities: list[EntityRecord]) -> list[EntityRecord]: ...

    def get_entities(self, run_id: str, entity_type: str | None = None) -> list[EntityRecord]: ...

    def get_entity(self, run_id: str, entity_id: str) -> EntityRecord | None: ...

    def update_entity(self, run_id: str, entity: EntityRecord) -> EntityRecord: ...

    def replace_issues(self, run_id: str, issues: list[IssueRecord]) -> list[IssueRecord]: ...

    def add_issues(self, issues: list[IssueRecord]) -> list[IssueRecord]: ...

    def get_issues(self, run_id: str) -> list[IssueRecord]: ...

    def add_decisions(self, decisions: list[DecisionRecord]) -> list[DecisionRecord]: ...

    def get_decisions(self, run_id: str) -> list[DecisionRecord]: ...


from app.repository.sqlite import SchemaVersionError, SqliteRepository

__all__ = [
    "Repository",
    "SchemaVersionError",
    "SqliteRepository",
]
