"""Column mapping proposal models (PRD section 10)."""

from __future__ import annotations

from pydantic import BaseModel

from .enums import EntityType, MappingConfidence, MappingMethod


class ColumnMapping(BaseModel):
    source_column: str
    target_entity: EntityType | None = None
    target_field: str | None = None
    method: MappingMethod
    confidence: MappingConfidence
    sample_values: list[str] = []
    confirmed: bool = False


class MappingConfirmation(BaseModel):
    source_column: str
    target_entity: EntityType | None = None
    target_field: str | None = None
