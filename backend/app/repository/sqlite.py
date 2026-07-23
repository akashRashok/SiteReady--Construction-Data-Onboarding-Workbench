"""SQLite repository implementation."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.models import (
    ColumnMapping,
    DecisionRecord,
    DecisionType,
    EntityRecord,
    EntityType,
    FuzzyCandidate,
    IdConfidence,
    ImportRun,
    IssueRecord,
    ReviewStatus,
    RunStatus,
    Severity,
    SourceRow,
)


SCHEMA_VERSION_KEY = "schema_version"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SchemaVersionError(RuntimeError):
    """Raised when the database schema version does not match the application."""


class SqliteRepository:
    """SQLite-backed repository. All SQL lives here only."""

    def __init__(self, db_path: Path, schema_path: Path, expected_version: str) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self.expected_version = expected_version
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        ddl = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(ddl)
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                (SCHEMA_VERSION_KEY,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
                    (SCHEMA_VERSION_KEY, self.expected_version),
                )
            elif row["value"] != self.expected_version:
                raise SchemaVersionError(
                    f"Database schema version {row['value']!r} does not match "
                    f"expected {self.expected_version!r}"
                )
            conn.commit()

    def create_run(
        self,
        *,
        name: str,
        reference_date: date,
        is_synthetic: bool = True,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> ImportRun:
        now = _utcnow()
        run_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO import_runs (
                    id, name, status, source_filename, source_path, is_synthetic,
                    reference_date, llm_provider, llm_model, mappings_json,
                    fuzzy_candidates_json, artifact_paths_json, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                (
                    run_id,
                    name,
                    RunStatus.CREATED.value,
                    1 if is_synthetic else 0,
                    reference_date.isoformat(),
                    llm_provider,
                    llm_model,
                    json.dumps({}),
                    _iso(now),
                    _iso(now),
                ),
            )
            conn.commit()
        run = self.get_run(run_id)
        assert run is not None
        return run

    def get_run(self, run_id: str) -> ImportRun | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM import_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self) -> list[ImportRun]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM import_runs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

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
    ) -> ImportRun:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        new_status = status or run.status
        new_filename = source_filename if source_filename is not None else run.source_filename
        new_path = source_path if source_path is not None else run.source_path
        new_provider = llm_provider if llm_provider is not None else run.llm_provider
        new_model = llm_model if llm_model is not None else run.llm_model
        new_mappings = mappings if mappings is not None else run.mappings
        new_fuzzy = fuzzy_candidates if fuzzy_candidates is not None else run.fuzzy_candidates
        new_artifacts = artifact_paths if artifact_paths is not None else run.artifact_paths
        now = _utcnow()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE import_runs SET
                    status = ?,
                    source_filename = ?,
                    source_path = ?,
                    llm_provider = ?,
                    llm_model = ?,
                    mappings_json = ?,
                    fuzzy_candidates_json = ?,
                    artifact_paths_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    new_status.value,
                    new_filename,
                    new_path,
                    new_provider,
                    new_model,
                    json.dumps([m.model_dump(mode="json") for m in new_mappings])
                    if new_mappings is not None
                    else None,
                    json.dumps([f.model_dump(mode="json") for f in new_fuzzy])
                    if new_fuzzy is not None
                    else None,
                    json.dumps(new_artifacts),
                    _iso(now),
                    run_id,
                ),
            )
            conn.commit()
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM import_runs WHERE id = ?", (run_id,))
            conn.commit()
            return cur.rowcount > 0

    def add_source_rows(self, rows: list[SourceRow]) -> list[SourceRow]:
        if not rows:
            return []
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO source_rows (run_id, source_row_number, raw_data, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        row.run_id,
                        row.source_row_number,
                        json.dumps(row.raw_data),
                        _iso(row.created_at),
                    ),
                )
            conn.commit()
        return self.get_source_rows(rows[0].run_id)

    def get_source_rows(self, run_id: str) -> list[SourceRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM source_rows
                WHERE run_id = ?
                ORDER BY source_row_number
                """,
                (run_id,),
            ).fetchall()
        return [
            SourceRow(
                id=r["id"],
                run_id=r["run_id"],
                source_row_number=r["source_row_number"],
                raw_data=json.loads(r["raw_data"]),
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    def replace_entities(self, run_id: str, entities: list[EntityRecord]) -> list[EntityRecord]:
        with self._connect() as conn:
            conn.execute("DELETE FROM entities WHERE run_id = ?", (run_id,))
            for entity in entities:
                conn.execute(
                    """
                    INSERT INTO entities (
                        id, run_id, entity_type, data, parent_id, id_confidence,
                        review_status, source_rows, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity.id,
                        entity.run_id,
                        entity.entity_type.value,
                        json.dumps(entity.data),
                        entity.parent_id,
                        entity.id_confidence.value,
                        entity.review_status.value,
                        json.dumps(entity.source_rows),
                        _iso(entity.created_at),
                        _iso(entity.updated_at),
                    ),
                )
            conn.commit()
        return self.get_entities(run_id)

    def get_entities(self, run_id: str, entity_type: str | None = None) -> list[EntityRecord]:
        with self._connect() as conn:
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT * FROM entities
                    WHERE run_id = ? AND entity_type = ?
                    ORDER BY id
                    """,
                    (run_id, entity_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM entities WHERE run_id = ? ORDER BY entity_type, id",
                    (run_id,),
                ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def get_entity(self, run_id: str, entity_id: str) -> EntityRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM entities WHERE run_id = ? AND id = ?",
                (run_id, entity_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    def update_entity(self, run_id: str, entity: EntityRecord) -> EntityRecord:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE entities SET
                    data = ?,
                    parent_id = ?,
                    id_confidence = ?,
                    review_status = ?,
                    source_rows = ?,
                    updated_at = ?
                WHERE run_id = ? AND id = ?
                """,
                (
                    json.dumps(entity.data),
                    entity.parent_id,
                    entity.id_confidence.value,
                    entity.review_status.value,
                    json.dumps(entity.source_rows),
                    _iso(now),
                    run_id,
                    entity.id,
                ),
            )
            conn.commit()
        updated = self.get_entity(run_id, entity.id)
        assert updated is not None
        return updated

    def replace_issues(self, run_id: str, issues: list[IssueRecord]) -> list[IssueRecord]:
        with self._connect() as conn:
            conn.execute("DELETE FROM issues WHERE run_id = ?", (run_id,))
            self._insert_issues(conn, issues)
            conn.commit()
        return self.get_issues(run_id)

    def add_issues(self, issues: list[IssueRecord]) -> list[IssueRecord]:
        if not issues:
            return []
        with self._connect() as conn:
            self._insert_issues(conn, issues)
            conn.commit()
        return self.get_issues(issues[0].run_id)

    def _insert_issues(self, conn: sqlite3.Connection, issues: list[IssueRecord]) -> None:
        for issue in issues:
            conn.execute(
                """
                INSERT INTO issues (
                    run_id, rule_id, severity, entity_type, entity_id, source_rows,
                    field, raw_value, normalised_value, message, import_consequence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue.run_id,
                    issue.rule_id,
                    issue.severity.value,
                    issue.entity_type.value if issue.entity_type else None,
                    issue.entity_id,
                    json.dumps(issue.source_rows),
                    issue.field,
                    issue.raw_value,
                    issue.normalised_value,
                    issue.message,
                    issue.import_consequence,
                    _iso(issue.created_at),
                ),
            )

    def get_issues(self, run_id: str) -> list[IssueRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM issues WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            IssueRecord(
                id=r["id"],
                run_id=r["run_id"],
                rule_id=r["rule_id"],
                severity=Severity(r["severity"]),
                entity_type=EntityType(r["entity_type"]) if r["entity_type"] else None,
                entity_id=r["entity_id"],
                source_rows=json.loads(r["source_rows"]),
                field=r["field"],
                raw_value=r["raw_value"],
                normalised_value=r["normalised_value"],
                message=r["message"],
                import_consequence=r["import_consequence"],
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    def add_decisions(self, decisions: list[DecisionRecord]) -> list[DecisionRecord]:
        if not decisions:
            return []
        with self._connect() as conn:
            for d in decisions:
                conn.execute(
                    """
                    INSERT INTO decisions (
                        run_id, entity_id, decision, reason, related_entity_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        d.run_id,
                        d.entity_id,
                        d.decision.value,
                        d.reason,
                        d.related_entity_id,
                        _iso(d.created_at),
                    ),
                )
            conn.commit()
        return self.get_decisions(decisions[0].run_id)

    def get_decisions(self, run_id: str) -> list[DecisionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [
            DecisionRecord(
                id=r["id"],
                run_id=r["run_id"],
                entity_id=r["entity_id"],
                decision=DecisionType(r["decision"]),
                reason=r["reason"],
                related_entity_id=r["related_entity_id"],
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    def _row_to_run(self, row: sqlite3.Row) -> ImportRun:
        mappings_raw = row["mappings_json"]
        fuzzy_raw = row["fuzzy_candidates_json"]
        artifacts_raw = row["artifact_paths_json"]
        return ImportRun(
            id=row["id"],
            name=row["name"],
            status=RunStatus(row["status"]),
            source_filename=row["source_filename"],
            source_path=row["source_path"],
            is_synthetic=bool(row["is_synthetic"]),
            reference_date=date.fromisoformat(row["reference_date"]),
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            mappings=[ColumnMapping.model_validate(m) for m in json.loads(mappings_raw)]
            if mappings_raw
            else None,
            fuzzy_candidates=[FuzzyCandidate.model_validate(f) for f in json.loads(fuzzy_raw)]
            if fuzzy_raw
            else None,
            artifact_paths=json.loads(artifacts_raw) if artifacts_raw else {},
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def _row_to_entity(self, row: sqlite3.Row) -> EntityRecord:
        return EntityRecord(
            id=row["id"],
            run_id=row["run_id"],
            entity_type=EntityType(row["entity_type"]),
            data=json.loads(row["data"]),
            parent_id=row["parent_id"],
            id_confidence=IdConfidence(row["id_confidence"]),
            review_status=ReviewStatus(row["review_status"]),
            source_rows=json.loads(row["source_rows"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )
