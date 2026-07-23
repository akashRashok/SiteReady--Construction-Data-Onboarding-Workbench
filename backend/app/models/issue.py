"""Issue and decision records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .enums import DecisionType, EntityType, Severity


class Issue(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    run_id: str
    rule_id: str
    severity: Severity
    entity_type: EntityType | None = None
    entity_id: str | None = None
    source_rows: list[int] = []
    field: str | None = None
    raw_value: str | None = None
    normalised_value: str | None = None
    message: str
    import_consequence: str | None = None
    created_at: datetime


class Decision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    run_id: str
    entity_id: str
    decision: DecisionType
    reason: str | None = None
    related_entity_id: str | None = None
    created_at: datetime
