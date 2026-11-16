# Product: Construction Data Onboarding Workbench

**Type:** Standalone portfolio demonstration  
**Affiliation:** Independent work. Not affiliated with, integrated into, or endorsed by any commercial product.  
**Data:** Synthetic only — UI, README, Markdown, and JSON metadata show *Independent demo. Synthetic data.*

---

## Problem

Construction customers migrate onto new systems by importing years of operational history from spreadsheets. Worker, subcontractor, and certification data arrives denormalised, inconsistent, duplicated, and formatted differently from the target schema. Cleaning that by hand is slow, error-prone, and hard to explain to the customer.

Implementation engineers need a controlled path from messy CSV → reviewed entities → import-ready files, with every exclusion and transformation defensible.

---

## What was built

A lean end-to-end **onboarding workbench**: upload one messy construction CSV, map columns, split into canonical entities, normalise and validate deterministically, review issues and duplicates with a mandatory human gate, then export clean packages plus full lineage and a customer-facing summary.

A **secondary SWMS flow** extracts structured fields from a machine-readable Safe Work Method Statement PDF (UI + API), with source evidence retained per value.

### Primary outcome (CSV onboarding)

An implementation engineer can:

1. Create a named import run with a reference date (for reproducible expiry warnings).
2. Upload a denormalised worker–certification CSV.
3. Confirm source → canonical column mappings (low-confidence mappings require confirmation; columns can be ignored).
4. Review Company, Worker, and Certification entities with raw vs normalised values, validation issues, exact duplicates, and fuzzy candidates.
5. Approve (including **Approve all** for pending records without errors), reject, override errors (with reason), and resolve fuzzy pairs.
6. Export import-ready and excluded CSVs, exception report, audit log, and an implementation summary — each artifact listed with a short description.
7. Trace any exported field back to its source row in Audit.

### Secondary outcome (SWMS)

Extract structured fields from one machine-readable SWMS PDF:

- **UI:** sidenav **Secondary → SWMS** (always reachable; not gated by a CSV run)
- **API:** `POST /swms/extract`
- **Output:** downloadable `swms_extract.json` (also written under `outputs/swms/`)

Extraction is deterministic (`pdfplumber`): labelled lines (`Label: value` or `Label value`), two-column key/value tables, list sections, and job-step tables across pages. ABN checksum uses the same validator as the CSV pipeline. Scanned/image-only PDFs are out of scope (no OCR).

Fixture: `fixtures/SWMS_Roof_Sheeting_Working_at_Heights.pdf`.

---

## Users

| Role | Need |
| --- | --- |
| **Implementation / solutions engineer** (primary) | Convert a messy historical export into a safe import package without inventing data or silently merging identities. |
| **Customer success / account owner** (secondary) | Understand what was received, cleaned, imported, excluded, and decided — with reasons. |

---

## Product principles (shipped)

| Principle | How it shows up |
| --- | --- |
| **Deterministic first** | Mapping, normalisation, validation, exact/fuzzy dedupe, IDs, counts, export eligibility, and SWMS field extraction are ordinary code. |
| **AI is advisory only** | LLM drafts summaries and fuzzy *explanations*. It never invents source values, merges identities, approves records, or calculates totals. |
| **Human gate is mandatory** | No entity enters an import-ready export without an explicit recorded decision. Error overrides require a reason. |
| **Full lineage** | Source row numbers, raw values, transformations, issues, duplicate links, decisions, artifacts, and model provider/model are persisted. SWMS keeps `source_text` (+ page when known) per field. |
| **Honest privacy** | Default local Ollama keeps prompts on-machine. Hosted providers are opt-in and surface a visible warning. No production compliance claims. |
| **Safe exports** | CSV files always start with real headers on row one. Disclaimers live in UI, Markdown, and JSON metadata only. |

See [AI_BOUNDARIES.md](AI_BOUNDARIES.md) for the full AI contract.

---

## Experience

GCP Console–style shell: top bar + left nav. Core **Workflow** steps are gated by run status. **Secondary → SWMS** is always available.

### Workflow

| Step | What the user does |
| --- | --- |
| **1. Upload** | Name the run, set reference date, upload CSV (`fixtures/messy_construction_records_28_rows.csv`). List/open/delete prior runs. |
| **2. Mapping** | Review proposed mappings (method, confidence, samples). Confirm or ignore columns; confirm starts processing. |
| **3. Review** | Filter entities; expand raw vs normalised and issues. Approve / **Approve all** (pending, no errors) / Override / Reject; resolve fuzzy pairs. |
| **4. Export** | Blocked while anything is pending. On success: grouped artifact table (import-ready, excluded, reports) with hints and download links. |
| **5. Audit** | Pick an entity and walk source rows → transformations → issues → decisions → export membership. |

### Secondary: SWMS

| UI area | Content |
| --- | --- |
| Upload | PDF input; synthetic-data notice; Extract |
| Document fields | SWMS number, title/activity, contractor, ABN, project, site, dates, responsible person — value + evidence |
| Lists | High-risk categories, PPE, plant/equipment, competencies |
| Job steps | Step, hazard, risk rating, control measures |
| Download | Client-side `swms_extract.json` from the API response |

### Model connectors (top bar)

- Model chip (not a separate Settings button) opens connectors: provider, model, hosted API keys.
- Local = amber chip; hosted = red warning (prompts leave this machine).
- Overrides in `data/llm_settings.json` (gitignored); **Reset to .env** clears UI overrides.

---

## Pipeline (backend)

Deterministic stages behind a FastAPI service and SQLite repository:

| Stage | Responsibility |
| --- | --- |
| **Ingest** | Parse CSV, assign source row numbers, store raw rows. |
| **Profile / map** | Propose column mappings with confidence. |
| **Split** | Denormalised rows → Company, Worker, Certification with stable IDs. |
| **Normalise** | Names, dates, phones, emails, enums, ABN checksum, etc. |
| **Validate** | Errors and warnings with field-level evidence and import consequence. |
| **Dedupe** | Exact collapse with lineage; fuzzy candidates with scored evidence. |
| **Export** | Eligibility + parent-child blocking; write artifact pack. |
| **SWMS** (secondary) | PDF text/tables → structured fields + evidence → `swms_extract.json`. |

Persistence: five-table SQLite schema (`import_runs`, `source_rows`, `entities`, `issues`, `decisions`) behind a `Repository` protocol so Postgres can be added later without rewriting pipeline stages.

---

## AI usage (advisory)

| Call | Purpose | Guardrail |
| --- | --- | --- |
| Implementation summary | Customer-facing note from structured counts/decisions | Must not invent numbers absent from input |
| Exception narrative | Readable grouping of deterministic issues | Counts still from pipeline |
| Fuzzy explanation | Strength + supporting/conflicting evidence + recommended check | Human still chooses merge / separate / defer |

Providers behind one `LLMAdapter`: **Ollama** (default, e.g. `llama3.1:latest`), **OpenAI**, **Anthropic**, **Gemini**, or **fallback** templates. Structured calls validate → retry once → deterministic fallback. Missing keys or stopped Ollama do not crash the run.

SWMS extraction does **not** require the LLM (`llm_used: false` in the current demo path).

---

## Artifacts

### Per CSV export (`outputs/<run_id>/`)

| File | Purpose |
| --- | --- |
| `*_import_ready.csv` | Approved entities eligible for import (headers on row one) |
| `*_excluded.csv` | Excluded entities with reasons |
| `exception_report.json` / `.md` | Deterministic issue counts; MD may append advisory narrative |
| `audit_log.json` | Run, entities, issues, decisions |
| `implementation_summary.md` | Customer-facing note (AI draft or deterministic template) |

### Per SWMS extract (`outputs/swms/`)

| File | Purpose |
| --- | --- |
| `swms_extract.json` | Fields, evidence, disclaimer, source filename |

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React + TypeScript + Vite |
| Backend | Python 3.12+ / FastAPI / Pydantic v2 |
| Persistence | SQLite via `Repository` |
| AI | Ollama by default; optional hosted adapters |
| PDF | `pdfplumber` for SWMS |
| Fixtures | Messy CSV + SWMS PDF under `fixtures/` |
| Tests | Backend pytest (unit, integration, fixture e2e); frontend typecheck/build |

Clone-and-run: no cloud account, no hosted migrations, no required API keys for the core demo.

---

## What is deliberately out of scope

- Real customer data; auth / multi-tenancy / multi-user accounts  
- Cloud storage, signed URLs, production encryption/compliance claims  
- Direct import into commercial construction systems  
- Autonomous approvals or automatic identity merges  
- OCR for scanned/handwritten PDFs; arbitrary Excel workflows  
- Tying SWMS extracts to a CSV import run in SQLite  
- MCP server and Postgres migration (optional post-demo extensions)

---

## Seeded demo path

1. Create a run (e.g. `Harbour demo`) with a fixed reference date for reproducible expiry counts.
2. Upload `fixtures/messy_construction_records_28_rows.csv`.
3. Confirm mappings (especially low-confidence / ignore decisions).
4. Review: override one error with a reason, reject one company, **Approve all** (or approve selectively), resolve fuzzy pairs.
5. Export and download the artifact pack (use the per-file hints on the Export screen).
6. In Audit, trace an exported field to its source row.
7. Optional: **Secondary → SWMS** → upload `fixtures/SWMS_Roof_Sheeting_Working_at_Heights.pdf` → review fields/lists/job steps → download `swms_extract.json`.

Setup and run commands: [README.md](README.md).  
Build specification: [PRD_Construction_Data_Onboarding_Workbench_v2_lean.md](PRD_Construction_Data_Onboarding_Workbench_v2_lean.md).  
AI contract: [AI_BOUNDARIES.md](AI_BOUNDARIES.md).

---

## Success criteria (product)

The workbench succeeds when a reviewer can, without cloud credentials:

- Complete upload → map → review → export → audit on the synthetic CSV fixture.
- Explain every exclusion from evidence and recorded decisions.
- See that AI never bypassed the human gate or invented source values.
- Re-run the same input and reference date and get the same IDs and issue set from deterministic stages.
- Open **Secondary → SWMS**, extract the fixture PDF, see populated fields with evidence, and download `swms_extract.json`.
