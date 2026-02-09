# AI Test Case Generator

Internal service for generating high-quality test cases from requirements and feature descriptions using LLMs (Ollama, OpenAI, Gemini, or Groq). Includes a React UI for batch generation, per-feature and merged CSV export, **Excel template export** (single feature or all features combined), and test case deletion.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Ollama** (optional) — for local generation. Install from [ollama.ai](https://ollama.ai) and run `ollama pull llama3.2:3b` (or your chosen model).
- **OpenAI API key** (optional) — for cloud generation and embedding-based deduplication. Set `AI_TC_GEN_OPENAI_API_KEY`.
- **Gemini API key** (optional) — for Gemini 2.5 Flash. Set `AI_TC_GEN_GEMINI_API_KEY`.
- **Groq API key** (optional) — for Llama 3.3 70B (Groq). Set `AI_TC_GEN_GROQ_API_KEY`.

## Project layout

```text
ai_testcase_generator/
├── backend/                # Python FastAPI app (run from here)
│   ├── app/                # Application package
│   │   ├── main.py         # FastAPI app (uvicorn app.main:app)
│   │   ├── api/            # Health + test case endpoints
│   │   ├── core/           # Config, logging
│   │   ├── providers/      # LLM providers (Ollama, OpenAI, Gemini, Groq)
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic (generation, batch, dedup)
│   │   └── utils/          # Prompts, embeddings, token allocation, Excel, excel_template_merge
│   ├── tests/
│   ├── main.py             # Optional entrypoint (python main.py)
│   └── requirements.txt
├── frontend/               # React + Vite UI (BatchResultsView, TemplateUploadModal, useTemplateStorage)
├── package.json            # Root: npm run dev (backend + frontend)
├── .env                    # Backend env vars (at root; backend loads via path)
└── DOCUMENTATION.md        # Full production documentation
```

## Installation

### Backend

From the project root, install Python dependencies in the backend:

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

Requires **Node.js 18+**. From the project root:

```bash
cd frontend
npm install
```

Or, for the full setup (root + frontend):

```bash
npm install
cd frontend && npm install
```

**Environment (optional)** — Create `frontend/.env` if you need to override the API base URL (e.g. when running frontend separately or in production):

```bash
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

Leave this unset during local dev with `npm run dev` from root; the Vite proxy forwards `/api` to the backend automatically.

**Available scripts** (from `frontend/`):

| Script | Description |
|--------|-------------|
| `npm run dev` | Start dev server (port 5173) with HMR |
| `npm run build` | Production build → `dist/` |
| `npm run preview` | Serve production build locally |

## Running the application

### Recommended: Backend + frontend together

From the project root:

```bash
npm run dev
```

This starts:

- **Backend** at `http://localhost:8000`
- **Frontend** at `http://localhost:5173` (proxies `/api` to the backend)

Open `http://localhost:5173` in your browser.

**Export options (batch results):**

- **Export CSV** — Per-feature CSV download.
- **Export All Features** — Merged CSV of all features (deduplicated).
- **Export to Excel Template** — Per-feature: upload an `.xlsx` template; test cases are merged into the template’s “Test Cases” sheet (Summary sheet unchanged). Optional “Remember this template” stores it in the browser for next time.
- **Export All to Excel Template** — Same template upload; all features’ test cases are combined into the single “Test Cases” sheet (Feature1’s cases first, then Feature2’s, etc.). Column A = sequential No. (1, 2, …); Column B = Test ID per feature (e.g. `TC_FEAT1_001`, `TC_FEAT2_001`).

### Run backend only

From the project root:

```bash
cd backend && uvicorn app.main:app --reload
```

Or from inside `backend/`:

```bash
cd backend
uvicorn app.main:app --reload
```

Alternatively: `cd backend && python main.py` (no reload).

API at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

### Run frontend only

```bash
cd frontend && npm run dev
```

Ensure the backend is already running at `http://localhost:8000`, or set `VITE_API_BASE_URL` in `frontend/.env` to point to the API.

### Run backend tests

From the project root:

```bash
cd backend && python -m pytest tests/ -v
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_TC_GEN_DEFAULT_LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `gemini`, or `groq` |
| `AI_TC_GEN_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `AI_TC_GEN_OLLAMA_MODEL` | `llama3.2:3b` | Ollama model name |
| `AI_TC_GEN_OPENAI_API_KEY` | — | Required for OpenAI provider and embeddings |
| `AI_TC_GEN_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `AI_TC_GEN_GEMINI_API_KEY` | — | Required for Gemini provider. Set in `.env`. |
| `AI_TC_GEN_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `AI_TC_GEN_GROQ_API_KEY` | — | Required for Groq provider (Llama 3.3 70B). Set in `.env`. |
| `AI_TC_GEN_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `VITE_API_BASE_URL` | (empty) | API base URL in production; empty uses dev proxy |

Use `.env` in the project root for backend variables (the backend loads it from the project root when run from `backend/`). Use `frontend/.env` for `VITE_*` variables.

## Key API endpoints

- `GET /api/health` — health check
- `POST /api/testcases/generate-test-cases` — single-feature generation. Body: `feature_name`, `feature_description`, `coverage_level` (low|medium|high|comprehensive). Optional `?generate_excel=true`.
- `POST /api/testcases/batch-generate` — start batch; returns `batch_id`
- `GET /api/testcases/batches/{batch_id}` — batch status and per-feature results
- `POST /api/testcases/batches/{batch_id}/features/{feature_id}/retry` — retry failed feature
- `GET /api/testcases/batches/{batch_id}/export-all` — download merged CSV
- `POST /api/testcases/export-to-excel` — **Export to Excel template** (single feature). Multipart: `template` (.xlsx), `testCases` (JSON), `featureName`. Returns Excel with test cases merged into the template’s “Test Cases” sheet.
- `POST /api/testcases/export-all-to-excel` — **Export all features to Excel template**. Multipart: `template` (.xlsx), `testCasesByFeature` (JSON array of `{ featureName, testCases }`). Returns one Excel file with all features’ test cases combined in the template’s “Test Cases” sheet (Summary sheet unchanged).
- `DELETE /api/testcases/{id}` — delete test case (excluded from exports)
- `GET /api/testcases/csv-filename?feature_name=` — OS-safe filename for per-feature export

See `DOCUMENTATION.md` for full API reference, Excel template structure, and architecture details.
