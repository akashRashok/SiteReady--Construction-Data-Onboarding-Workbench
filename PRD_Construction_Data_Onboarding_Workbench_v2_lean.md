# PRD: Construction Data Onboarding Workbench (Lean Build)

**Owner:** Akash Renuka Ashok
**Status:** Build specification for Codex, Cursor, or Claude Code
**Type:** Standalone portfolio demonstration
**Affiliation:** Independent work. Not affiliated with, integrated into, or endorsed by any commercial product.
**Version note:** This is the lean build. It keeps the full data-quality, traceability, and AI-boundary rigour of the expanded specification, and deliberately cuts hosted infrastructure so the project is completable and recordable in roughly one focused week. Section numbering is aligned with the expanded PRD so the two can be diffed.

**Primary goal:** A working end-to-end demonstration that ingests a messy construction onboarding CSV, maps it into canonical Company, Worker, and Certification entities, detects data-quality issues deterministically, requires explicit recorded human approval, persists the full run with complete lineage, generates import-ready and excluded files, and drafts a customer-facing implementation summary.

**Secondary goal:** Extract structured data from one supplied machine-readable Safe Work Method Statement (SWMS) PDF.

---

## 0. Non-negotiable build rules

1. **Working beats broad.** Complete the core onboarding loop before beginning the SWMS flow, hosted-model adapters, or the MCP wrapper. Do not mock, stub, or fake any step in the core loop.
2. **Synthetic data only.** All fixtures and demo records are synthetic. Display `Independent demo. Synthetic data.` in the interface, the README, Markdown reports, and JSON metadata.
3. **Do not corrupt machine-readable exports.** CSV files must begin with their actual column headers on row one. Never insert disclaimer text above a CSV header row. Disclaimers belong in JSON metadata fields, Markdown documents, and the UI only.
4. **Deterministic first, AI second.** Validation, normalisation, schema mapping, exact duplicate detection, fuzzy candidate scoring, ID generation, referential-integrity checks, all counts, and every export decision must be implemented in deterministic code.
5. **AI is advisory and non-authoritative.** The LLM may draft customer-facing language and describe why a deterministic fuzzy-match candidate was surfaced. It must never invent a source value, decide two people are the same, approve a record, merge records, or calculate a report total.
6. **Human approval is mandatory.** No entity enters an import-ready export without an explicit recorded approval decision. Error overrides require a human-entered reason.
7. **Everything is traceable.** Preserve source row numbers, raw values, transformations, issues, duplicate relationships, approval decisions, exports, and model provider details.
8. **SQLite is the system of record, behind a repository interface.** All persistence goes through a single repository layer so the storage engine can be swapped to Postgres without touching pipeline code. See section 6.
9. **Privacy claims must be accurate.** Local Ollama prevents prompts being sent to a hosted LLM provider by default. This demo does not claim production-grade security, compliance, tenant isolation, or data governance. Do not overclaim in the UI, README, or generated summaries.
10. **No real company branding or private APIs.** No real construction software names, logos, private schemas, or proprietary endpoints anywhere in code, data, interface, or output.
11. **Stop at phase boundaries.** At the end of each phase, run the tests and stop for human review before starting the next phase. Do not chain phases autonomously.

---

## 1. Product summary

Construction businesses onboard onto new systems by importing years of operational history from spreadsheets. Worker records, subcontractor details, certification data, and contact information are typically inconsistent, duplicated, incomplete, and formatted differently from the target system. Cleaning this by hand is slow, error prone, and consumes hours of implementation time per account.

The Construction Data Onboarding Workbench lets an implementation or solutions engineer:

1. Upload a messy onboarding CSV.
2. Review and confirm proposed source-column mappings.
3. Split the denormalised source into canonical Company, Worker, and Certification entities.
4. Normalise values deterministically.
5. Detect validation errors, warnings, exact duplicates, and fuzzy duplicate candidates.
6. Review the supporting evidence behind every issue.
7. Approve, reject, override, or resolve duplicates through a visible human gate.
8. Export clean, approved entity files plus excluded records with reasons.
9. Produce an audit trail, exception report, and customer-facing implementation note.

It should look and behave like a small internal customer-delivery tool, not a generic AI chatbot.

---

## 2. Target users

### 2.1 Primary user
An implementation, solutions, or forward-deployed engineer onboarding a construction customer and converting a messy historical export into a safe import package.

### 2.2 Secondary user
A customer success manager who needs a clear account of what was received, what was cleaned, what was imported, what was excluded, what still needs clarification, and what decisions were made.

---

## 3. Core user story

> As an implementation engineer, I want to upload a messy customer onboarding spreadsheet, understand every detected issue, approve or reject proposed records, and export clean entity files with a complete audit trail, so that I can complete the migration safely and explain the outcome to the customer.

---

## 4. Scope

### 4.1 In scope (the build target)
- One denormalised CSV upload representing worker-certification rows
- Source-column profiling and mapping confirmation
- Splitting into canonical Company, Worker, and Certification entities
- Deterministic normalisation and validation
- Exact duplicate collapsing with full lineage
- Deterministic fuzzy duplicate candidate scoring with evidence
- Visible issue and evidence review
- Explicit approval, rejection, error override, and duplicate resolution
- SQLite persistence of the full run lifecycle behind a repository interface
- Import-ready CSV per entity type
- Excluded-record CSV per entity type, each with reasons
- JSON audit log and approval-decision export
- Deterministic Markdown exception report
- Ollama-generated customer-facing implementation summary with deterministic fallback
- Unit and integration tests for deterministic logic
- Synthetic sample data covering all required edge cases
- A Loom-friendly UI and seeded demonstration flow

### 4.2 Secondary scope
- One supplied machine-readable SWMS PDF
- Deterministic labelled-field and table extraction using `pdfplumber`
- Source evidence retained for every extracted field
- Optional LLM classification of free-text categories
- `swms_extract.json` output

### 4.3 Optional, only after everything above works and is recorded
- One hosted-model adapter (OpenAI preferred) behind the same interface
- Additional Anthropic or Gemini adapters
- A read-only MCP server exposing pipeline tools
- Migration of the repository layer from SQLite to Postgres or Supabase

### 4.4 Out of scope
- Real customer data
- Authentication, multi-tenancy, multi-user accounts
- Cloud-hosted storage, signed URLs, object stores
- Direct integration with commercial construction software
- Production-grade access control, compliance, encryption, retention, backup
- Automatic imports into external systems
- Automatic duplicate merges or autonomous approvals
- OCR for scanned or handwritten PDFs
- Arbitrary spreadsheet formats, Excel output
- Production-scale batch processing

**Cut from the expanded specification, deliberately:** hosted Supabase, Supabase Storage and signed URLs, the service-role key boundary, the 14-table schema, TanStack Query, per-phase report documents, and the nine-document documentation set. None of these change what a viewer sees in the demonstration. They are listed in 4.3 as post-recording extensions.

---

## 5. Technical architecture

Do not substitute the stack unless a library is unavailable or blocks the core flow.

### 5.1 Frontend
- React with TypeScript, built with Vite
- Plain `fetch` for API calls with simple local state. No server-state library.
- Minimal styling. Visual clarity on a screen recording takes priority over design-system work.

### 5.2 Backend
- Python 3.12+
- FastAPI
- Pydantic v2
- pandas
- python-dateutil
- `phonenumbers`
- rapidfuzz
- pdfplumber
- pytest

### 5.3 Data and storage
- SQLite, accessed only through a repository interface (section 6)
- Generated artifacts written to a local `outputs/` directory
- Source uploads retained on local disk alongside the run record

### 5.4 AI runtime
- Ollama as the default and primary provider
- Model configurable through `LLM_MODEL`, recommended default `qwen2.5:7b` or another small instruct model verified to produce the required structured output
- Single adapter interface
- JSON/format mode, then schema validation, then one retry with the validation error fed back, then deterministic fallback
- Deterministic fallback on any failure or provider unavailability

### 5.5 Application boundary
The frontend calls FastAPI only and never touches the database directly. The backend owns all persistence, pipeline execution, export generation, LLM calls, and approval validation.

---

## 6. Persistence and the repository interface

SQLite is used so a reviewer can clone the repository and run the demonstration with a single command, with no cloud account, no migrations against a hosted service, and no credentials. That is a deliberate product decision about respecting a reviewer's setup time, and it should be stated in the README.

All database access goes through one `Repository` protocol. No SQL appears in pipeline, API, or export code. Implement `SqliteRepository` now. Because the interface is the only coupling point, a `PostgresRepository` can be added later without touching anything else, and this claim must be demonstrably true, not aspirational: keep the protocol narrow and free of SQLite-specific types.

Schema is created at startup from committed DDL in `schema.sql`. Store the schema version and refuse to run against a mismatched database.

---

## 7. Source data contract

Input is a single denormalised CSV where each row represents one worker-certification pairing, carrying company details redundantly. Column headers are inconsistent with the canonical schema by design. The bundled fixture is `messy_construction_records.csv`.

Parsing rules:
- Record the source row number for every row, starting at 2 to match spreadsheet line numbers including the header.
- Preserve the complete raw row as JSON before any transformation.
- Never discard a raw value. Normalisation produces a new field, it does not overwrite the record of what arrived.
- Rows with a column count mismatch are recorded as structural errors and surfaced, not silently dropped.

---

## 8. Canonical target schemas

### 8.1 Company
| Field | Type | Rules |
| --- | --- | --- |
| id | string | Stable, generated. See section 9. |
| company_name | string | Trimmed, whitespace collapsed. |
| canonical_name | string | Lowercased, legal suffixes stripped, punctuation removed. Used for matching only. |
| abn | string or null | 11 digits passing the ABN checksum, else null with the raw value preserved. |
| role | enum | `head_contractor` or `subcontractor`. |
| review_status | enum | See section 13. |
| source_rows | int array | Every source row contributing to this entity. |

### 8.2 Worker
| Field | Type | Rules |
| --- | --- | --- |
| id | string | Stable, generated. |
| full_name | string | Trimmed, whitespace collapsed, title cased. |
| trade | enum | `carpenter`, `electrician`, `plumber`, `concreter`, `steelfixer`, `crane_operator`, `scaffolder`, `labourer`, `site_supervisor`, `traffic_controller`, `other`. |
| email | string or null | Valid email, else null with raw preserved. |
| phone | string or null | E.164 via `phonenumbers`, else null with raw preserved. |
| company_id | string | Foreign key to Company. Unmatched is an error. |
| review_status | enum | See section 13. |
| source_rows | int array | |

### 8.3 Certification
| Field | Type | Rules |
| --- | --- | --- |
| id | string | Stable, generated. |
| worker_id | string | Foreign key to Worker. Unmatched is an error. |
| cert_type | enum | `white_card`, `hrwl`, `working_at_heights`, `first_aid`, `asbestos_awareness`, `traffic_management`, `ewp`, `other`. |
| cert_number | string | Required. Missing is an error. |
| issue_date | ISO date or null | |
| expiry_date | ISO date or null | |
| review_status | enum | See section 13. |
| source_rows | int array | |

---

## 9. Stable ID generation

IDs must be deterministic so that re-running the same input produces the same IDs. Derive each ID from a hash of its stable natural key:

- Company: `canonical_name` plus valid ABN when present
- Worker: normalised full name plus `company_id`, strengthened by email when present
- Certification: `worker_id` plus `cert_type` plus normalised `cert_number`

Record an `id_confidence` value (`high`, `medium`, `low`) reflecting how much identifying evidence was available. Re-run determinism is an acceptance criterion and must be covered by a test.

---

## 10. Column mapping

Profile each source column and propose a mapping to a target entity and field. For each proposal record the method (exact header match, alias dictionary, or heuristic on sample values), a confidence level, and three sample values.

Low-confidence mappings block processing until a human confirms them in the UI. This is a visible step in the demonstration, not a silent inference.

---

## 11. Deterministic data-quality rules

Every issue record carries: rule ID, severity, entity type, canonical record ID when available, source row number(s), field name, raw value, normalised value when applicable, a human-readable message, the import consequence, and a created timestamp.

### 11.1 Severity definitions
- **Error:** excluded from export unless explicitly overridden by a human with a reason.
- **Warning:** eligible for approval but visibly surfaced.
- **Info:** a safe deterministic transformation or a duplicate lineage event.

### 11.2 Required rules

**Required fields**
- Missing worker name: error
- Missing company name: error
- Missing company link: error
- Missing certification number: error

**Dates**

Support at least `YYYY-MM-DD`, `DD/MM/YYYY`, and `DD-MMM-YY`.
- Unparseable date: error
- Ambiguous date: error
- Issue date in the future: error
- Expiry before issue: error
- Expired certification: warning

All expiry logic uses an injected reference date, never the system clock directly. The reference date is stored on the run and shown in the UI, so demonstration counts are reproducible on any recording day.

**Email**
- Invalid email: warning, canonical value null, raw preserved in transformation log

**Phone**
- Use `phonenumbers`, accept plausible Australian mobile and landline numbers, normalise valid values to E.164
- Invalid phone: warning, canonical value null, raw preserved

**ABN**

Implement the checksum exactly:
1. Strip spaces and non-digit separators.
2. Require exactly 11 digits.
3. Subtract 1 from the first digit.
4. Multiply digits by weights `[10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]`.
5. Sum the products.
6. Valid when the sum is divisible by 89.

Invalid ABN: error, canonical value null, raw preserved.

**Enums**
- Apply deterministic alias dictionaries first, for example `sparky` to `electrician`, `chippy` to `carpenter`.
- Unknown trade or certification type: warning, canonical value `other`, original preserved in the transformation log.

**Referential integrity**
- Worker referencing no canonical company: error
- Certification referencing no canonical worker: error
- A child entity cannot be exported when its parent is rejected or excluded

---

## 12. Duplicate handling

### 12.1 Exact duplicates
Detected after normalisation. Never silently dropped. Collapse into one canonical record retaining the canonical source row, all duplicate source rows, the duplicate count, the normalised comparison key, and an audit event. Shown during approval and may be approved in bulk.

### 12.2 Fuzzy candidates
Generated deterministically with RapidFuzz and blocking rules.

Worker evidence may include name similarity, same company, matching email, matching phone, matching certification number, and conflicting fields. Company evidence may include canonical-name similarity, legal-suffix differences, matching ABN, and conflicting ABNs.

### 12.3 LLM boundary
The LLM must not return an identity verdict. It may return only:

```json
{
  "match_strength": "strong | moderate | weak",
  "supporting_evidence": ["..."],
  "conflicting_evidence": ["..."],
  "recommended_human_check": "..."
}
```

The human chooses `merge`, `keep_separate`, or `defer`. No fuzzy candidate is ever auto-merged.

---

## 13. Approval model

### 13.1 Record states
`pending_review`, `approved`, `approved_with_override`, `rejected`, `excluded_by_rule`.

### 13.2 Rules
- An entity with an unresolved error cannot reach `approved`. It reaches `approved_with_override` only with a human-entered reason recorded against the decision.
- Every decision is persisted with the entity ID, the resulting state, the reason when applicable, and a timestamp.
- Export refuses to run while any entity remains `pending_review`, and says which ones.
- A rejected or excluded parent blocks export of its dependent children, and the blocked children are listed in the excluded output with that reason.

---

## 14. Pipeline stages

Each stage is pure and independently testable, taking the working dataset plus the issue log and returning both updated.

1. **Ingest.** Parse CSV, record source row numbers, persist raw rows.
2. **Profile.** Propose column mappings with method, confidence, and samples.
3. **Confirm mappings.** Human gate on low-confidence proposals.
4. **Split.** Derive canonical Company, Worker, and Certification entities with stable IDs.
5. **Normalise.** Trim, case, collapse whitespace, parse dates to ISO, normalise phones and emails, apply enum aliases. Log every transformation with its raw input.
6. **Validate.** Run all section 11 rules.
7. **Deduplicate.** Exact collapse, then fuzzy candidate scoring with evidence.
8. **Report.** Generate the deterministic exception report.
9. **Review and approve.** The human gate. Nothing proceeds without recorded decisions.
10. **Export.** Import-ready and excluded CSVs per entity type.
11. **Summarise.** LLM drafts the implementation summary from the structured result only.

---

## 15. Data model (SQLite)

Five tables. Committed DDL in `schema.sql`.

**`import_runs`**: `id`, `name`, `status`, `source_filename`, `source_path`, `is_synthetic`, `reference_date`, `llm_provider`, `llm_model`, `created_at`, `updated_at`.
Run states: `created`, `ingested`, `mapping_pending`, `processing`, `review_pending`, `approved`, `exported`, `failed`.

**`source_rows`**: `id`, `run_id`, `source_row_number`, `raw_data` (JSON), `created_at`. Unique on `(run_id, source_row_number)`.

**`entities`**: `id`, `run_id`, `entity_type` (`company` / `worker` / `certification`), `data` (JSON, the canonical fields for that type), `parent_id` (nullable), `id_confidence`, `review_status`, `source_rows` (JSON array), `created_at`, `updated_at`. Unique on `(run_id, id)`.

A single polymorphic entity table is used deliberately instead of three typed tables. It keeps the schema small while preserving every field, and the Pydantic models in section 8 provide type safety at the application layer where it matters.

**`issues`**: `id`, `run_id`, `rule_id`, `severity`, `entity_type`, `entity_id` (nullable), `source_rows` (JSON), `field`, `raw_value`, `normalised_value`, `message`, `import_consequence`, `created_at`.

**`decisions`**: `id`, `run_id`, `entity_id`, `decision` (`approve` / `reject` / `override` / `merge` / `keep_separate` / `defer`), `reason` (nullable, required for `override`), `related_entity_id` (nullable, for duplicate resolution), `created_at`.

Transformations are recorded as `info` severity rows in `issues` with the raw and normalised values, rather than in a separate table.

---

## 16. Artifact storage

Generated files are written to `outputs/<run_id>/` on local disk. The run record stores relative paths. The API serves them through a download endpoint. No object store, no signed URLs.

---

## 17. AI usage

### 17.1 Where the LLM is called
Exactly three places. Everywhere else is deterministic.

1. **Implementation summary drafting.** Input is the final structured result: counts by category, excluded totals by reason, notable decisions. Output is a short plain-English note a CSM could send to a client. The model must not state a number that is not in its structured input.
2. **Exception summary narrative.** Input is the structured issue report. Output is a readable grouping of what was found. Counts come from the deterministic report, not the model.
3. **Fuzzy candidate evidence explanation.** Bounded by the schema in section 12.3. The model sees only the two candidate records and their computed similarity evidence, never the full dataset.

### 17.2 Provider strategy
Ollama running locally is the default. The demonstration must run end to end with no API key set and no outbound network call. This matters because customer operational data (names, contact details, licence numbers) is exactly what a client will not want leaving their environment during a migration. Surface the active provider in the UI so it is visible on the recording.

Single `LLMAdapter` protocol, selected by `LLM_PROVIDER`, defaulting to `ollama`. Adding a provider must not require touching pipeline code.

### 17.3 Reliability
Small local models are unreliable at schema adherence. Never assume valid JSON. Use JSON/format mode, validate against the schema, retry once with the validation error fed back, then fall back to a deterministic template. The pipeline must never crash or emit unvalidated model output. If Ollama is unavailable, the run completes with template summaries and a clear notice that AI drafting was skipped.

### 17.4 Honest claims
Record the provider and model on the run and in the footer of every generated artifact. Where the UI or README mentions local processing, state precisely that prompts are not sent to a hosted provider by default, and that this is not a production security or compliance claim.

---

## 18. Outputs

Written to `outputs/<run_id>/`:

1. `companies_import_ready.csv`, `workers_import_ready.csv`, `certifications_import_ready.csv`
2. `companies_excluded.csv`, `workers_excluded.csv`, `certifications_excluded.csv`, each row carrying at least one reason
3. `exception_report.json` and `exception_report.md`
4. `audit_log.json` containing the run, decisions, and transformation lineage
5. `implementation_summary.md`
6. `swms_extract.json` from the secondary flow

CSVs begin with their schema headers on row one. Disclaimers appear only in Markdown and JSON metadata.

---

## 19. Interface requirements

Five screens, optimised for legibility on a screen recording:

1. **Upload**: file input, reference date, run name, and the synthetic-data notice.
2. **Mapping**: proposed mappings with method, confidence, and sample values. Low-confidence rows require confirmation before continuing.
3. **Review**: the centre of the demonstration. Entities grouped by type and status, issues shown inline with severity, raw value beside normalised value, exact duplicate groups, and fuzzy candidates with their evidence. Actions: approve, reject, override with a reason, resolve duplicate.
4. **Export**: blocked while anything is pending, with the blocking list shown. On success, links to all generated files.
5. **Audit**: pick any exported field and trace it back through transformations to its original source row.

Active LLM provider and model are shown persistently in the header.

---

## 20. SWMS secondary flow

Takes one supplied machine-readable SWMS PDF and extracts, using `pdfplumber`:

`swms_number`, `document_title`, `contractor_name`, `contractor_abn` (validated with the same checksum), `project_name`, `site_address`, `activity`, `high_risk_categories[]`, `date_prepared`, `review_date`, `responsible_person`, `ppe_required[]`, `plant_and_equipment[]`, `required_competencies_licences[]`, and `job_steps[]` as `{ step, hazard, risk_rating, control_measures }`.

Labelled fields and the job-steps table are extracted deterministically. The LLM may only classify or normalise free text, and the source text is always retained alongside any model-derived value. Output `swms_extract.json`. Fixture: `SWMS_Roof_Sheeting_Working_at_Heights.pdf`.

---

## 21. API surface

`POST /runs` create, `POST /runs/{id}/upload`, `GET /runs/{id}/mappings`, `POST /runs/{id}/mappings/confirm`, `POST /runs/{id}/process`, `GET /runs/{id}/entities`, `GET /runs/{id}/issues`, `POST /runs/{id}/decisions`, `POST /runs/{id}/export`, `GET /runs/{id}/artifacts/{name}`, `GET /runs/{id}/audit/{entity_id}`, `POST /swms/extract`, `DELETE /runs/{id}`.

---

## 22. Build phases

**Phase 0: Foundation.** Repository interface, SQLite schema, FastAPI skeleton, React shell, test harness.
*Exit:* a run can be created and retrieved, tests run.

**Phase 1: Deterministic core (the must-work phase).** Ingest, profile, mapping confirmation, entity split with stable IDs, normalisation, all section 11 validation, exact dedupe, fuzzy candidate scoring, exception report, review UI, approval gate, exports. No LLM at all.
*Exit:* the bundled fixture produces the expected issue counts and a full approve-to-export cycle completes. **This alone is a recordable demonstration.**

**Phase 2: AI layer.** LLM adapter with Ollama, schema validation, retry, deterministic fallback, implementation summary, exception narrative, provider logging.
*Exit:* the pipeline succeeds with Ollama running and with Ollama stopped.

**Phase 3: SWMS.** Extraction, evidence retention, ABN validation, `swms_extract.json`.
*Exit:* all required fields populated with source evidence.

**Phase 4: Optional, only after recording.** Hosted adapter, MCP tools, Postgres repository.

At each phase boundary: run the tests, report what passed and what is incomplete, and stop for human review. Do not begin a phase while any part of the previous one is stubbed.

---

## 23. Testing requirements

**Unit:** ABN checksum with known valid and invalid cases; date parsing across all supported formats; ambiguous and impossible dates; reference-date-driven expiry; email validation; Australian phone normalisation; enum aliases and unknown values; stable ID generation and re-run determinism; exact duplicate collapse; fuzzy blocking and scoring; parent-child export dependency; override reason enforcement; LLM response validation and deterministic fallback.

**Integration:** source CSV through to persisted records; mapping confirmation gating processing; decisions through to export; rejected company blocking dependent workers and certifications; rejected worker blocking dependent certifications; export refusing while review is incomplete; run deletion removing records and artifacts.

**End-to-end fixture:** the bundled CSV must produce expected non-zero counts for every required issue category, asserted as exact counts where practical so the demonstration is reproducible.

---

## 24. Acceptance criteria

1. One denormalised synthetic CSV uploads and persists.
2. Mappings are proposed with method, confidence, and sample values.
3. Low-confidence mappings cannot proceed without confirmation.
4. Input splits into canonical Company, Worker, and Certification entities.
5. Re-running the same input produces identical stable IDs.
6. Every transformed field retains its raw value and source-row lineage.
7. The fixture's invalid ABN, malformed date, impossible date, expired certification, invalid email, malformed phone, unmatched link, exact duplicate, fuzzy candidate, and unmapped enum cases are all detected correctly.
8. Missing certification number is treated as an error.
9. Invalid phone and email are null in canonical records and retained in audit data.
10. Exact duplicates retain all duplicate source-row references.
11. Fuzzy duplicates are never merged without an explicit human decision.
12. Every error override carries a human-entered reason.
13. No entity appears in an import-ready CSV without a persisted approval decision.
14. A rejected parent blocks dependent child exports, and those children appear in the excluded output with that reason.
15. Every excluded record has at least one stated reason.
16. All CSV files begin with valid schema headers on row one.
17. Import-ready and excluded files are generated for all three entity types.
18. The database contains the full run, rows, entities, issues, and decisions.
19. Artifacts are written to disk and downloadable through the API.
20. The implementation summary contains only deterministic counts, with no invented figures.
21. The pipeline runs end to end with local Ollama and no hosted API key.
22. With Ollama stopped, the pipeline completes using deterministic fallback text.
23. All pipeline and export logic is free of direct SQL, going through the repository interface only.
24. The SWMS flow returns populated structured fields with evidence for every extracted value.
25. All unit, integration, and end-to-end tests pass.

---

## 25. Required documentation

Two documents only, plus configuration.

**`README.md`** must state: that this is an independent demonstration using synthetic data; how to install and run backend, frontend, and tests; how to start Ollama and the exact `ollama pull` command; how to run the seeded demonstration; the SQLite-for-portability decision and how the repository interface allows Postgres later; the precise limits of the local-model privacy claim; and how to delete a run.

**`AI_BOUNDARIES.md`** must state: where the LLM is and is not used and why; what deterministic-first buys in a customer data migration; how schema validation, retry, and fallback handle unreliable local model output; and what this design does not claim. Write this one carefully, it doubles as a writing sample.

Plus `.env.example`, `schema.sql`, and the bundled synthetic fixtures.

---

## 26. Loom demonstration story

1. State the customer onboarding problem in one sentence.
2. Show the messy synthetic CSV, pointing at a genuinely broken row.
3. Upload and confirm the proposed mappings.
4. Show deterministic transformations and detected issues.
5. Explain why validation is deterministic and the model is advisory.
6. Review one exact duplicate and one fuzzy candidate with its evidence.
7. Override one error with a reason, reject another record.
8. Approve the clean records.
9. Show a rejected parent blocking its child.
10. Export and open the import-ready and excluded files.
11. Show the customer-facing implementation summary.
12. Trace one exported value back to its source row in the audit view.
13. Note that Ollama runs locally by default and show graceful fallback if practical.
14. Optionally show the SWMS extraction.

Target three to four minutes. Beats 5, 7, 9, and 12 are the ones that carry the most signal, so do not rush them.

---

## 27. Explicit non-goals and guardrails

- The LLM never fabricates a field value.
- The LLM never approves, rejects, merges, or exports a record.
- The LLM never determines that two people are the same.
- Counts and validation outcomes are never model-generated.
- No export bypasses a persisted human approval.
- No child exports when its required parent is rejected.
- No real company branding, product name, private API, customer data, or customer document appears anywhere.
- Source data is not sent to any hosted model by default. Using a hosted provider is an explicit configuration change with a visible warning.
- CSV files remain valid machine-readable files.
- Scanned PDFs and OCR are out of scope.
- MCP and hosted adapters are optional and must not delay the working core demonstration.

---

## 28. Definition of done

A reviewer can clone the repository and, following the README:

1. Start the stack with one documented command, needing no cloud account or credentials.
2. Upload the bundled synthetic CSV.
3. Confirm mappings.
4. Observe deterministic validation and duplicate evidence.
5. Make real approval decisions, including an override with a reason.
6. Export valid, approved entity files.
7. Inspect excluded records and their reasons.
8. Read a clear customer-facing summary.
9. Trace any exported field back to its original source row and transformation history.
10. Run the full automated test suite successfully.
11. Understand the system, trade-offs, limitations, and AI boundaries from the two documents and the recorded demonstration.
