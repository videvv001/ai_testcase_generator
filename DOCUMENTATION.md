# AI Test Case Generator — Production Documentation

## 1. Project Overview

### Purpose

AI Test Case Generator is an internal backend service that produces structured test cases from feature descriptions and requirements using LLMs (Ollama, OpenAI, Gemini, or Groq). It supports single-feature and batch generation, with scenario-driven coverage, deduplication, CSV export, and **Excel template export** (merge test cases into an uploaded .xlsx template).

### Problems It Solves

- **Manual effort**: Reduces time spent writing test cases from requirements.
- **Coverage gaps**: Uses coverage dimensions (core, validation, negative, boundary, state, security, destructive) to guide scenarios.
- **Duplication**: Applies embedding-based and title-based deduplication to avoid redundant test cases.
- **Inconsistency**: Produces standardized, structured test cases with scenario, description, preconditions, steps, and expected results.
- **Export flexibility**: Supports CSV (per-feature and merged) and Excel template export: upload an .xlsx template; test cases are merged into the “Test Cases” sheet (single feature or all features combined) with formatting preserved.

### Target Users

- QA engineers generating test cases from specs
- Developers performing exploratory test design
- Teams wanting local (Ollama) or cloud (OpenAI, Gemini, Groq) LLM-based generation

---

## 2. Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React + Vite)                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │GenerationForm│  │BatchResultsView │  │ResultsTable, TemplateUploadModal  │ │
│  └──────┬──────┘  └────────┬────────┘  │(Export CSV / Export to Excel)      │ │
│         │                  │                                                  │
│         └──────────────────┼──────────────────────────────────────────────────┤
│                            │  API Client (fetch)                               │
└────────────────────────────┼──────────────────────────────────────────────────┘
                             │  HTTP/REST
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Backend (FastAPI)                                    │
│  ┌─────────────┐     ┌──────────────────┐     ┌───────────────────────────┐  │
│  │api/testcases│────▶│TestCaseService   │────▶│Providers (Ollama/OpenAI/  │  │
│  │api/health   │     │(in-memory store) │     │ Gemini/Groq)              │  │
│  └─────────────┘     └────────┬─────────┘     └───────────────────────────┘  │
│                               │                                               │
│                               ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ utils: prompt_builder, embeddings, token_allocation, csv_filename,       │ │
│  │        excel_exporter, excel_template_merge (export-to-excel)           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  External Services                                                           │
│  - Ollama (localhost:11434) — local LLM                                      │
│  - OpenAI API — chat completions + embeddings (text-embedding-3-small/large) │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Relationships

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| **API** | `app.api.testcases` | HTTP handlers, request validation, delegates to service |
| **API** | `app.api.health` | Liveness/readiness probe |
| **Service** | `TestCaseService` (`app.services`) | Business logic: generation, batch orchestration, storage, dedup |
| **Providers** | `OllamaProvider`, `OpenAIProvider`, `GeminiProvider`, `GroqProvider` (`app.providers`) | LLM calls; implement `LLMProvider` interface |
| **Utils** | `prompt_builder` | Two-pass prompts (scenario extraction, test expansion) |
| **Utils** | `embeddings` | Semantic dedup via OpenAI embeddings |
| **Utils** | `token_allocation` | Dynamic `max_tokens` for OpenAI |
| **Utils** | `csv_filename` | OS-safe filename generation for exports |
| **Utils** | `excel_exporter` | Excel file generation (openpyxl) |
| **Utils** | `excel_template_merge` | Merge test cases into uploaded .xlsx template (single or all features); preserve Summary sheet and “Test Cases” structure (rows 1–2 headers, row 3+ data, columns A–L) |

### Data Flow

**Single feature (generate-test-cases)**  
1. `GenerateTestCasesRequest` → `TestCaseService.generate_ai_test_cases()`  
2. For each coverage layer: `_extract_scenarios()` (Pass 1) → `deduplicate_scenarios()` → `_expand_scenarios_to_tests()` (Pass 2)  
3. Accumulate, then `_deduplicate_by_embeddings()` and `_remove_near_duplicate_titles()`  
4. Persist in `_store`, return `TestCaseListResponse`

**Batch**  
1. `POST /batch-generate` → `start_batch()` creates `_BatchState`, spawns `asyncio.gather()` per feature  
2. Each feature runs `_run_one_feature()` → `generate_ai_test_cases()` → updates `fr.items`  
3. Frontend polls `GET /batches/{batch_id}` (e.g. 1.5s interval) until `completed` or `partial`  
4. Per-feature export: frontend calls `getCsvFilename()`, then `exportToCsv(items)`; or **Export to Excel Template**: upload .xlsx → `POST /export-to-excel` (template, testCases, featureName) → merged Excel download.  
5. Export All: `GET /batches/{batch_id}/export-all` → merged CSV; or **Export All to Excel Template**: upload .xlsx → `POST /export-all-to-excel` (template, testCasesByFeature) → one Excel with all features’ test cases combined in the “Test Cases” sheet.

**Delete**  
1. `DELETE /testcases/{id}` → `delete_test_case()` removes from `_store` and from all `fr.items`  
2. Frontend calls `deleteTestCase()` then `getBatchStatus()` to refresh UI

### External Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Ollama** | Local LLM inference | `AI_TC_GEN_OLLAMA_BASE_URL`, `AI_TC_GEN_OLLAMA_MODEL` |
| **OpenAI Chat** | Cloud LLM (gpt-4o-mini, gpt-4o) | `AI_TC_GEN_OPENAI_API_KEY`, `AI_TC_GEN_OPENAI_MODEL` |
| **OpenAI Embeddings** | Dedup (text-embedding-3-small, text-embedding-3-large) | Same API key as Chat |
| **Gemini API** | Cloud LLM (gemini-2.5-flash) | `AI_TC_GEN_GEMINI_API_KEY`, `AI_TC_GEN_GEMINI_MODEL` |
| **Groq API** | Cloud LLM (llama-3.3-70b-versatile) | `AI_TC_GEN_GROQ_API_KEY`, `AI_TC_GEN_GROQ_MODEL` |

---

## 3. Tech Stack

### Languages

- **Python 3.x** — Backend
- **TypeScript** — Frontend

### Frameworks

- **FastAPI** — Async HTTP API, OpenAPI, Pydantic validation
- **React 18** — UI
- **Vite 5** — Frontend build, HMR, proxy to backend

### Key Libraries

| Package | Purpose |
|---------|---------|
| `uvicorn` | ASGI server |
| `pydantic`, `pydantic-settings` | Schemas, config from env |
| `httpx` | Async HTTP (Ollama) |
| `openai` | OpenAI Chat + Embeddings API |
| `google-genai` | Gemini API (google-genai SDK) |
| `groq` | Groq API (llama-3.3-70b-versatile) |
| `tiktoken` | Token estimation for dynamic max_tokens |
| `openpyxl` | Excel export and template merge |
| `python-multipart` | Multipart form (file + form fields for export-to-excel) |
| `lucide-react` | Icons |
| `tailwindcss` | Styling |
| `class-variance-authority`, `clsx`, `tailwind-merge` | Component variants |

### Rationale

- **FastAPI**: Async, type-safe, built-in OpenAPI
- **Pydantic**: Strong validation for LLM JSON output and API contracts
- **Provider abstraction**: Swappable LLM backends (Ollama, OpenAI, Gemini, Groq)
- **Vite**: Fast dev, proxy to backend without CORS

---

## 4. Folder Structure

```
ai_testcase_generator/
├── backend/                # Python FastAPI app (run from here)
│   ├── app/                # Application package (uvicorn app.main:app)
│   │   ├── __init__.py
│   │   ├── main.py         # App factory, FastAPI app
│   │   ├── api/
│   │   │   ├── __init__.py  # Route registration (health, testcases)
│   │   │   ├── health.py    # GET /api/health
│   │   │   └── testcases.py # All test case endpoints
│   │   ├── core/
│   │   │   ├── config.py   # Settings (pydantic-settings), .env from project root
│   │   │   └── logging_config.py
│   │   ├── schemas/
│   │   │   └── testcase.py  # Pydantic request/response models
│   │   ├── services/
│   │   │   └── testcase_service.py # Business logic, batch orchestration
│   │   ├── providers/
│   │   │   ├── base.py      # LLMProvider interface
│   │   │   ├── factory.py   # get_provider(ollama|openai|gemini|groq)
│   │   │   ├── ollama_provider.py
│   │   │   ├── openai_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   └── groq_provider.py
│   │   └── utils/
│   │       ├── prompt_builder.py
│   │       ├── embeddings.py
│   │       ├── token_allocation.py
│   │       ├── csv_filename.py
│   │       ├── excel_exporter.py
│   │       └── excel_template_merge.py   # Merge test cases into .xlsx template
│   ├── tests/
│   │   └── test_health.py   # Health endpoint test
│   ├── main.py              # Optional entrypoint (python main.py from backend/)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/             # client.ts, types.ts
│   │   ├── assets/icons/    # Provider icons (google, groq, local, openai)
│   │   ├── components/      # GenerationForm, BatchResultsView, ResultsTable, TemplateUploadModal
│   │   ├── hooks/           # useTemplateStorage (Excel template in localStorage)
│   │   ├── constants/       # exportColumns
│   │   └── index.css        # Tailwind imports
│   ├── vite.config.ts       # Proxy /api → backend
│   └── package.json
├── venv/                    # Python virtual environment (create via python -m venv venv)
├── .env                     # Backend env vars (at root; backend loads via path)
├── package.json             # Root: npm run dev (concurrently: backend via venv + frontend)
└── DOCUMENTATION.md
```

### Responsibilities

| Directory | Responsibility |
|-----------|----------------|
| `backend/app/api/` | HTTP routing, error handling, thin handlers |
| `backend/app/core/` | App config, logging |
| `backend/app/schemas/` | Request/response models, validation |
| `backend/app/services/` | Generation, batch, storage, dedup |
| `backend/app/providers/` | LLM abstraction, provider implementations |
| `backend/app/utils/` | Prompts, embeddings, tokens, filenames, Excel |
| `frontend/` | React app, API client, UI components |

---

## 5. Setup Guide

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) Ollama for local generation
- (Optional) OpenAI API key for cloud generation + embeddings
- (Optional) Gemini API key for Gemini 2.5 Flash
- (Optional) Groq API key for Llama 3.3 70B (Groq)

### First-time setup (from project root)

Use a **virtual environment** for the backend so the project is portable (e.g. after moving or cloning). All commands below are from the project root.

**1. Python virtual environment and backend dependencies**

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

**2. Node dependencies**

```bash
npm install
npm install --prefix frontend
```

**3. Environment (optional)** — Copy `.env.example` to `.env` in the project root and set API keys (OpenAI, Gemini, Groq) as needed.

See **README.md** for the full first-time setup and run instructions.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_TC_GEN_DEFAULT_LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `gemini`, or `groq` |
| `AI_TC_GEN_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `AI_TC_GEN_OLLAMA_MODEL` | `llama3.2:3b` | Ollama model name |
| `AI_TC_GEN_OLLAMA_TIMEOUT_SECONDS` | `600` | Ollama read timeout |
| `AI_TC_GEN_OPENAI_API_KEY` | — | Required for OpenAI provider and embeddings |
| `AI_TC_GEN_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `AI_TC_GEN_OPENAI_TIMEOUT_SECONDS` | `120` | OpenAI timeout |
| `AI_TC_GEN_GEMINI_API_KEY` | — | Required for Gemini provider |
| `AI_TC_GEN_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model |
| `AI_TC_GEN_GROQ_API_KEY` | — | Required for Groq provider |
| `AI_TC_GEN_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `AI_TC_GEN_LOG_LEVEL` | `INFO` | Logging level |
| `VITE_API_BASE_URL` | (empty) | Override API base in production; empty uses proxy |

Use `.env` in the project root for backend variables (the backend loads it from the project root when run from `backend/`). Use `frontend/.env` for `VITE_*` variables.

### Running Locally

```bash
# Backend + frontend (recommended, from project root)
npm run dev
# Starts backend (using project venv on Windows) and frontend. No need to activate venv on Windows.
# On macOS/Linux: activate venv first (source venv/bin/activate), then npm run dev.
# Backend: http://localhost:8000  |  Frontend: http://localhost:5173

# Run backend only (with venv activated, from project root):
cd backend && uvicorn app.main:app --reload
# Without activating venv: cd backend && ..\venv\Scripts\python.exe -m uvicorn app.main:app --reload (Windows)
#                         cd backend && ../venv/bin/python -m uvicorn app.main:app --reload (macOS/Linux)
# API at http://localhost:8000. OpenAPI docs at http://localhost:8000/docs

# Run frontend only (ensure backend is running first):
cd frontend && npm run dev
```

Frontend proxies `/api` to `http://localhost:8000` via Vite.

---

## 6. Usage Guide

### Single-Feature Generation (API)

```bash
curl -X POST http://localhost:8000/api/testcases/generate-test-cases \
  -H "Content-Type: application/json" \
  -d '{
    "feature_name": "User Login",
    "feature_description": "Users authenticate via email and password.",
    "coverage_level": "medium",
    "provider": "openai"
  }'
```

### Batch Generation (UI)

1. Open `http://localhost:5173`.
2. Add one or more feature tabs (Name, Description, Allowed/Excluded, Coverage).
3. Choose model from the dropdown (default: **Gemini 2.5 Flash**). Options: Gemini 2.5 Flash, Llama 3.3 70B (Groq), Llama 3.2 3B (Local), GPT-4o Mini, GPT-4o.
4. Click **Generate Test Cases**.
5. Polling shows per-feature status; expand features to view results.
6. Export: **Export CSV** per feature; **Export All Features** for merged CSV; **Export to Excel Template** (per feature) or **Export All to Excel Template** (all features combined into one “Test Cases” sheet).

### Export Workflow

- **Per-feature CSV**: Uses backend-generated filename (`tc_{feature}_{timestamp}.csv`).
- **Export All (CSV)**: `GET /api/testcases/batches/{batch_id}/export-all` returns merged, deduplicated CSV.
- **Export to Excel Template (single feature)**: Click “Export to Excel Template” on a feature → upload .xlsx (or use stored template) → optional “Remember this template” → Export. Backend merges that feature’s test cases into the template’s “Test Cases” sheet; **Summary** sheet is unchanged.
- **Export All to Excel Template**: Click “Export All to Excel Template” (top right) → same template upload → Export. All features’ test cases are combined in order into the single “Test Cases” sheet (e.g. Feature1’s 5 cases, then Feature2’s 3 cases = 8 rows). Column A = sequential No. (1–8); Column B = Test ID per feature (e.g. `TC_FEAT1_001`, `TC_FEAT2_001`). The backend returns a timestamped filename including UTC date and time (e.g. `All_Features_Test_Cases_2026-02-11_1432.xlsx`); the frontend mirrors this pattern if the header is missing.

### Excel Template Structure

The template must contain a sheet named **“Test Cases”**. Expected layout:

- **Rows 1–2**: Headers (merged cells allowed). Not modified.
- **Row 3+**: Data rows. Existing data is cleared; new test cases are written from row 3.
- **Columns A–L**: No., Test ID, Test Scenario, Test Description, Pre-condition, Test Data, Step (enumerated), Expected Result, Actual Result, Status, Comment, (empty). Formatting from row 3 is applied to new rows.

If the template has a **Summary** sheet, it is left unchanged. Template file limit: 10 MB; `.xlsx` only.

### Delete Test Case

- Use the trash icon on a test case row in batch results.
- The test case is removed from the batch and excluded from all exports.

---

## 7. API Documentation

Base URL: `http://localhost:8000` (or configured host)

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness/readiness |

### Test Cases

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/testcases/from-requirements` | Generate from requirements (non-LLM) |
| POST | `/api/testcases/generate-test-cases` | Generate via LLM; optional `?generate_excel=true` |
| GET | `/api/testcases` | List all (in-memory) |
| GET | `/api/testcases/{id}` | Get by ID |
| DELETE | `/api/testcases/{id}` | Delete; removed from batch and exports |
| GET | `/api/testcases/csv-filename` | `?feature_name=` for OS-safe filename |
| POST | `/api/testcases/export-to-excel` | **Export to Excel template** (single feature). Multipart: `template` (.xlsx), `testCases` (JSON), `featureName`. Returns Excel with test cases in “Test Cases” sheet. |
| POST | `/api/testcases/export-all-to-excel` | **Export all to Excel template**. Multipart: `template` (.xlsx), `testCasesByFeature` (JSON array of `{ featureName, testCases }`). Returns Excel with all features’ test cases combined in “Test Cases” sheet. |

### Batch

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/testcases/batch-generate` | Start batch; returns `batch_id` |
| GET | `/api/testcases/batches/{batch_id}` | Batch status and per-feature results |
| POST | `/api/testcases/batches/{batch_id}/features/{feature_id}/retry` | Retry failed feature |
| GET | `/api/testcases/batches/{batch_id}/export-all` | Merged CSV download |

### Key Schemas

**GenerateTestCasesRequest**

- `feature_name`, `feature_description` (required)
- `coverage_level`: `low` \| `medium` \| `high` \| `comprehensive`
- `provider`: `ollama` \| `openai` \| `gemini` \| `groq` (optional; derived from `model_id` when set)
- `model_id`: `gpt-4o-mini` \| `gpt-4o` \| `gemini-2.5-flash` \| `llama-3.3-70b-versatile` \| `llama3.2:3b` (optional; when set, provider is derived from it)

**BatchGenerateRequest**

- `provider` (optional; derived from `model_id` when set)
- `model_id`: model identifier (optional; when set, provider is derived: gpt-4o-mini/gpt-4o→openai, gemini-2.5-flash→gemini, llama-3.3-70b-versatile→groq, llama3.2:3b→ollama)
- `features`: list of `{feature_name, feature_description, coverage_level, ...}`

OpenAPI spec: `http://localhost:8000/docs`

---

## 8. Testing Strategy

### Current Tests

- `backend/tests/test_health.py`: Health endpoint returns 200 and expected body fields.

### Test Execution

With the project venv activated, from the project root:

```bash
cd backend && python -m pytest tests/ -v
```

If the venv is not activated, use the venv’s Python: `cd backend && ..\venv\Scripts\python.exe -m pytest tests/ -v` (Windows) or `../venv/bin/python -m pytest tests/ -v` (macOS/Linux).

### Gaps and Recommendations

- **Unit tests**: `TestCaseService` methods, `prompt_builder`, `embeddings`, `token_allocation`.
- **Integration tests**: Batch flow with mocked LLM.
- **E2E**: Playwright/Cypress for critical UI flows.
- **LLM output**: Snapshot tests for JSON parsing and fallbacks.

---

## 9. Scalability Considerations

### Current Limitations

- **In-memory storage**: `_store` and `_batch_store` are process-local; no persistence across restarts.
- **Single process**: No horizontal scaling; batches run in one process.
- **Embeddings**: OpenAI API calls add latency and cost; no local embedding option.
- **Ollama**: No load balancing; single instance.

### Suggested Improvements

- **Persistence**: PostgreSQL/SQLite for test cases and batch state.
- **Task queue**: Celery/RQ for batch jobs; Redis for state.
- **Caching**: Cache embeddings per scenario text; TTL-based invalidation.
- **Rate limiting**: Protect LLM and embedding endpoints.
- **Local embeddings**: Use sentence-transformers for on-prem, embedding-free dedup fallback.

---

## 10. Security Considerations

### Implemented

- **CSV filenames**: `sanitize_feature_name()` prevents path traversal; no raw user input in filenames.
- **Route order**: `/csv-filename` defined before `/{test_case_id}` to avoid UUID matching issues.
- **Pydantic validation**: Request bodies validated; malformed input rejected.

### Not Implemented

- **Authentication**: No auth; API is open.
- **Authorization**: No RBAC.
- **API key**: `api_key_header_name` in config is unused.
- **Secrets**: API keys (OpenAI, Gemini, Groq) from env; ensure `.env` is not committed.

### Recommendations

- Add API key or OAuth for production.
- Rate limit per client to reduce abuse.
- Validate/sanitize LLM output before storage (already done via Pydantic + `_clean_test_case_data`).
- Use secrets management for API keys (OpenAI, Gemini, Groq) in production.
