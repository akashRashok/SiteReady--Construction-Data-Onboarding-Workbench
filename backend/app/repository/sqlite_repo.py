"""SQLite implementation of the Repository protocol.

This is the ONLY module in the application that contains SQL.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from ..models.entity_record import EntityRecord
from ..models.enums import EntityType, ReviewStatus
from ..models.issue import Decision, Issue
from ..models.run import ImportRun, SourceRow


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SqliteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ runs
    def create_run(self, run: ImportRun) -> None:
        self._conn.execute(
            """
            INSERT INTO import_runs (
                id, name, status, source_filename, source_path, is_synthetic,
                reference_date, llm_provider, llm_model, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.name,
                run.status,
                run.source_filename,
                run.source_path,
                1 if run.is_synthetic else 0,
                run.reference_date,
                run.llm_provider,
                run.llm_model,
                run.created_at.isoformat(),
                run.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> ImportRun | None:
        row = self._conn.execute(
            "SELECT * FROM import_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return self._row_to_run(row) if row else None

    def update_run(self, run: ImportRun) -> None:
        self._conn.execute(
            """
            UPDATE import_runs SET
                name = ?, status = ?, source_filename = ?, source_path = ?,
                is_synthetic = ?, reference_date = ?, llm_provider = ?,
                llm_model = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                run.name,
                run.status,
                run.source_filename,
                run.source_path,
                1 if run.is_synthetic else 0,
                run.reference_date,
                run.llm_provider,
                run.llm_model,
                run.updated_at.isoformat(),
                run.id,
            ),
        )
        self._conn.commit()

    def list_runs(self) -> list[ImportRun]:
        rows = self._conn.execute(
            "SELECT * FROM import_runs ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def delete_run(self, run_id: str) -> None:
        self._conn.execute("DELETE FROM import_runs WHERE id = ?", (run_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> ImportRun:
        return ImportRun(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            source_filename=row["source_filename"],
            source_path=row["source_path"],
            is_synthetic=bool(row["is_synthetic"]),
            reference_date=row["reference_date"],
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    # ----------------------------------------------------------- source rows
    def add_source_rows(self, rows: list[SourceRow]) -> None:
        self._conn.executemany(
            """
            INSERT INTO source_rows (id, run_id, source_row_number, raw_data, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    r.id,
                    r.run_id,
                    r.source_row_number,
                    json.dumps(r.raw_data, ensure_ascii=False),
                    r.created_at.isoformat(),
                )
                for r in rows
            ],
        )
        self._conn.commit()

    def get_source_rows(self, run_id: str) -> list[SourceRow]:
        rows = self._conn.execute(
            "SELECT * FROM source_rows WHERE run_id = ? ORDER BY source_row_number",
            (run_id,),
        ).fetchall()
        return [
            SourceRow(
                id=r["id"],
                run_id=r["run_id"],
                source_row_number=r["source_row_number"],
                raw_data=json.loads(r["raw_data"]),
                created_at=_dt(r["created_at"]),
            )
            for r in rows
        ]

    # -------------------------------------------------------------- entities
    def clear_entities(self, run_id: str) -> None:
        self._conn.execute("DELETE FROM entities WHERE run_id = ?", (run_id,))
        self._conn.commit()

    def add_entities(self, entities: list[EntityRecord]) -> None:
        self._conn.executemany(
            """
            INSERT INTO entities (
                id, run_id, entity_type, data, parent_id, id_confidence,
                review_status, source_rows, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e.id,
                    e.run_id,
                    e.entity_type,
                    json.dumps(e.data, ensure_ascii=False),
                    e.parent_id,
                    e.id_confidence,
                    e.review_status,
                    json.dumps(e.source_rows),
                    e.created_at.isoformat(),
                    e.updated_at.isoformat(),
                )
                for e in entities
            ],
        )
        self._conn.commit()

    def get_entities(
        self, run_id: str, entity_type: EntityType | None = None
    ) -> list[EntityRecord]:
        if entity_type is not None:
            rows = self._conn.execute(
                "SELECT * FROM entities WHERE run_id = ? AND entity_type = ? "
                "ORDER BY created_at",
                (run_id, entity_type.value),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM entities WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def get_entity(self, run_id: str, entity_id: str) -> EntityRecord | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE run_id = ? AND id = ?",
            (run_id, entity_id),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def set_entity_status(
        self, run_id: str, entity_id: str, status: ReviewStatus
    ) -> None:
        self._conn.execute(
            "UPDATE entities SET review_status = ?, updated_at = ? "
            "WHERE run_id = ? AND id = ?",
            (status.value, datetime.utcnow().isoformat(), run_id, entity_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> EntityRecord:
        return EntityRecord(
            id=row["id"],
            run_id=row["run_id"],
            entity_type=row["entity_type"],
            data=json.loads(row["data"]),
            parent_id=row["parent_id"],
            id_confidence=row["id_confidence"],
            review_status=row["review_status"],
            source_rows=json.loads(row["source_rows"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    # ---------------------------------------------------------------- issues
    def clear_issues(self, run_id: str) -> None:
        self._conn.execute("DELETE FROM issues WHERE run_id = ?", (run_id,))
        self._conn.commit()

    def add_issues(self, issues: list[Issue]) -> None:
        self._conn.executemany(
            """
            INSERT INTO issues (
                id, run_id, rule_id, severity, entity_type, entity_id,
                source_rows, field, raw_value, normalised_value, message,
                import_consequence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    i.id,
                    i.run_id,
                    i.rule_id,
                    i.severity,
                    i.entity_type,
                    i.entity_id,
                    json.dumps(i.source_rows),
                    i.field,
                    i.raw_value,
                    i.normalised_value,
                    i.message,
                    i.import_consequence,
                    i.created_at.isoformat(),
                )
                for i in issues
            ],
        )
        self._conn.commit()

    def get_issues(
        self, run_id: str, entity_id: str | None = None
    ) -> list[Issue]:
        if entity_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM issues WHERE run_id = ? AND entity_id = ? "
                "ORDER BY created_at",
                (run_id, entity_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM issues WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [self._row_to_issue(r) for r in rows]

    @staticmethod
    def _row_to_issue(row: sqlite3.Row) -> Issue:
        return Issue(
            id=row["id"],
            run_id=row["run_id"],
            rule_id=row["rule_id"],
            severity=row["severity"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            source_rows=json.loads(row["source_rows"]),
            field=row["field"],
            raw_value=row["raw_value"],
            normalised_value=row["normalised_value"],
            message=row["message"],
            import_consequence=row["import_consequence"],
            created_at=_dt(row["created_at"]),
        )

    # ------------------------------------------------------------- decisions
    def add_decision(self, decision: Decision) -> None:
        self._conn.execute(
            """
            INSERT INTO decisions (
                id, run_id, entity_id, decision, reason, related_entity_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.id,
                decision.run_id,
                decision.entity_id,
                decision.decision,
                decision.reason,
                decision.related_entity_id,
                decision.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_decisions(
        self, run_id: str, entity_id: str | None = None
    ) -> list[Decision]:
        if entity_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM decisions WHERE run_id = ? AND entity_id = ? "
                "ORDER BY created_at",
                (run_id, entity_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM decisions WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [
            Decision(
                id=r["id"],
                run_id=r["run_id"],
                entity_id=r["entity_id"],
                decision=r["decision"],
                reason=r["reason"],
                related_entity_id=r["related_entity_id"],
                created_at=_dt(r["created_at"]),
            )
            for r in rows
        ]
