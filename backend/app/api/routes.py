"""API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..config import Settings
from ..deps import get_repository, get_settings_dep
from ..models.run import ImportRun
from ..repository import Repository
from ..services.runs import RunService
from .schemas import CreateRunRequest

router = APIRouter()


def _run_service(repo: Repository, settings: Settings) -> RunService:
    return RunService(repo, settings)


@router.post("/runs", response_model=ImportRun, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: CreateRunRequest,
    repo: Repository = Depends(get_repository),
    settings: Settings = Depends(get_settings_dep),
) -> ImportRun:
    return _run_service(repo, settings).create_run(
        payload.name, payload.reference_date, payload.is_synthetic
    )


@router.get("/runs", response_model=list[ImportRun])
def list_runs(
    repo: Repository = Depends(get_repository),
    settings: Settings = Depends(get_settings_dep),
) -> list[ImportRun]:
    return _run_service(repo, settings).list_runs()


@router.get("/runs/{run_id}", response_model=ImportRun)
def get_run(
    run_id: str,
    repo: Repository = Depends(get_repository),
    settings: Settings = Depends(get_settings_dep),
) -> ImportRun:
    run = _run_service(repo, settings).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: str,
    repo: Repository = Depends(get_repository),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    deleted = _run_service(repo, settings).delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
