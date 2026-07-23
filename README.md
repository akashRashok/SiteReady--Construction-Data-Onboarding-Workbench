# Construction Data Onboarding Workbench

Independent demo. Synthetic data.

A lean portfolio demonstration that ingests a messy construction onboarding CSV, maps it into canonical Company, Worker, and Certification entities, detects data-quality issues deterministically, requires recorded human approval, exports import-ready and excluded files with full lineage, and drafts a customer-facing implementation summary.

This is independent work. It is not affiliated with, integrated into, or endorsed by any commercial product.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React + TypeScript + Vite (`fetch`, local state) |
| Backend | Python 3.12+ / FastAPI / Pydantic v2 |
| Persistence | SQLite behind a `Repository` protocol |
| AI (optional) | `LLMAdapter`: Ollama (default), OpenAI, Anthropic, Gemini, or deterministic fallback |

SQLite is intentional: a reviewer can clone and run with no cloud account, no hosted migrations, and no credentials. All SQL lives in `SqliteRepository`; pipeline and API code talk only to the repository interface, so a `PostgresRepository` can be added later without touching pipeline stages.

## Quick start

### Prerequisites

- Python 3.12+ (3.13 works)
- Node.js 18+
- Optional: [Ollama](https://ollama.com) for local AI drafting

### One-time setup

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cd ..
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

# Frontend
cd frontend
npm install
cd ..
```

### Run the stack

Terminal 1 — API:

```bash
cd backend
# activate venv first
set PYTHONPATH=.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — UI:

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173

### Optional: Ollama

```bash
ollama pull llama3.1:latest
ollama serve
```

The demo runs end to end with Ollama stopped. Summaries then use deterministic templates and the UI still shows the configured provider/model.

### Change model from the UI

Click **Settings** (or the Model chip) in the top bar → **Model connectors**.

- Switch provider: `ollama` / `openai` / `anthropic` / `gemini` / `fallback`
- Pick or type a model id
- Enter API keys for hosted providers (stored locally in `data/llm_settings.json`, gitignored)
- Hosted providers show a red warning that prompts leave this machine
- **Reset to .env** clears UI overrides

You can still set defaults in `.env`; the UI overrides them without editing files.

### Optional: hosted providers via `.env` (explicit opt-in)

Default is local Ollama. Setting a hosted provider sends prompts off-machine. The header shows a red warning when this is active.

```bash
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-latest
ANTHROPIC_API_KEY=sk-ant-...

# Gemini
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
GEMINI_API_KEY=...
```

Missing or invalid API keys fall back to deterministic templates without crashing the pipeline. See [AI_BOUNDARIES.md](AI_BOUNDARIES.md).

## Seeded demonstration

1. Create a run named e.g. `Harbour demo` with reference date `2025-06-15` (keeps expiry warnings reproducible).
2. Upload `fixtures/messy_construction_records.csv`.
3. Confirm column mappings (low-confidence rows must be confirmed).
4. Review entities: exact duplicates, fuzzy candidates, raw vs normalised values, errors/warnings.
5. Override one error with a reason, reject one company, approve the rest, resolve fuzzy pairs.
6. Export and download import-ready / excluded CSVs, exception report, audit log, and implementation summary.
7. Use Audit to trace an exported field back to its source row.
8. Optional: `POST /swms/extract` with `fixtures/SWMS_Roof_Sheeting_Working_at_Heights.pdf`.

CSV files always begin with schema headers on row one. Disclaimers appear only in the UI, Markdown, and JSON metadata — never above a CSV header.

## Tests

```bash
cd backend
set PYTHONPATH=.
pytest
```

```bash
cd frontend
npm run typecheck
npm run build
```

## Delete a run

From the Upload screen, or:

```http
DELETE /runs/{id}
```

Removes database rows and local upload/output artifacts for that run.

## Privacy (precise)

Default `LLM_PROVIDER=ollama` keeps prompts on the local machine. This is not a production security or compliance claim. See [AI_BOUNDARIES.md](AI_BOUNDARIES.md).

## Project layout

```
backend/app/          FastAPI app, pipeline, repository, LLM, SWMS
backend/schema.sql    Five-table SQLite DDL + schema version
backend/tests/        Unit, integration, and fixture e2e tests
frontend/src/         Five-screen Vite React UI
fixtures/             Synthetic CSV + SWMS PDF
outputs/              Generated artifacts per run
data/                 SQLite DB and uploads
```

## Out of scope

Authentication, multi-tenancy, cloud storage, hosted providers by default, MCP, Postgres migration, OCR, and real customer data. Those are optional post-recording extensions only.
