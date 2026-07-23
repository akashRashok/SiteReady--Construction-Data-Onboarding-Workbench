"""Compatibility helpers for schema versioning (legacy import path)."""

from __future__ import annotations

from app.repository.sqlite import SchemaVersionError

SCHEMA_VERSION = "1"

__all__ = ["SCHEMA_VERSION", "SchemaVersionError"]
