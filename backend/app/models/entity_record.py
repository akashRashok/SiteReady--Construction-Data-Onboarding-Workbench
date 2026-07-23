"""Polymorphic stored entity record (maps to the `entities` table)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from .enums import EntityType, IdConfidence, ReviewStatus


class EntityRecord(BaseModel):
    """A single stored entity of any type.

    The `data` field holds the canonical fields for the entity type. Type safety
    for those fields is provided by the Company / Worker / Certification models at
    the point of construction; this record keeps the schema small (PRD section 15).
    """

    model_config = ConfigDict(use_enum_values=True)

    id: str
    run_id: str
    entity_type: EntityType
    data: dict[str, Any]
    parent_id: str | None = None
    id_confidence: IdConfidence
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = []
    created_at: datetime
    updated_at: datetime
