# DocuMind — Code Deliverables

AI-powered contract analysis service: upload legal documents, extract clauses via LLM, classify risk levels.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for full-stack setup)

## Setup

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env to add your AI_API_KEY (optional — health endpoint works without it)
```

### 2. Run tests (no Docker needed)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

### 3. Run the full stack with Docker Compose

```bash
docker compose up --build -d
```

This starts PostgreSQL, Redis, and the app. Wait for all services to become healthy:

```bash
docker compose ps
```

### 4. Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 5. Shut down

```bash
docker compose down
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/documind` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `AI_API_KEY` | *(empty)* | API key for the AI provider (optional for local dev) |
| `AI_PROVIDER` | `anthropic` | AI provider (`anthropic` or `openai`) |
| `AI_MODEL` | `claude-sonnet-4-5-20250514` | Model to use for clause extraction |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size in MB |

## What this codebase demonstrates

- **Analysis orchestration** with retry logic, error handling, and status tracking
- **AI prompt engineering** with structured JSON response validation
- **Multi-stage Docker build** with health checks and non-root user
- **CI/CD pipeline** (lint, test, build, deploy)
- **Worker pseudocode** for queue-based processing with distributed locks

> The API exposes only a `/health` endpoint by design. Full API routes and the worker implementation are described in the exercise explanation answers.

## Project Structure

```
src/
├── api/
│   └── __init__.py            # FastAPI app + /health endpoint
├── config.py                  # App settings (pydantic-settings)
├── models/                    # SQLAlchemy models + enums
│   ├── analysis.py            # Analysis entity (status, timing, retry tracking)
│   ├── clause.py              # Extracted clause (type, risk, confidence)
│   ├── document.py            # Uploaded document (file metadata, extracted text)
│   ├── template.py            # Analysis template (custom prompts, clause filters)
│   └── ...
├── services/                  # Business logic
│   ├── analysis_service.py    # Core orchestration
│   ├── ai_client.py           # Provider abstraction (Anthropic/OpenAI)
│   ├── retry.py               # Exponential backoff
│   └── exceptions.py          # Domain exceptions
├── prompts/                   # AI prompt construction + validation
│   ├── clause_extraction.py   # Prompt builder + response parser
│   └── schemas.py             # Pydantic response schemas
└── workers/
    └── worker.py              # Queue worker (pseudocode)
tests/
├── conftest.py                # Shared fixtures, MockAIClient
├── test_analysis_service.py   # 6 tests: success, retry, timeout, validation, errors
└── test_prompt_validation.py  # 7 tests: parsing, fences, edge cases
```

## File → Exercise Map

| Exercise | Files | What |
|----------|-------|------|
| 3.1 | `src/services/analysis_service.py`, `tests/test_analysis_service.py` | Analysis orchestration with retry, error handling, status tracking |
| 3.3 | `src/prompts/`, `src/prompts/schemas.py`, `tests/test_prompt_validation.py` | AI prompt engineering, JSON response validation, Pydantic schemas |
| 4.1 | `Dockerfile`, `.github/workflows/ci-cd.yml` | Multi-stage Docker build, CI/CD pipeline (lint → test → build → deploy) |
| 5.1c | `src/workers/worker.py` | Worker pseudocode: dedup, distributed lock, graceful shutdown |
