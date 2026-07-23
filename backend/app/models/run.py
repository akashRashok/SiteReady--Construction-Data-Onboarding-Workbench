"""Run and source-row models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from .enums import RunStatus


class ImportRun(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    name: str
    status: RunStatus = RunStatus.CREATED
    source_filename: str | None = None
    source_path: str | None = None
    is_synthetic: bool = True
    reference_date: str
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: datetime
    updated_at: datetime


class SourceRow(BaseModel):
    id: str
    run_id: str
    source_row_number: int
    raw_data: dict[str, Any]
    created_at: datetime
