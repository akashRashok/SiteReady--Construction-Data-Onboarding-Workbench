"""Generate a synthetic machine-readable SWMS PDF fixture."""

from __future__ import annotations

from pathlib import Path


def build_pdf(path: Path) -> None:
    # Minimal PDF with embedded text that pdfplumber can extract.
    lines = [
        "SAFE WORK METHOD STATEMENT",
        "SWMS Number: SWMS-2024-0142",
        "Document Title: Roof Sheeting Working at Heights",
        "Contractor Name: Apex Build Pty Ltd",
        "Contractor ABN: 51 824 753 556",
        "Project Name: Riverside Warehouse Roof Replacement",
        "Site Address: 42 Harbour Road, Newcastle NSW 2300",
        "Activity: Installation of metal roof sheeting at height",
        "Date Prepared: 2024-03-12",
        "Review Date: 2025-03-12",
        "Responsible Person: Sarah Chen",
        "",
        "High Risk Categories:",
        "- Working at heights",
        "- Use of mobile plant",
        "- Risk of falling objects",
        "",
        "PPE Required:",
        "- Hard hat",
        "- Safety harness",
        "- Non-slip footwear",
        "- Cut-resistant gloves",
        "",
        "Plant and Equipment:",
        "- Scissor lift",
        "- Edge protection",
        "- Screw gun",
        "",
        "Required Competencies / Licences:",
        "- White Card",
        "- Working at Heights",
        "- EWP licence",
        "",
        "Job Steps:",
        "Step | Hazard | Risk | Control",
        "1. Site setup | Uneven ground | Medium | Inspect and barricade work area",
        "2. Install edge protection | Fall from height | High | Certified edge protection before work",
        "3. Lift sheets | Falling objects | High | Exclusion zone and tagged lifting gear",
        "4. Fix sheeting | Cuts and falls | High | Harness, gloves, sequenced fixing",
    ]
    # Build a simple one-page PDF
    content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
    first = True
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if first:
            content_lines.append(f"({safe}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({safe}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(out))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    target = root / "fixtures" / "SWMS_Roof_Sheeting_Working_at_Heights.pdf"
    build_pdf(target)
    print(f"Wrote {target}")
