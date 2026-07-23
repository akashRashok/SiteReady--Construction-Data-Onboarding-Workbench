"""Request and response schemas for the API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..models.mapping import MappingConfirmation


class CreateRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    reference_date: date
    is_synthetic: bool = True


class ConfirmMappingsRequest(BaseModel):
    mappings: list[MappingConfirmation]


class DecisionRequest(BaseModel):
    entity_id: str
    decision: str
    reason: str | None = None
    related_entity_id: str | None = None
