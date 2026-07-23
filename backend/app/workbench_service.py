"""Application services orchestrating pipeline stages."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.models import (
    AuditTrail,
    ColumnMapping,
    DecisionRecord,
    DecisionType,
    EntityRecord,
    FuzzyCandidate,
    ImportRun,
    IssueRecord,
    MappingConfidence,
    ReviewStatus,
    RunStatus,
    Severity,
)
from app.pipeline import (
    collapse_exact_duplicates,
    generate_exports,
    ingest_csv,
    mappings_ready,
    pending_entities,
    profile_columns,
    score_fuzzy_candidates,
    split_and_normalise,
    validate_entities,
)
from app.repository.sqlite import SqliteRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WorkbenchService:
    def __init__(
        self,
        repo: SqliteRepository,
        settings: Settings,
        llm_adapter: object | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings
        self.llm = llm_adapter
        self.settings.upload_path.mkdir(parents=True, exist_ok=True)
        self.settings.output_path.mkdir(parents=True, exist_ok=True)

    def create_run(self, name: str, reference_date, is_synthetic: bool = True) -> ImportRun:
        provider = getattr(self.llm, "provider", None) or self.settings.llm_provider
        model = getattr(self.llm, "model", None) or self.settings.llm_model
        return self.repo.create_run(
            name=name,
            reference_date=reference_date,
            is_synthetic=is_synthetic,
            llm_provider=provider,
            llm_model=model,
        )

    def get_run(self, run_id: str) -> ImportRun:
        run = self.repo.get_run(run_id)
        if run is None:
            raise ServiceError(f"Run {run_id} not found", 404)
        return run

    def list_runs(self) -> list[ImportRun]:
        return self.repo.list_runs()

    def upload_csv(self, run_id: str, filename: str, content: bytes) -> ImportRun:
        run = self.get_run(run_id)
        upload_dir = self.settings.upload_path / run_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / filename
        dest.write_bytes(content)

        source_rows, structural_issues, headers = ingest_csv(run_id, content)
        self.repo.add_source_rows(source_rows)
        if structural_issues:
            self.repo.add_issues(structural_issues)

        mappings = profile_columns(headers, [r.raw_data for r in source_rows])
        status = (
            RunStatus.MAPPING_PENDING
            if not mappings_ready(mappings)
            else RunStatus.INGESTED
        )
        return self.repo.update_run(
            run_id,
            status=status,
            source_filename=filename,
            source_path=str(dest.relative_to(self.settings.upload_path.parent.parent))
            if False
            else str(dest),
            mappings=mappings,
        )

    def get_mappings(self, run_id: str) -> list[ColumnMapping]:
        run = self.get_run(run_id)
        return run.mappings or []

    def confirm_mappings(self, run_id: str, mappings: list) -> ImportRun:
        run = self.get_run(run_id)
        existing = {m.source_column: m for m in (run.mappings or [])}
        confirmed: list[ColumnMapping] = []
        for m in mappings:
            source_column = m.source_column if hasattr(m, "source_column") else m["source_column"]
            target_entity = m.target_entity if hasattr(m, "target_entity") else m.get("target_entity")
            target_field = m.target_field if hasattr(m, "target_field") else m.get("target_field")
            method = getattr(m, "method", None)
            if isinstance(m, dict):
                method = m.get("method", method)
            base = existing.get(source_column)
            ignored = target_entity is None or target_field is None
            if base is None:
                from app.models import MappingConfidence, MappingMethod

                data = ColumnMapping(
                    source_column=source_column,
                    target_entity=None if ignored else target_entity,
                    target_field=None if ignored else target_field,
                    method=MappingMethod.UNMAPPED if ignored else (method or MappingMethod.UNMAPPED),
                    confidence=getattr(m, "confidence", None)
                    or (m.get("confidence") if isinstance(m, dict) else None)
                    or MappingConfidence.LOW,
                    sample_values=getattr(m, "sample_values", None)
                    or (m.get("sample_values") if isinstance(m, dict) else None)
                    or [],
                    confirmed=True,
                )
            else:
                update: dict = {
                    "target_entity": None if ignored else target_entity,
                    "target_field": None if ignored else target_field,
                    "confirmed": True,
                }
                if ignored:
                    from app.models import MappingMethod

                    update["method"] = MappingMethod.UNMAPPED
                data = base.model_copy(update=update)
            confirmed.append(data)
        sent = {m.source_column for m in confirmed}
        for col, base in existing.items():
            if col not in sent:
                item = base.model_copy(deep=True)
                item.confirmed = True
                confirmed.append(item)
        if not mappings_ready(confirmed):
            raise ServiceError("Not all low-confidence mappings are confirmed")
        return self.repo.update_run(
            run_id,
            status=RunStatus.INGESTED,
            mappings=confirmed,
        )

    def process(self, run_id: str) -> ImportRun:
        run = self.get_run(run_id)
        if not run.mappings or not mappings_ready(run.mappings):
            raise ServiceError(
                "Mappings must be confirmed before processing",
                400,
            )
        self.repo.update_run(run_id, status=RunStatus.PROCESSING)
        try:
            source_rows = self.repo.get_source_rows(run_id)
            raws = [r.raw_data for r in source_rows]
            row_nums = [r.source_row_number for r in source_rows]

            entities, transform_issues = split_and_normalise(
                run_id,
                raws,
                row_nums,
                run.mappings,
                run.reference_date,
            )
            entities, validation_issues = validate_entities(
                run_id, entities, run.reference_date
            )
            entities, dup_issues = collapse_exact_duplicates(run_id, entities)
            fuzzy = score_fuzzy_candidates(run_id, entities)

            # Optional LLM explanations for fuzzy candidates (advisory only)
            if self.llm is not None and hasattr(self.llm, "explain_fuzzy"):
                by_id = {e.id: e for e in entities}
                enriched: list[FuzzyCandidate] = []
                for cand in fuzzy:
                    a = by_id.get(cand.entity_id_a)
                    b = by_id.get(cand.entity_id_b)
                    explanation = None
                    if a and b:
                        explanation = self.llm.explain_fuzzy(a, b, cand)  # type: ignore[attr-defined]
                    enriched.append(
                        cand.model_copy(update={"llm_explanation": explanation})
                    )
                fuzzy = enriched

            all_issues = transform_issues + validation_issues + dup_issues
            # Preserve structural issues from ingest
            existing = [
                i
                for i in self.repo.get_issues(run_id)
                if i.rule_id == "structural_column_mismatch"
            ]
            self.repo.replace_issues(run_id, existing + all_issues)
            self.repo.replace_entities(run_id, entities)
            return self.repo.update_run(
                run_id,
                status=RunStatus.REVIEW_PENDING,
                fuzzy_candidates=fuzzy,
            )
        except Exception as exc:
            self.repo.update_run(run_id, status=RunStatus.FAILED)
            raise ServiceError(f"Processing failed: {exc}", 500) from exc

    def get_entities(self, run_id: str, entity_type: str | None = None) -> list[EntityRecord]:
        self.get_run(run_id)
        return self.repo.get_entities(run_id, entity_type)

    def get_issues(self, run_id: str) -> list[IssueRecord]:
        self.get_run(run_id)
        return self.repo.get_issues(run_id)

    def apply_decisions(self, run_id: str, decision_inputs: list) -> list[DecisionRecord]:
        run = self.get_run(run_id)
        now = _utcnow()
        records: list[DecisionRecord] = []
        fuzzy = list(run.fuzzy_candidates or [])

        for item in decision_inputs:
            entity = self.repo.get_entity(run_id, item.entity_id)
            if entity is None and item.decision not in (
                DecisionType.MERGE,
                DecisionType.KEEP_SEPARATE,
                DecisionType.DEFER,
            ):
                raise ServiceError(f"Entity {item.entity_id} not found", 404)

            if item.decision == DecisionType.OVERRIDE:
                if not item.reason or not item.reason.strip():
                    raise ServiceError("Override requires a human-entered reason")
                if entity is None:
                    raise ServiceError(f"Entity {item.entity_id} not found", 404)
                # Must have errors to override
                errors = [
                    i
                    for i in self.repo.get_issues(run_id)
                    if i.entity_id == entity.id and i.severity == Severity.ERROR
                ]
                if not errors:
                    raise ServiceError("Override only applies to entities with errors")
                entity.review_status = ReviewStatus.APPROVED_WITH_OVERRIDE
                entity.data["review_status"] = ReviewStatus.APPROVED_WITH_OVERRIDE.value
                self.repo.update_entity(run_id, entity)

            elif item.decision == DecisionType.APPROVE:
                if entity is None:
                    raise ServiceError(f"Entity {item.entity_id} not found", 404)
                errors = [
                    i
                    for i in self.repo.get_issues(run_id)
                    if i.entity_id == entity.id and i.severity == Severity.ERROR
                ]
                if errors:
                    raise ServiceError(
                        "Entity has unresolved errors; use override with a reason"
                    )
                entity.review_status = ReviewStatus.APPROVED
                entity.data["review_status"] = ReviewStatus.APPROVED.value
                self.repo.update_entity(run_id, entity)

            elif item.decision == DecisionType.REJECT:
                if entity is None:
                    raise ServiceError(f"Entity {item.entity_id} not found", 404)
                entity.review_status = ReviewStatus.REJECTED
                entity.data["review_status"] = ReviewStatus.REJECTED.value
                self.repo.update_entity(run_id, entity)

            elif item.decision in (
                DecisionType.MERGE,
                DecisionType.KEEP_SEPARATE,
                DecisionType.DEFER,
            ):
                resolved = False
                for idx, cand in enumerate(fuzzy):
                    if (
                        cand.entity_id_a == item.entity_id
                        and cand.entity_id_b == item.related_entity_id
                    ) or (
                        cand.entity_id_b == item.entity_id
                        and cand.entity_id_a == item.related_entity_id
                    ):
                        resolution = (
                            "merge"
                            if item.decision == DecisionType.MERGE
                            else "keep_separate"
                            if item.decision == DecisionType.KEEP_SEPARATE
                            else "defer"
                        )
                        fuzzy[idx] = cand.model_copy(update={"resolution": resolution})
                        resolved = True
                        # Merge: keep related (canonical), reject entity_id (never silent)
                        if item.decision == DecisionType.MERGE and item.related_entity_id:
                            keep = self.repo.get_entity(run_id, item.related_entity_id)
                            drop = self.repo.get_entity(run_id, item.entity_id)
                            if keep and drop:
                                keep.source_rows = sorted(
                                    set(keep.source_rows + drop.source_rows)
                                )
                                keep.data["source_rows"] = keep.source_rows
                                keep.data["duplicate_count"] = len(keep.source_rows)
                                keep.review_status = ReviewStatus.APPROVED
                                keep.data["review_status"] = ReviewStatus.APPROVED.value
                                drop.review_status = ReviewStatus.REJECTED
                                drop.data["review_status"] = ReviewStatus.REJECTED.value
                                drop.data["merged_into"] = keep.id
                                self.repo.update_entity(run_id, keep)
                                self.repo.update_entity(run_id, drop)
                        break
                if not resolved:
                    raise ServiceError("Fuzzy candidate pair not found")

            records.append(
                DecisionRecord(
                    run_id=run_id,
                    entity_id=item.entity_id,
                    decision=item.decision,
                    reason=item.reason,
                    related_entity_id=item.related_entity_id,
                    created_at=now,
                )
            )

        self.repo.update_run(run_id, fuzzy_candidates=fuzzy)
        saved = self.repo.add_decisions(records)

        # If no pending entities and all fuzzy resolved or deferred, mark approved
        entities = self.repo.get_entities(run_id)
        still_pending = pending_entities(entities)
        unresolved_fuzzy = [
            c for c in (self.get_run(run_id).fuzzy_candidates or []) if c.resolution is None
        ]
        if not still_pending and not unresolved_fuzzy:
            self.repo.update_run(run_id, status=RunStatus.APPROVED)
        return saved

    def export(self, run_id: str) -> ImportRun:
        run = self.get_run(run_id)
        entities = self.repo.get_entities(run_id)
        pending = pending_entities(entities)
        if pending:
            ids = ", ".join(e.id for e in pending[:20])
            more = "" if len(pending) <= 20 else f" (+{len(pending) - 20} more)"
            raise ServiceError(
                f"Export refused: {len(pending)} entities still pending_review: {ids}{more}"
            )
        unresolved_fuzzy = [
            c for c in (run.fuzzy_candidates or []) if c.resolution is None
        ]
        if unresolved_fuzzy:
            raise ServiceError(
                f"Export refused: {len(unresolved_fuzzy)} fuzzy candidates unresolved"
            )

        issues = self.repo.get_issues(run_id)
        decisions = self.repo.get_decisions(run_id)

        summary = None
        narrative = None
        if self.llm is not None and hasattr(self.llm, "draft_implementation_summary"):
            summary = self.llm.draft_implementation_summary(  # type: ignore[attr-defined]
                run, entities, issues, decisions
            )
            narrative = self.llm.draft_exception_narrative(run, issues)  # type: ignore[attr-defined]

        paths = generate_exports(
            run,
            entities,
            issues,
            decisions,
            self.settings.output_path,
            implementation_summary=summary,
        )
        if narrative:
            # Append narrative section to exception report md if provided
            md_path = self.settings.output_path / run.id / "exception_report.md"
            if md_path.exists():
                existing = md_path.read_text(encoding="utf-8")
                md_path.write_text(
                    existing
                    + "\n## Narrative\n\n"
                    + narrative
                    + "\n",
                    encoding="utf-8",
                )

        return self.repo.update_run(
            run_id,
            status=RunStatus.EXPORTED,
            artifact_paths=paths,
        )

    def get_artifact_path(self, run_id: str, name: str) -> Path:
        run = self.get_run(run_id)
        if name not in run.artifact_paths:
            # Allow direct file name under run output dir
            candidate = self.settings.output_path / run_id / name
            if candidate.exists() and candidate.is_file():
                return candidate
            raise ServiceError(f"Artifact {name} not found", 404)
        path = self.settings.output_path / run.artifact_paths[name]
        if not path.exists():
            raise ServiceError(f"Artifact file missing: {name}", 404)
        return path

    def get_audit(self, run_id: str, entity_id: str) -> AuditTrail:
        entity = self.repo.get_entity(run_id, entity_id)
        if entity is None:
            raise ServiceError(f"Entity {entity_id} not found", 404)
        issues = [i for i in self.repo.get_issues(run_id) if i.entity_id == entity_id]
        decisions = [d for d in self.repo.get_decisions(run_id) if d.entity_id == entity_id]
        source_rows = [
            r
            for r in self.repo.get_source_rows(run_id)
            if r.source_row_number in entity.source_rows
        ]
        return AuditTrail(
            entity=entity,
            issues=issues,
            decisions=decisions,
            source_rows=source_rows,
        )

    def delete_run(self, run_id: str) -> None:
        run = self.get_run(run_id)
        self.repo.delete_run(run_id)
        upload_dir = self.settings.upload_path / run_id
        output_dir = self.settings.output_path / run_id
        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        # Also remove source path file if present
        if run.source_path:
            p = Path(run.source_path)
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
