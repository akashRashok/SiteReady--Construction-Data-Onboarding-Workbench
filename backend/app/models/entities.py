"""Canonical entity models (section 8 of the PRD)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .enums import CertType, CompanyRole, ReviewStatus, Trade


class Company(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    company_name: str
    canonical_name: str
    abn: str | None = None
    role: CompanyRole
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = []


class Worker(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    full_name: str
    trade: Trade
    email: str | None = None
    phone: str | None = None
    company_id: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = []


class Certification(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    worker_id: str
    cert_type: CertType
    cert_number: str
    issue_date: str | None = None
    expiry_date: str | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_rows: list[int] = []
