"""CSV ingest stage."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from app.models import IssueRecord, Severity, SourceRow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def ingest_csv(
    run_id: str,
    content: bytes | str,
) -> tuple[list[SourceRow], list[IssueRecord], list[str]]:
    """Parse CSV into source rows. Row numbers start at 2 (spreadsheet convention)."""
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.reader(io.StringIO(text))
    rows_list = list(reader)
    if not rows_list:
        return [], [], []

    headers = [h.strip() for h in rows_list[0]]
    expected_cols = len(headers)
    source_rows: list[SourceRow] = []
    issues: list[IssueRecord] = []
    now = _utcnow()

    for idx, values in enumerate(rows_list[1:], start=2):
        if len(values) != expected_cols:
            # Pad or truncate for raw capture, but flag structural error
            padded = list(values) + [""] * max(0, expected_cols - len(values))
            padded = padded[:expected_cols]
            raw: dict[str, Any] = {headers[i]: padded[i] for i in range(expected_cols)}
            raw["__structural_mismatch"] = True
            raw["__raw_column_count"] = len(values)
            issues.append(
                IssueRecord(
                    run_id=run_id,
                    rule_id="structural_column_mismatch",
                    severity=Severity.ERROR,
                    entity_type=None,
                    entity_id=None,
                    source_rows=[idx],
                    field=None,
                    raw_value=str(values),
                    normalised_value=None,
                    message=(
                        f"Row {idx} has {len(values)} columns; expected {expected_cols}"
                    ),
                    import_consequence="Row retained for review; mapping may be incomplete",
                    created_at=now,
                )
            )
        else:
            raw = {headers[i]: values[i] for i in range(expected_cols)}

        source_rows.append(
            SourceRow(
                run_id=run_id,
                source_row_number=idx,
                raw_data=raw,
                created_at=now,
            )
        )

    return source_rows, issues, headers
