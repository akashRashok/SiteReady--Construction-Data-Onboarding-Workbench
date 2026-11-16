"""Deterministic SWMS PDF extraction with evidence retention."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

from app.pipeline.normalise import validate_abn

FIELD_LABELS: dict[str, list[str]] = {
    "swms_number": ["SWMS Number", "SWMS No", "Document Number"],
    "document_title": ["Document Title", "SWMS Title"],
    "contractor_name": [
        "Contractor Name",
        "Principal Contractor",
        "Company Name",
    ],
    "contractor_abn": ["Contractor ABN"],
    "project_name": ["Project Name", "Project"],
    "site_address": ["Site Address"],
    "activity": ["Activity", "Work Activity", "Description of Work"],
    "date_prepared": ["Date Prepared", "Prepared Date"],
    "review_date": ["Review Date", "Next Review"],
    "responsible_person": ["Responsible Person"],
}

# Prefer longer aliases first when matching table/text labels
for _key, labels in FIELD_LABELS.items():
    labels.sort(key=len, reverse=True)


def _evidence(value: str | None, source_text: str, page: int | None = None) -> dict[str, Any]:
    return {
        "value": value,
        "source_text": source_text,
        "page": page,
    }


def _normalise_pdf_text(text: str) -> str:
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    normalised = normalised.replace("\u00ad", "")
    normalised = re.sub(r"[ \t]+", " ", normalised)
    return normalised


def _clean_cell(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.replace("\n", " ")).strip()


def _find_labelled(text: str, labels: list[str]) -> tuple[str | None, str]:
    for label in labels:
        patterns = (
            # Label: value
            rf"(?im)^{re.escape(label)}\s*[:\-]\s+(.+)$",
            # Label value (no colon — common in form-style PDFs)
            rf"(?im)^{re.escape(label)}\s+(.+)$",
            rf"(?i){re.escape(label)}\s*[:\-]\s+(.+)",
            rf"(?i){re.escape(label)}\s+(.+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            value = match.group(1).strip().splitlines()[0].strip()
            # Avoid capturing the next label as the value
            if not value or value.lower() in {label.lower() for label in labels}:
                continue
            return value, match.group(0).strip().splitlines()[0].strip()
    return None, ""


def _match_field_key(label: str) -> str | None:
    cleaned = _clean_cell(label).lower().rstrip(":")
    for key, aliases in FIELD_LABELS.items():
        for alias in aliases:
            if cleaned == alias.lower():
                return key
    return None


def _extract_from_kv_tables(
    tables: list[tuple[int, list[list[str | None]]]],
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Pull labelled fields from 2-column key/value tables."""
    fields: dict[str, str] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for page_num, table in tables:
        if not table:
            continue
        for row in table:
            if not row or len(row) < 2:
                continue
            # Skip wide job-step tables
            if len([c for c in row if _clean_cell(c)]) >= 3:
                continue
            key = _match_field_key(row[0] or "")
            value = _clean_cell(row[1] if len(row) > 1 else "")
            if not key or not value or key in fields:
                continue
            fields[key] = value
            evidence[key] = _evidence(
                value,
                f"{_clean_cell(row[0])}: {value}",
                page_num,
            )
    return fields, evidence


KNOWN_SECTION_HEADINGS = [
    "High Risk Construction Work Categories",
    "High Risk Categories",
    "High-Risk Construction Work",
    "High Risk Work",
    "Personal Protective Equipment Required",
    "PPE Required",
    "PPE",
    "Personal Protective Equipment",
    "Plant and Equipment",
    "Plant & Equipment",
    "Equipment",
    "Required Competencies and Licences",
    "Required Competencies / Licences",
    "Required Competencies",
    "Competencies / Licences",
    "Licences",
    "Competencies",
    "Job Steps, Hazards and Control Measures",
    "Job Steps",
    "Job Step",
    "Worker Sign Off",
]


def _extract_list_section(text: str, headings: list[str]) -> tuple[list[str], str]:
    for heading in headings:
        other = [h for h in KNOWN_SECTION_HEADINGS if h.lower() != heading.lower()]
        stop = "|".join(re.escape(h) for h in other)
        pattern = re.compile(
            rf"(?im)^{re.escape(heading)}[^\n]*\n(.*?)(?=\n(?:{stop})\b|\Z)",
            re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            continue
        block = match.group(1).strip()
        items: list[str] = []
        for line in block.splitlines():
            cleaned = re.sub(r"^[\-\*\u2022]\s*", "", line.strip())
            if cleaned and not cleaned.endswith(":") and "|" not in cleaned:
                items.append(cleaned)
        # Some PDFs put the list as wrapped paragraphs (join soft line-breaks first)
        if not items and block:
            paragraph = re.sub(r"\s+", " ", block).strip()
            if paragraph and not paragraph.lower().startswith("step "):
                parts = [p.strip() for p in re.split(r",|;", paragraph) if p.strip()]
                # Drop tiny trailing fragments from line wraps ("lanyard.")
                parts = [p for p in parts if len(p) > 3]
                if len(parts) > 1:
                    items = parts
                elif paragraph:
                    items = [paragraph]
        if items:
            return items, match.group(0).strip()
    return [], ""


def _extract_job_steps_from_tables(
    tables: list[tuple[int, list[list[str | None]]]],
) -> tuple[list[dict[str, str]], list[str]]:
    job_steps: list[dict[str, str]] = []
    job_evidence_rows: list[str] = []
    for _page_num, table in tables:
        if not table or len(table) < 2:
            continue
        header = [_clean_cell(c).lower() for c in table[0]]
        if not any("step" in h for h in header):
            continue
        if not any("hazard" in h for h in header):
            continue
        idx_step = next((i for i, h in enumerate(header) if "step" in h or "task" in h), 0)
        idx_hazard = next((i for i, h in enumerate(header) if "hazard" in h), min(1, len(header) - 1))
        idx_risk = next(
            (i for i, h in enumerate(header) if "risk" in h),
            min(2, len(header) - 1),
        )
        idx_control = next(
            (i for i, h in enumerate(header) if "control" in h),
            min(3, len(header) - 1),
        )
        for row in table[1:]:
            if not row or not any(row):
                continue
            step = {
                "step": _clean_cell(row[idx_step]) if idx_step < len(row) else "",
                "hazard": _clean_cell(row[idx_hazard]) if idx_hazard < len(row) else "",
                "risk_rating": _clean_cell(row[idx_risk]) if idx_risk < len(row) else "",
                "control_measures": _clean_cell(row[idx_control])
                if idx_control < len(row)
                else "",
            }
            if any(step.values()):
                job_steps.append(step)
                job_evidence_rows.append(" | ".join(step.values()))
    return job_steps, job_evidence_rows


def extract_swms(pdf_path: Path) -> dict[str, Any]:
    """Extract labelled fields and job-steps table. LLM not required."""
    with pdfplumber.open(pdf_path) as pdf:
        page_texts: list[tuple[int, str]] = []
        tables: list[tuple[int, list[list[str | None]]]] = []
        for idx, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            page_texts.append((idx, _normalise_pdf_text(raw)))
            for table in page.extract_tables() or []:
                tables.append((idx, table))
        full_text = "\n".join(t for _, t in page_texts)

    fields: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    # 1) Key/value tables (common in Word/PDF exports)
    kv_fields, kv_evidence = _extract_from_kv_tables(tables)
    fields.update(kv_fields)
    evidence.update(kv_evidence)

    # 2) Labelled text lines (with or without colon)
    for key, labels in FIELD_LABELS.items():
        if fields.get(key):
            continue
        value, src = _find_labelled(full_text, labels)
        page_num = None
        for p, t in page_texts:
            if src and src in t:
                page_num = p
                break
        if key == "contractor_abn" and value:
            abn, err = validate_abn(value)
            fields[key] = abn
            evidence[key] = _evidence(
                abn,
                src + (f" (validation: {err})" if err else " (ABN checksum ok)"),
                page_num,
            )
            if err:
                evidence[key]["validation_error"] = err
                evidence[key]["raw_value"] = value
        else:
            fields[key] = value
            evidence[key] = _evidence(value, src or "not found", page_num)

    # Normalise ABN if it came from a table
    if fields.get("contractor_abn") and "validation_error" not in evidence.get(
        "contractor_abn", {}
    ):
        abn, err = validate_abn(str(fields["contractor_abn"]))
        raw = str(fields["contractor_abn"])
        fields["contractor_abn"] = abn
        prev = evidence.get("contractor_abn", _evidence(raw, raw))
        evidence["contractor_abn"] = _evidence(
            abn,
            str(prev.get("source_text") or raw)
            + (f" (validation: {err})" if err else " (ABN checksum ok)"),
            prev.get("page"),
        )
        if err:
            evidence["contractor_abn"]["validation_error"] = err
            evidence["contractor_abn"]["raw_value"] = raw

    # If document_title empty but activity filled (common on form SWMS), mirror it
    if not fields.get("document_title") and fields.get("activity"):
        fields["document_title"] = fields["activity"]
        evidence["document_title"] = _evidence(
            fields["activity"],
            f"Activity: {fields['activity']}",
            evidence.get("activity", {}).get("page"),
        )

    high_risk, hr_src = _extract_list_section(
        full_text,
        [
            "High Risk Construction Work Categories",
            "High Risk Categories",
            "High-Risk Construction Work",
            "High Risk Work",
        ],
    )
    fields["high_risk_categories"] = high_risk
    evidence["high_risk_categories"] = _evidence(
        "; ".join(high_risk) if high_risk else None,
        hr_src or "not found",
    )

    ppe, ppe_src = _extract_list_section(
        full_text,
        [
            "Personal Protective Equipment Required",
            "PPE Required",
            "PPE",
            "Personal Protective Equipment",
        ],
    )
    fields["ppe_required"] = ppe
    evidence["ppe_required"] = _evidence(
        "; ".join(ppe) if ppe else None, ppe_src or "not found"
    )

    plant, plant_src = _extract_list_section(
        full_text, ["Plant and Equipment", "Plant & Equipment", "Equipment"]
    )
    fields["plant_and_equipment"] = plant
    evidence["plant_and_equipment"] = _evidence(
        "; ".join(plant) if plant else None, plant_src or "not found"
    )

    comps, comps_src = _extract_list_section(
        full_text,
        [
            "Required Competencies and Licences",
            "Required Competencies / Licences",
            "Required Competencies",
            "Competencies / Licences",
            "Licences",
            "Competencies",
        ],
    )
    fields["required_competencies_licences"] = comps
    evidence["required_competencies_licences"] = _evidence(
        "; ".join(comps) if comps else None, comps_src or "not found"
    )

    job_steps, job_evidence_rows = _extract_job_steps_from_tables(tables)

    # Fallback: pipe-delimited job step lines in plain text
    if not job_steps:
        for line in full_text.splitlines():
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                continue
            if parts[0].lower().startswith("step") and "hazard" in parts[1].lower():
                continue
            step = {
                "step": parts[0],
                "hazard": parts[1],
                "risk_rating": parts[2],
                "control_measures": parts[3],
            }
            job_steps.append(step)
            job_evidence_rows.append(line.strip())

    fields["job_steps"] = job_steps
    evidence["job_steps"] = {
        "value": job_steps,
        "source_text": "\n".join(job_evidence_rows) if job_evidence_rows else "table not found",
        "page": None,
    }

    return {
        "disclaimer": "Independent demo. Synthetic data.",
        "source_file": pdf_path.name,
        "fields": fields,
        "evidence": evidence,
        "llm_used": False,
    }
