# Lenny Growth Assistant

> A RAG-powered conversational AI grounded in 300+ Lenny's Podcast transcripts — with Ship 30 for 30 essay generation and a live artifact viewer.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue) ![Ollama](https://img.shields.io/badge/Ollama-Local-purple)

---

## Features

- 🎙️ **Grounded Chat** — Every answer cites specific Lenny's Podcast episodes
- ✍️ **Ship 30 for 30 Skill** — Generate ~1,250-word atomic essays from transcript insights
- 🖼️ **Artifact Viewer** — Side-by-side canvas (Preview + Raw Markdown) with sandboxed iframe
- 🔄 **Model Switching** — Toggle between Claude, GPT-4o, and local Ollama at runtime
- 🗄️ **Session Persistence** — Full conversation history stored in PostgreSQL
- 🐳 **One-Command Start** — Docker Compose gets everything running instantly

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | For running backend locally |
| Docker Desktop | Latest | For `docker-compose` setup |
| PostgreSQL | 16 (via Docker) | Auto-started by Compose |
| Ollama | Latest | For local LLM (optional) |
| Node.js | Not required | Frontend is pure HTML/JS |

---

## Quick Start (Docker — Recommended)

```bash
# 1. Clone the project
cd C:\Users\HP\Downloads\lenny-growth-assistant

# 2. Copy and configure .env
copy .env.example .env
# Edit .env — set at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY
# Or set LLM_PROVIDER=ollama for local-only mode

# 3. Start everything
docker-compose up --build

# 4. Open the app
# Frontend: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

---

## Local Development (No Docker)

### 1. Set up PostgreSQL

```bash
# Using Docker for DB only
docker run -d --name lenny-pg -e POSTGRES_USER=lenny -e POSTGRES_PASSWORD=lenny -e POSTGRES_DB=lenny_db -p 5432:5432 postgres:16-alpine
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy ..\\.env.example ..\\.env
# Edit ../.env with your API keys

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

Open `frontend/index.html` directly in your browser, or use a simple server:

```bash
# Python simple server
python -m http.server 3000 --directory frontend

# Then open: http://localhost:3000
```

---

## Ollama Setup (Local LLM)

```bash
# 1. Download Ollama from https://ollama.com
# 2. Install and start Ollama

# 3. Pull a model
ollama pull llama3.2       # Recommended (4GB)
# or
ollama pull mistral        # Alternative (4GB)
# or
ollama pull phi3           # Lightweight (2.3GB)

# 4. Set in .env:
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2

# 5. Make sure Ollama is running
ollama serve
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `anthropic` | `anthropic` \| `openai` \| `ollama` |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | Your Anthropic API key |
| `OPENAI_API_KEY` | If using OpenAI | — | Your OpenAI API key |
| `OLLAMA_BASE_URL` | If using Ollama | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | If using Ollama | `llama3.2` | Model to use |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://lenny:lenny@localhost:5432/lenny_db` | PostgreSQL connection |

---

## Running Tests

```bash
cd backend
.venv\Scripts\activate

# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health + RAG index size |
| `POST` | `/api/sessions` | Create a new conversation session |
| `GET` | `/api/sessions/{id}/history` | Get message history |
| `POST` | `/api/chat` | Send a message, get RAG-grounded reply |
| `POST` | `/api/artifacts/generate` | Generate Ship 30 essay or markdown |
| `GET` | `/api/artifacts/{id}` | Retrieve artifact by ID |
| `POST` | `/api/models/switch` | Switch active LLM provider |
| `GET` | `/api/models/current` | Get current model |

Full interactive docs: **http://localhost:8000/docs**

---

## Troubleshooting

### "Ollama is not running"
```bash
ollama serve   # in a separate terminal
```

### "Model not found in Ollama"
```bash
ollama pull llama3.2
```

### Database connection refused
```bash
# Make sure PostgreSQL is running
docker ps | grep lenny-pg
# If not, start it:
docker-compose up db -d
```

### Transcripts not loading
The app fetches transcripts from [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts) on first run and caches them in `data/transcripts/`. Ensure you have internet access on the first startup.

---

## Project Structure

```
lenny-growth-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app + lifespan
│   │   ├── config.py         # Settings (pydantic-settings)
│   │   ├── api/              # Route handlers
│   │   ├── services/         # LLM, RAG, Ship30, Ingestion
│   │   ├── models/           # Pydantic schemas + SQLAlchemy ORM
│   │   └── db/               # Async session factory
│   ├── tests/                # Pytest test suite
│   └── Dockerfile
├── frontend/
│   ├── index.html            # Single-page app
│   ├── style.css             # Dark premium UI
│   └── app.js                # Vanilla JS logic
├── data/transcripts/         # Cached transcript files
├── docs/                     # PRD, design, architecture
├── docker-compose.yml
├── nginx.conf
└── .env.example
```
