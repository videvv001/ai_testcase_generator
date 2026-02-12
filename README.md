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

## First-time setup

Run these steps once after cloning or moving the project. All commands are from the **project root** (e.g. `F:\project\tool\ai_testcase_generator` or `ai_testcase_generator/`).

### 1. Python virtual environment and backend dependencies

Create a virtual environment and install backend dependencies so the API runs in an isolated environment (avoids path issues when moving the project).

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

**macOS / Linux (bash):**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Node dependencies

Install root and frontend dependencies (concurrently is used by `npm run dev`):

```bash
npm install
npm install --prefix frontend
```

### 3. Environment (optional)

- **Backend:** Copy `.env.example` to `.env` in the project root and set API keys if you use OpenAI, Gemini, or Groq. The backend loads `.env` from the project root.
- **Frontend:** Only needed if you run the frontend against a different API URL; see [Frontend](#frontend) below.

### 4. Run the app

```bash
npm run dev
```

This starts the backend at `http://localhost:8000` and the frontend at `http://localhost:5173`. Open `http://localhost:5173` in your browser.

The root `package.json` dev script uses the project’s `venv` for the backend on Windows, so you don’t need to activate the venv before `npm run dev`. On macOS/Linux, activate the venv first, then run `npm run dev`.

---

