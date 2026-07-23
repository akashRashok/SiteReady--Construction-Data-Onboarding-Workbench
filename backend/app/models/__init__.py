"""Domain models and enums for the onboarding workbench."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    CREATED = "created"
    INGESTED = "ingested"
    MAPPING_PENDING = "mapping_pending"
    PROCESSING = "processing"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    EXPORTED = "exported"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    APPROVED_WITH_OVERRIDE = "approved_with_override"
    REJECTED = "rejected"
    EXCLUDED_BY_RULE = "excluded_by_rule"


class EntityType(str, Enum):
    COMPANY = "company"
    WORKER = "worker"
    CERTIFICATION = "certification"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IdConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompanyRole(str, Enum):
    HEAD_CONTRACTOR = "head_contractor"
    SUBCONTRACTOR = "subcontractor"


class Trade(str, Enum):
    CARPENTER = "carpenter"
    ELECTRICIAN = "electrician"
    PLUMBER = "plumber"
    CONCRETER = "concreter"
    STEELFIXER = "steelfixer"
    CRANE_OPERATOR = "crane_operator"
    SCAFFOLDER = "scaffolder"
    LABOURER = "labourer"
    SITE_SUPERVISOR = "site_supervisor"
    TRAFFIC_CONTROLLER = "traffic_controller"
    OTHER = "other"


class CertType(str, Enum):
    WHITE_CARD = "white_card"
    HRWL = "hrwl"
    WORKING_AT_HEIGHTS = "working_at_heights"
    FIRST_AID = "first_aid"
    ASBESTOS_AWARENESS = "asbestos_awareness"
    TRAFFIC_MANAGEMENT = "traffic_management"
    EWP = "ewp"
    OTHER = "other"


class DecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    OVERRIDE = "override"
    MERGE = "merge"
    KEEP_SEPARATE = "keep_separate"
    DEFER = "defer"


class MappingConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MappingMethod(str, Enum):
    EXACT_HEADER = "exact_header"
    ALIAS_DICTIONARY = "alias"
    HEURISTIC = "heuristic"
    UNMAPPED = "unmapped"


class CompanyData(BaseModel):
    id: str
    company_name: str
    canonical_name: str
    abn: str | None = None
    role: CompanyRole
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = Field(default_factory=list)
    id_confidence: IdConfidence = IdConfidence.MEDIUM
    duplicate_of: str | None = None
    duplicate_source_rows: list[int] = Field(default_factory=list)
    duplicate_count: int = 1


class WorkerData(BaseModel):
    id: str
    full_name: str
    trade: Trade
    email: str | None = None
    phone: str | None = None
    company_id: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = Field(default_factory=list)
    id_confidence: IdConfidence = IdConfidence.MEDIUM
    duplicate_of: str | None = None
    duplicate_source_rows: list[int] = Field(default_factory=list)
    duplicate_count: int = 1


class CertificationData(BaseModel):
    id: str
    worker_id: str
    cert_type: CertType
    cert_number: str
    issue_date: str | None = None
    expiry_date: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = Field(default_factory=list)
    id_confidence: IdConfidence = IdConfidence.MEDIUM
    duplicate_of: str | None = None
    duplicate_source_rows: list[int] = Field(default_factory=list)
    duplicate_count: int = 1


class ImportRun(BaseModel):
    id: str
    name: str
    status: RunStatus
    source_filename: str | None = None
    source_path: str | None = None
    is_synthetic: bool = True
    reference_date: date
    llm_provider: str | None = None
    llm_model: str | None = None
    mappings: list[ColumnMapping] | None = None
    fuzzy_candidates: list[FuzzyCandidate] | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SourceRow(BaseModel):
    id: int | None = None
    run_id: str
    source_row_number: int
    raw_data: dict[str, Any]
    created_at: datetime


class EntityRecord(BaseModel):
    id: str
    run_id: str
    entity_type: EntityType
    data: dict[str, Any]
    parent_id: str | None = None
    id_confidence: IdConfidence
    review_status: ReviewStatus
    source_rows: list[int]
    created_at: datetime
    updated_at: datetime


class IssueRecord(BaseModel):
    id: int | None = None
    run_id: str
    rule_id: str
    severity: Severity
    entity_type: EntityType | None = None
    entity_id: str | None = None
    source_rows: list[int] = Field(default_factory=list)
    field: str | None = None
    raw_value: str | None = None
    normalised_value: str | None = None
    message: str
    import_consequence: str
    created_at: datetime


class DecisionRecord(BaseModel):
    id: int | None = None
    run_id: str
    entity_id: str
    decision: DecisionType
    reason: str | None = None
    related_entity_id: str | None = None
    created_at: datetime


class ColumnMapping(BaseModel):
    source_column: str
    target_entity: EntityType | None = None
    target_field: str | None = None
    method: MappingMethod
    confidence: MappingConfidence
    sample_values: list[str] = Field(default_factory=list)
    confirmed: bool = False


class FuzzyEvidence(BaseModel):
    name_similarity: float | None = None
    same_company: bool | None = None
    matching_email: bool | None = None
    matching_phone: bool | None = None
    matching_cert_number: bool | None = None
    matching_abn: bool | None = None
    conflicting_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FuzzyCandidate(BaseModel):
    entity_type: EntityType
    entity_id_a: str
    entity_id_b: str
    score: float
    evidence: FuzzyEvidence
    llm_explanation: dict[str, Any] | None = None
    resolution: Literal["merge", "keep_separate", "defer"] | None = None


class CreateRunRequest(BaseModel):
    name: str
    reference_date: date
    is_synthetic: bool = True


class ConfirmMappingItem(BaseModel):
    source_column: str
    target_entity: EntityType | None = None
    target_field: str | None = None
    method: MappingMethod | None = None
    confidence: MappingConfidence | None = None
    sample_values: list[str] = Field(default_factory=list)
    confirmed: bool = True


class ConfirmMappingsRequest(BaseModel):
    mappings: list[ConfirmMappingItem]


class DecisionRequest(BaseModel):
    entity_id: str
    decision: DecisionType
    reason: str | None = None
    related_entity_id: str | None = None


class DecisionsBatchRequest(BaseModel):
    decisions: list[DecisionRequest]


class AuditTrail(BaseModel):
    entity: EntityRecord
    issues: list[IssueRecord]
    decisions: list[DecisionRecord]
    source_rows: list[SourceRow]
    disclaimer: str = "Independent demo. Synthetic data."


# Resolve forward refs for ImportRun
ImportRun.model_rebuild()
