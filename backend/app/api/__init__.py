"""HTTP API routes aligned with the React client."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.deps import get_app_settings, get_effective_llm, get_service, reload_service
from app.llm_settings import LlmSettingsUpdate, clear_overrides, to_view, update_overrides
from app.models import (
    ColumnMapping,
    ConfirmMappingsRequest,
    CreateRunRequest,
    DecisionRequest,
    DecisionType,
    DecisionsBatchRequest,
    EntityType,
    Severity,
)
from app.services import ServiceError
from app.swms import extract_swms

router = APIRouter()


def _error(exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _serialize_fuzzy(cand) -> dict:
    ev = cand.evidence
    supporting = list(ev.notes)
    if ev.name_similarity is not None:
        supporting.append(f"name_similarity={ev.name_similarity}")
    if ev.same_company:
        supporting.append("same_company")
    if ev.matching_email:
        supporting.append("matching_email")
    if ev.matching_phone:
        supporting.append("matching_phone")
    if ev.matching_cert_number:
        supporting.append("matching_cert_number")
    if ev.matching_abn:
        supporting.append("matching_abn")
    explanation = cand.llm_explanation
    if explanation and "source" not in explanation:
        explanation = {**explanation, "source": "llm"}
    return {
        "entity_type": cand.entity_type.value,
        "left_id": cand.entity_id_a,
        "right_id": cand.entity_id_b,
        "score": cand.score,
        "supporting_evidence": supporting,
        "conflicting_evidence": list(ev.conflicting_fields),
        "llm_explanation": explanation,
        "resolution": cand.resolution,
    }


@router.get("/health")
def health() -> dict:
    vals = get_effective_llm()
    from app.llm import hosted_provider_warning

    provider = vals["provider"]
    warning = hosted_provider_warning(provider)
    return {
        "status": "ok",
        "notice": "Independent demo. Synthetic data.",
        "disclaimer": "Independent demo. Synthetic data.",
        "llm_provider": provider,
        "llm_model": vals["model"],
        "llm_hosted": provider in {"openai", "anthropic", "gemini"},
        "llm_warning": warning,
    }


@router.get("/settings/llm")
def get_llm_settings():
    return to_view().model_dump(mode="json")


@router.put("/settings/llm")
def put_llm_settings(body: LlmSettingsUpdate):
    try:
        view = update_overrides(body)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    reload_service()
    return view.model_dump(mode="json")


@router.delete("/settings/llm")
def reset_llm_settings():
    view = clear_overrides()
    reload_service()
    return view.model_dump(mode="json")



@router.post("/runs", status_code=201)
def create_run(body: CreateRunRequest):
    service = get_service()
    run = service.create_run(body.name, body.reference_date, body.is_synthetic)
    return run.model_dump(mode="json")


@router.get("/runs")
def list_runs():
    service = get_service()
    return [r.model_dump(mode="json") for r in service.list_runs()]


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    service = get_service()
    try:
        run = service.get_run(run_id)
    except ServiceError as exc:
        return _error(exc)
    return run.model_dump(mode="json")


@router.post("/runs/{run_id}/upload")
async def upload(run_id: str, file: UploadFile = File(...)):
    service = get_service()
    content = await file.read()
    filename = file.filename or "upload.csv"
    try:
        run = service.upload_csv(run_id, filename, content)
    except ServiceError as exc:
        return _error(exc)
    return run.model_dump(mode="json")


@router.get("/runs/{run_id}/mappings")
def get_mappings(run_id: str):
    service = get_service()
    try:
        mappings = service.get_mappings(run_id)
    except ServiceError as exc:
        return _error(exc)
    return [m.model_dump(mode="json") for m in mappings]


@router.post("/runs/{run_id}/mappings/confirm")
def confirm_mappings(run_id: str, body: ConfirmMappingsRequest):
    service = get_service()
    try:
        run = service.confirm_mappings(run_id, body.mappings)
    except ServiceError as exc:
        return _error(exc)
    return run.model_dump(mode="json")


@router.post("/runs/{run_id}/process")
def process_run(run_id: str):
    service = get_service()
    try:
        run = service.process(run_id)
    except ServiceError as exc:
        return _error(exc)
    return run.model_dump(mode="json")


@router.get("/runs/{run_id}/entities")
def get_entities(run_id: str, entity_type: str | None = None):
    service = get_service()
    try:
        entities = service.get_entities(run_id, entity_type)
    except ServiceError as exc:
        return _error(exc)
    return [e.model_dump(mode="json") for e in entities]


@router.get("/runs/{run_id}/issues")
def get_issues(run_id: str):
    service = get_service()
    try:
        issues = service.get_issues(run_id)
    except ServiceError as exc:
        return _error(exc)
    return [i.model_dump(mode="json") for i in issues]


@router.get("/runs/{run_id}/review")
def get_review(run_id: str):
    service = get_service()
    try:
        run = service.get_run(run_id)
        entities = service.get_entities(run_id)
        issues = service.get_issues(run_id)
    except ServiceError as exc:
        return _error(exc)

    exact_duplicates = []
    for entity in entities:
        count = int(entity.data.get("duplicate_count") or 1)
        if count > 1:
            exact_duplicates.append(
                {
                    "canonical_id": entity.id,
                    "duplicate_ids": [],
                    "duplicate_count": count,
                    "comparison_key": entity.id,
                }
            )

    return {
        "entities": [e.model_dump(mode="json") for e in entities],
        "issues": [i.model_dump(mode="json") for i in issues],
        "exact_duplicates": exact_duplicates,
        "fuzzy_candidates": [_serialize_fuzzy(c) for c in (run.fuzzy_candidates or [])],
    }


@router.post("/runs/{run_id}/decisions")
async def post_decisions(run_id: str, body: dict):
    """Accept either a single decision object or a {decisions: [...]} batch."""
    service = get_service()
    try:
        if "decisions" in body:
            batch = DecisionsBatchRequest.model_validate(body)
            items = batch.decisions
        else:
            items = [DecisionRequest.model_validate(body)]
        decisions = service.apply_decisions(run_id, items)
    except ServiceError as exc:
        return _error(exc)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return [d.model_dump(mode="json") for d in decisions]


@router.post("/runs/{run_id}/export")
def export_run(run_id: str):
    service = get_service()
    try:
        # Pre-check blockers for frontend-friendly response
        run = service.get_run(run_id)
        entities = service.get_entities(run_id)
        from app.pipeline.export import pending_entities

        pending = pending_entities(entities)
        unresolved_fuzzy = [
            c for c in (run.fuzzy_candidates or []) if c.resolution is None
        ]
        if pending or unresolved_fuzzy:
            blockers = [
                {
                    "entity_id": e.id,
                    "entity_type": e.entity_type.value,
                    "reason": "pending_review",
                }
                for e in pending
            ]
            for c in unresolved_fuzzy:
                blockers.append(
                    {
                        "entity_id": c.entity_id_a,
                        "entity_type": c.entity_type.value,
                        "reason": f"unresolved_fuzzy_with_{c.entity_id_b}",
                    }
                )
            return {"status": "blocked", "blockers": blockers, "artifacts": []}

        run = service.export(run_id)
        return {
            "status": "exported",
            "blockers": [],
            "artifacts": list(run.artifact_paths.keys()),
        }
    except ServiceError as exc:
        if "pending_review" in exc.message or "fuzzy" in exc.message:
            return {
                "status": "blocked",
                "blockers": [{"entity_id": "?", "entity_type": "company", "reason": exc.message}],
                "artifacts": [],
            }
        return _error(exc)


@router.get("/runs/{run_id}/artifacts/{name}")
def get_artifact(run_id: str, name: str):
    service = get_service()
    try:
        path = service.get_artifact_path(run_id, name)
    except ServiceError as exc:
        return _error(exc)
    media = "text/csv" if name.endswith(".csv") else "application/octet-stream"
    if name.endswith(".json"):
        media = "application/json"
    if name.endswith(".md"):
        media = "text/markdown"
    return FileResponse(path, media_type=media, filename=name)


@router.get("/runs/{run_id}/audit/{entity_id}")
def get_audit(run_id: str, entity_id: str):
    service = get_service()
    try:
        trail = service.get_audit(run_id, entity_id)
    except ServiceError as exc:
        return _error(exc)
    transformations = [i for i in trail.issues if i.severity == Severity.INFO]
    other_issues = [i for i in trail.issues if i.severity != Severity.INFO]
    return {
        "entity": trail.entity.model_dump(mode="json"),
        "source_rows": [
            {"source_row_number": r.source_row_number, "raw_data": r.raw_data}
            for r in trail.source_rows
        ],
        "transformations": [i.model_dump(mode="json") for i in transformations],
        "issues": [i.model_dump(mode="json") for i in other_issues],
        "decisions": [d.model_dump(mode="json") for d in trail.decisions],
        "disclaimer": trail.disclaimer,
    }


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str):
    service = get_service()
    try:
        service.delete_run(run_id)
    except ServiceError as exc:
        return _error(exc)
    return Response(status_code=204)


@router.post("/swms/extract")
async def swms_extract(file: UploadFile = File(...)):
    content = await file.read()
    suffix = Path(file.filename or "swms.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        result = extract_swms(tmp_path)
        settings = get_app_settings()
        out_dir = settings.output_path / "swms"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "swms_extract.json"
        out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["artifact_path"] = str(out_file)
        return result
    finally:
        tmp_path.unlink(missing_ok=True)
