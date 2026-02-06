# ai_testcase_generator

Internal backend service for generating high-quality test cases from
requirements and specifications, designed with clean architecture and
prepared for local Ollama integration.

## Project layout

```text
ai_testcase_generator/
 ├── main.py               # Single entrypoint (FastAPI app factory)
 ├── api/                  # Routers / endpoints only (health, testcases)
 ├── core/                 # Configuration, settings, logging
 ├── services/             # Business logic
 ├── schemas/              # Pydantic request & response models
 ├── utils/                # Helpers (prompt builder, Excel export)
 ├── providers/            # LLM provider abstraction (Ollama, OpenAI)
 ├── tests/                # Automated tests
 ├── requirements.txt
 └── README.md
```

## Installation

From the project directory:

```bash
pip install -r requirements.txt
```

## Running the service

From the project directory (`ai_testcase_generator/`):

```bash
python main.py
```

Or as a module (from the parent of `ai_testcase_generator/`):

```bash
python -m ai_testcase_generator
```

The API will be available at `http://localhost:8000`.

### Key endpoints

- `GET /api/health` — health check for liveness/readiness.
- `POST /api/testcases/from-requirements` — generate test cases from requirements.
- `POST /api/testcases/generate-test-cases` — generate test cases via LLM (Ollama or OpenAI). Request body: `feature_name`, `feature_description`, `coverage_level` (low|medium|high|comprehensive; default medium). Optional `?generate_excel=true` for Excel download.
- `GET /api/testcases` — list generated test cases (in-memory).
- `GET /api/testcases/{id}` — fetch a specific test case by ID.

