"""Deterministic SWMS PDF extraction with evidence retention."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

from app.pipeline.normalise import validate_abn

FIELD_LABELS: dict[str, list[str]] = {
    "swms_number": ["SWMS Number", "SWMS No", "Document Number"],
    "document_title": ["Document Title", "Title", "SWMS Title"],
    "contractor_name": ["Contractor Name", "Contractor", "Company Name"],
    "contractor_abn": ["Contractor ABN", "ABN"],
    "project_name": ["Project Name", "Project"],
    "site_address": ["Site Address", "Address", "Location"],
    "activity": ["Activity", "Work Activity", "Description of Work"],
    "date_prepared": ["Date Prepared", "Prepared Date", "Date"],
    "review_date": ["Review Date", "Next Review"],
    "responsible_person": ["Responsible Person", "Responsible", "Supervisor"],
}


def _evidence(value: str | None, source_text: str, page: int | None = None) -> dict[str, Any]:
    return {
        "value": value,
        "source_text": source_text,
        "page": page,
    }


def _find_labelled(text: str, labels: list[str]) -> tuple[str | None, str]:
    for label in labels:
        # Label: value  OR  Label value on same line
        pattern = re.compile(
            rf"{re.escape(label)}\s*[:\-]\s*(.+)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            value = match.group(1).strip().splitlines()[0].strip()
            return value, match.group(0).strip()
    return None, ""


KNOWN_SECTION_HEADINGS = [
    "High Risk Categories",
    "High-Risk Construction Work",
    "High Risk Work",
    "PPE Required",
    "PPE",
    "Personal Protective Equipment",
    "Plant and Equipment",
    "Plant & Equipment",
    "Equipment",
    "Required Competencies",
    "Competencies / Licences",
    "Licences",
    "Competencies",
    "Job Steps",
    "Job Step",
]


def _extract_list_section(text: str, headings: list[str]) -> tuple[list[str], str]:
    for heading in headings:
        # Capture until the next known section heading
        other = [h for h in KNOWN_SECTION_HEADINGS if h.lower() != heading.lower()]
        stop = "|".join(re.escape(h) for h in other)
        pattern = re.compile(
            rf"{re.escape(heading)}\s*[:\-]?\s*\n(.*?)(?=\n(?:{stop})\b|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            block = match.group(1).strip()
            items: list[str] = []
            for line in block.splitlines():
                cleaned = re.sub(r"^[\-\*\u2022]\s*", "", line.strip())
                if cleaned and not cleaned.endswith(":"):
                    items.append(cleaned)
            return items, match.group(0).strip()
    return [], ""


def extract_swms(pdf_path: Path) -> dict[str, Any]:
    """Extract labelled fields and job-steps table. LLM not required."""
    with pdfplumber.open(pdf_path) as pdf:
        page_texts: list[tuple[int, str]] = []
        tables: list[list[list[str | None]]] = []
        for idx, page in enumerate(pdf.pages, start=1):
            page_texts.append((idx, page.extract_text() or ""))
            for table in page.extract_tables() or []:
                tables.append(table)
        full_text = "\n".join(t for _, t in page_texts)

    fields: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    for key, labels in FIELD_LABELS.items():
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

    high_risk, hr_src = _extract_list_section(
        full_text,
        ["High Risk Categories", "High-Risk Construction Work", "High Risk Work"],
    )
    fields["high_risk_categories"] = high_risk
    evidence["high_risk_categories"] = _evidence(
        "; ".join(high_risk) if high_risk else None,
        hr_src or "not found",
    )

    ppe, ppe_src = _extract_list_section(full_text, ["PPE Required", "PPE", "Personal Protective Equipment"])
    fields["ppe_required"] = ppe
    evidence["ppe_required"] = _evidence("; ".join(ppe) if ppe else None, ppe_src or "not found")

    plant, plant_src = _extract_list_section(
        full_text, ["Plant and Equipment", "Plant & Equipment", "Equipment"]
    )
    fields["plant_and_equipment"] = plant
    evidence["plant_and_equipment"] = _evidence(
        "; ".join(plant) if plant else None, plant_src or "not found"
    )

    comps, comps_src = _extract_list_section(
        full_text,
        ["Required Competencies", "Competencies / Licences", "Licences", "Competencies"],
    )
    fields["required_competencies_licences"] = comps
    evidence["required_competencies_licences"] = _evidence(
        "; ".join(comps) if comps else None, comps_src or "not found"
    )

    job_steps: list[dict[str, str]] = []
    job_evidence_rows: list[str] = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [((c or "").strip().lower()) for c in table[0]]
        # Look for job step style headers
        if not any("step" in h or "hazard" in h for h in header):
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
                "step": (row[idx_step] or "").strip() if idx_step < len(row) else "",
                "hazard": (row[idx_hazard] or "").strip() if idx_hazard < len(row) else "",
                "risk_rating": (row[idx_risk] or "").strip() if idx_risk < len(row) else "",
                "control_measures": (row[idx_control] or "").strip()
                if idx_control < len(row)
                else "",
            }
            if any(step.values()):
                job_steps.append(step)
                job_evidence_rows.append(" | ".join(step.values()))
        if job_steps:
            break

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
