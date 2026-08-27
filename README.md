# Lenny Growth Assistant

> A RAG-powered conversational AI grounded in 300+ Lenny's Podcast transcripts — with Ship 30 for 30 essay generation, a live artifact viewer, and runtime LLM switching between local Ollama and cloud providers.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue) ![Ollama](https://img.shields.io/badge/Ollama-Local-purple) ![Tests](https://img.shields.io/badge/Tests-30%20passing-brightgreen)

---

## Features

- 🎙️ **Grounded Chat** — Every answer cites specific Lenny's Podcast episodes with guest name, episode title, and relevance score
- ✍️ **Ship 30 for 30 Skill** — Generate atomic essays from transcript insights (*Note: Local Ollama targets ~800 words to keep generation time reasonable on CPU; cloud providers like Claude target the full ~1,250 words*)
- 🖼️ **Artifact Viewer** — Side-by-side canvas (Preview + Raw Markdown) with sandboxed iframe rendering
- 🔄 **Flexible LLM Config** — Switch between Claude 3.5 Sonnet, GPT-4o, and local Ollama at runtime without restarting
- ⚙️ **Settings UI** — Configure API keys securely at runtime; keys are stored server-side only (never in browser/DB/logs)
- 🗄️ **Session Persistence** — Full conversation and artifact history stored in PostgreSQL
- 🐳 **One-Command Start** — Docker Compose gets everything running. Works **without any API keys** (Ollama default)

---

## Quick Start (Docker — Recommended)

No API keys required. The app defaults to local Ollama.

```bash
# 1. Clone the project
git clone <repo-url>
cd lenny-growth-assistant

# 2. Copy environment file (all defaults work out of the box)
copy .env.example .env

# 3. Start everything
docker-compose up --build

# 4. Open the app
# Frontend: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

### Using Ollama (local LLM — default)

```bash
# Install Ollama from https://ollama.com, then:
ollama pull qwen3:4b      # Recommended (2.6GB)
# or
ollama pull llama3.2      # Alternative (2GB)

ollama serve              # Keep this running in a separate terminal
```

### Using Cloud Providers (optional)

You can configure API keys at runtime via the **Settings** panel (⚙️ in the sidebar) — no restart needed. Keys are stored server-side only.

Or set them in `.env`:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Desktop | Latest | Recommended setup |
| Ollama | Latest | For local LLM (default) |
| Python | 3.11+ | Only if running without Docker |

---

## Local Development (No Docker)

### 1. Start PostgreSQL

```bash
docker run -d --name lenny-pg \
  -e POSTGRES_USER=lenny \
  -e POSTGRES_PASSWORD=lenny \
  -e POSTGRES_DB=lenny_db \
  -p 5432:5432 postgres:16-alpine
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

# Configure (defaults work for Ollama)
copy ..\.env.example ..\.env

uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
# Open directly in browser, or serve with:
python -m http.server 3000 --directory frontend
# Then open: http://localhost:3000
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` \| `anthropic` \| `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3:4b` | Ollama model to use |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required only if using Anthropic |
| `OPENAI_API_KEY` | _(empty)_ | Required only if using OpenAI |
| `DATABASE_URL` | `postgresql+asyncpg://lenny:lenny@localhost:5432/lenny_db` | PostgreSQL connection |

> **Note**: API keys can also be configured at runtime via the Settings UI — no `.env` edit or restart needed.

---

## Running Tests

```bash
cd backend
.venv\Scripts\activate

# Run all 30 tests
pytest -v

# Coverage report
pytest --cov=app --cov-report=term-missing
```

**Test coverage (30 tests):**
- `test_api.py` — Health, root, model switching endpoints (mocked DB)
- `test_llm.py` — Ollama provider, error handling, factory validation
- `test_rag.py` — Frontmatter parsing, chunking, BM25 retrieval, context formatting
- `test_persistence.py` — Real PostgreSQL: table existence, Session/Message/Artifact CRUD, cascade deletes

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health + RAG index size |
| `POST` | `/api/chat` | Send a message, get RAG-grounded reply with citations |
| `POST` | `/api/sessions` | Create a new conversation session |
| `GET` | `/api/sessions/{id}/history` | Get message history |
| `POST` | `/api/artifacts/generate` | Generate Ship 30 essay, markdown, or HTML artifact |
| `GET` | `/api/artifacts/{id}` | Retrieve artifact by ID |
| `GET` | `/api/artifacts/session/{id}` | List all artifacts for a session |
| `POST` | `/api/models/switch` | Switch active LLM provider at runtime |
| `GET` | `/api/models/current` | Get current model |
| `POST` | `/api/settings/keys` | Set API key server-side (key never logged or stored in DB) |
| `GET` | `/api/settings/providers` | Check which providers are configured |
| `POST` | `/api/settings/test` | Test connection to a provider |

Full interactive docs: **http://localhost:8000/docs**

---

## Troubleshooting

### Ollama not responding
```bash
ollama serve    # in a separate terminal
ollama pull qwen3:4b
```

### "API key not configured" for cloud providers
Use the ⚙️ Settings panel in the sidebar to enter your key at runtime, or set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in `.env`.

### Database connection refused
```bash
docker-compose up db -d
# then restart backend
docker-compose up backend -d
```

### Transcripts not loading
Transcripts are bundled in `data/transcripts/` (303 episode files). If the directory is empty, the BM25 index will be empty. Re-run ingestion or ensure the volume is mounted correctly.

---

## Project Structure

```
lenny-growth-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── config.py            # Settings (pydantic-settings, default: ollama)
│   │   ├── api/
│   │   │   ├── chat.py          # Chat + session endpoints
│   │   │   ├── artifacts.py     # Artifact generation + retrieval
│   │   │   ├── health.py        # Health check
│   │   │   ├── settings.py      # Runtime API key management
│   │   │   └── models.py        # Model switching
│   │   ├── services/
│   │   │   ├── llm.py           # LLM provider abstraction (Ollama/Anthropic/OpenAI)
│   │   │   ├── rag.py           # BM25 retrieval (10,083 chunks, 303 episodes)
│   │   │   ├── ingestion.py     # Transcript chunking + frontmatter parsing
│   │   │   └── ship30.py        # Ship 30 for 30 essay generation skill
│   │   ├── models/
│   │   │   ├── database.py      # SQLAlchemy ORM models (Session, Message, Artifact)
│   │   │   └── schemas.py       # Pydantic request/response schemas
│   │   └── db/
│   │       └── session.py       # Async PostgreSQL session factory
│   ├── tests/
│   │   ├── test_api.py          # API endpoint tests (mocked DB)
│   │   ├── test_llm.py          # LLM provider unit tests
│   │   ├── test_rag.py          # RAG pipeline tests
│   │   └── test_persistence.py  # Real PostgreSQL persistence tests
│   ├── data/transcripts/        # 303 Lenny's Podcast transcript files
│   └── Dockerfile
├── frontend/
│   ├── index.html               # Single-page app with Settings modal
│   ├── style.css                # Dark premium UI
│   └── app.js                   # Vanilla JS: chat, artifacts, model switching, settings
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## Architecture

```
Browser (Vanilla JS)
        │  HTTP
        ▼
  Nginx (port 3000)
        │  proxy /api → :8000
        ▼
  FastAPI Backend (port 8000)
   ├── BM25 RAG Index (10,083 chunks, 303 episodes, in-memory)
   ├── LLM Provider Layer (Ollama / Anthropic / OpenAI)
   └── PostgreSQL (Sessions, Messages, Artifacts)
```
