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

It is designed to look and behave like a small internal delivery tool (GCP Console–style shell), not a chat product with AI in the critical path.

### Primary outcome

An implementation engineer can:

1. Create a named import run with a fixed reference date (for reproducible expiry warnings).
2. Upload a denormalised worker–certification CSV.
3. Confirm source → canonical column mappings (low-confidence mappings require confirmation; columns can be ignored).
4. Review Company, Worker, and Certification entities with raw vs normalised values, validation issues, exact duplicates, and fuzzy candidates.
5. Approve, reject, override errors (with reason), and resolve fuzzy pairs.
6. Export import-ready and excluded CSVs, exception report, audit log, and an implementation summary.
7. Trace any exported field back to its source row in Audit.

### Secondary outcome

Extract structured fields from one machine-readable Safe Work Method Statement (SWMS) PDF via API (`POST /swms/extract`), retaining source evidence per field.

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
| **Deterministic first** | Mapping proposals, normalisation, validation, exact/fuzzy dedupe, IDs, counts, and export eligibility are ordinary code — re-runnable and testable without a model. |
| **AI is advisory only** | LLM drafts summaries and fuzzy *explanations*. It never invents source values, merges identities, approves records, or calculates totals. |
| **Human gate is mandatory** | No entity enters an import-ready export without an explicit recorded decision. Error overrides require a reason. |
| **Full lineage** | Source row numbers, raw values, transformations, issues, duplicate links, decisions, artifacts, and model provider/model are persisted. |
| **Honest privacy** | Default local Ollama keeps prompts on-machine. Hosted providers are opt-in and surface a visible warning. No production compliance claims. |
| **Safe exports** | CSV files always start with real headers on row one. Disclaimers live in UI, Markdown, and JSON metadata only. |

See [AI_BOUNDARIES.md](AI_BOUNDARIES.md) for the full AI contract.

---

## Experience: five-step workflow

The UI is a top bar + left nav shell with five reachable steps gated by run status.

### 1. Upload

- Create or select a run; set reference date.
- Upload CSV (seeded fixture: `fixtures/messy_construction_records.csv`).
- Delete a run (DB rows + local upload/output artifacts).

### 2. Mapping

- Profiled columns with proposed canonical targets and confidence.
- Confirm mappings; ignore columns that should not map.
- Confirming triggers pipeline processing (split → normalise → validate → dedupe).

### 3. Review

- Dense entity table with status filters and chips.
- Expandable detail: raw vs normalised, issues with evidence, automatic clean-ups.
- Decisions: approve, reject, override (reason), fuzzy resolve (merge / keep separate / defer).
- Parent–child integrity respected (e.g. blocked certs when company/worker excluded).

### 4. Export

- Generate import-ready and excluded CSVs per entity type.
- Exception report (Markdown), audit/decisions JSON, implementation summary.
- Download artifacts; proceed to Audit when ready.

### 5. Audit

- Look up an entity and walk source rows → transformations → issues → decisions → export membership.

### Model connectors (top bar)

- Model chip opens settings (provider, model, hosted API keys).
- Local = amber/yellow chip with status; hosted = red warning state (prompts leave this machine).
- Overrides persist in `data/llm_settings.json` (gitignored); **Reset to .env** restores file-based defaults.

---

## Pipeline (backend)

Deterministic stages behind a FastAPI service and SQLite repository:

| Stage | Responsibility |
| --- | --- |
| **Ingest** | Parse CSV, assign source row numbers, store raw rows. |
| **Profile / map** | Propose column mappings with confidence. |
| **Split** | Denormalised rows → Company, Worker, Certification entities with stable IDs. |
| **Normalise** | Names, dates, phones, emails, enums, ABN checksum, etc. |
| **Validate** | Errors and warnings with field-level evidence and import consequence. |
| **Dedupe** | Exact collapse with lineage; fuzzy candidates with scored evidence. |
| **Export** | Eligibility + parent-child blocking; write artifact pack. |

Persistence: five-table SQLite schema (`import_runs`, `source_rows`, `entities`, `issues`, `decisions`) behind a `Repository` protocol so Postgres can be added later without rewriting pipeline stages.

---

## AI usage (advisory)

| Call | Purpose | Guardrail |
| --- | --- | --- |
| Implementation summary | Customer-facing note from structured counts/decisions | Must not invent numbers absent from input |
| Exception narrative | Readable grouping of deterministic issues | Counts still from pipeline |
| Fuzzy explanation | Strength + supporting/conflicting evidence + recommended check | Human still chooses merge / separate / defer |

Providers behind one `LLMAdapter`: **Ollama** (default, e.g. `llama3.1:latest`), **OpenAI**, **Anthropic**, **Gemini**, or **fallback** templates. Structured calls validate → retry once → deterministic fallback. Missing keys or stopped Ollama do not crash the run.

---

## Artifacts produced per export

Typical pack under `outputs/` for a run:

- Import-ready CSV per entity type (Company, Worker, Certification)
- Excluded CSV per entity type (with reasons)
- Markdown exception report
- JSON audit / approval-decision export
- Customer-facing implementation summary (Markdown)
- Metadata noting synthetic demo and (when applicable) LLM provider/model

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React + TypeScript + Vite |
| Backend | Python 3.12+ / FastAPI / Pydantic v2 |
| Persistence | SQLite via `Repository` |
| AI | Ollama by default; optional hosted adapters |
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
- MCP server and Postgres migration (optional post-demo extensions)

---

## Seeded demo path

1. Run named e.g. `Harbour demo`, reference date `2025-06-15`.
2. Upload `fixtures/messy_construction_records.csv`.
3. Confirm mappings (especially low-confidence / ignore decisions).
4. Review: override one error with a reason, reject one company, approve the rest, resolve fuzzy pairs.
5. Export and download the artifact pack.
6. In Audit, trace an exported field to its source row.
7. Optional: `POST /swms/extract` with `fixtures/SWMS_Roof_Sheeting_Working_at_Heights.pdf`.

Setup and run commands: [README.md](README.md).  
Build specification: [PRD_Construction_Data_Onboarding_Workbench_v2_lean.md](PRD_Construction_Data_Onboarding_Workbench_v2_lean.md).

---

## Success criteria (product)

The workbench succeeds when a reviewer can, without cloud credentials:

- Complete upload → map → review → export → audit on the synthetic fixture.
- Explain every exclusion from evidence and recorded decisions.
- See that AI never bypassed the human gate or invented source values.
- Re-run the same input and reference date and get the same IDs and issue set from deterministic stages.
