"""Canonical enumerations shared across the pipeline."""

from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    COMPANY = "company"
    WORKER = "worker"
    CERTIFICATION = "certification"


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


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    APPROVED_WITH_OVERRIDE = "approved_with_override"
    REJECTED = "rejected"
    EXCLUDED_BY_RULE = "excluded_by_rule"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IdConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RunStatus(str, Enum):
    CREATED = "created"
    INGESTED = "ingested"
    MAPPING_PENDING = "mapping_pending"
    PROCESSING = "processing"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    EXPORTED = "exported"
    FAILED = "failed"


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
    ALIAS = "alias"
    HEURISTIC = "heuristic"
    UNMAPPED = "unmapped"
