# Architecture Document: Lenny Growth Assistant

**Version:** 1.0 | **Date:** August 2026

---

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Frontend (Port 3000)                      │
│            HTML + Vanilla CSS/JS — Artifact Viewer           │
└─────────────────────────────┬────────────────────────────────┘
                              │ HTTP/JSON
┌─────────────────────────────▼────────────────────────────────┐
│                  FastAPI Backend (Port 8000)                  │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  /api/chat  │  │/api/artifacts│  │   /api/models/*    │  │
│  └──────┬──────┘  └──────┬───────┘  └────────────────────┘  │
│         │                │                                    │
│  ┌──────▼──────────────────────────────────────────────────┐ │
│  │                    Services Layer                        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │ │
│  │  │  RAG     │  │  Ship30  │  │   LLM    │  │Ingest. │  │ │
│  │  │ (BM25)   │  │  Skill   │  │ Abstrac. │  │Pipeline│  │ │
│  │  └──────────┘  └──────────┘  └────┬─────┘  └────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                       │                       │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  LLM Providers                           │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │ │
│  │  │ Anthropic  │  │  OpenAI   │  │  Ollama (Local)    │ │ │
│  │  │  Claude    │  │  GPT-4o   │  │  llama3.2/mistral  │ │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │            PostgreSQL (via SQLAlchemy async)             │ │
│  │   sessions | messages | artifacts                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────▼─────────────┐
                │  GitHub (Transcript Repo)  │
                │ ChatPRD/lennys-podcast-... │
                └───────────────────────────┘
```

---

## Data Ingestion Pipeline

### Step 1: Fetch
```
GitHub API → list .md files in /transcripts
            ↓
Raw transcript fetch (per file, cached locally)
```

### Step 2: Parse
```
Raw .md file
  ↓ _parse_frontmatter()
YAML meta: {title, guest, episode, date}  +  body text
  ↓ _clean_text()
Remove timestamps [00:01:23], speaker labels "Lenny:", normalize whitespace
```

### Step 3: Chunk
```
Clean body text
  ↓ _chunk_text(chunk_size=500, overlap=50)
[chunk_0, chunk_1, …, chunk_n]  (word-count based, overlapping)
```

### Step 4: Index
```
All chunks → tokenize (lowercase, strip punctuation)
           → BM25Okapi index (rank_bm25)
           → in-memory singleton
```

---

## RAG Retrieval Flow

```
User query
  ↓ tokenize
BM25 scoring against all chunks (O(n) scan)
  ↓ top-k=5 chunks by score
SourceChunk list  →  format_context()
  ↓
System prompt + context injected into LLM messages
  ↓
LLM response with citations
```

---

## Database Schema

### sessions
| Column | Type | Description |
|---|---|---|
| id | UUID PK | Session identifier |
| created_at | timestamptz | When session was created |
| model_provider | varchar(50) | anthropic / openai / ollama |
| model_name | varchar(100) | Specific model identifier |

### messages
| Column | Type | Description |
|---|---|---|
| id | UUID PK | Message identifier |
| session_id | UUID FK → sessions | Parent session |
| role | varchar(20) | user / assistant |
| content | text | Message body |
| model_provider | varchar(50) | Provider used for this message |
| model_name | varchar(100) | Model used |
| sources | jsonb | Retrieved chunks metadata |
| created_at | timestamptz | Timestamp |

### artifacts
| Column | Type | Description |
|---|---|---|
| id | UUID PK | Artifact identifier |
| session_id | UUID FK → sessions | Parent session |
| artifact_type | varchar(50) | ship30 / markdown / html |
| title | varchar(300) | Derived from first line |
| content | text | Raw markdown/html content |
| sanitized_html | text | Bleach-sanitized for iframe |
| word_count | integer | Approximate word count |
| sources | jsonb | RAG sources used |
| created_at | timestamptz | Timestamp |

---

## Security Model

### HTML Artifact Sandboxing
- All HTML artifacts rendered in `<iframe sandbox="allow-same-origin">`
- No `allow-scripts` — JavaScript cannot execute in artifact frames
- Content sanitized via `bleach.clean()` before storage and display
- Allowed tags: paragraph elements, formatting, headings, tables, links
- Allowed attributes: `href`, `title`, `target`, `class`

### API Security
- CORS configured (restrict `*` origins in production)
- API keys stored only in `.env` (gitignored)
- No auth in MVP — add JWT/OAuth in production

---

## Agent Routing Logic

```
User input
  ↓
Is it a Ship 30 essay request? (explicit button or "write an essay about")
  → ship30_skill.generate() → RAG → LLM → ArtifactResponse
  
Is it a general question?
  → rag.retrieve() → LLM → ChatResponse with sources

Is it a model switch?
  → llm.build_provider() → health_check() → update singleton
```

---

## LLM Provider Abstraction

All providers implement:
```python
async def complete(messages: list[dict], system: str) -> str
async def health_check() -> bool
```

Graceful degradation:
- Anthropic rate limit → retry with exponential backoff (tenacity)
- Ollama not running → `RuntimeError("Ollama is not running. Start with: ollama serve")`
- Model not pulled → `RuntimeError("Model 'X' not found. Run: ollama pull X")`
- API key missing → `ValueError("ANTHROPIC_API_KEY is not set")`

---

## Performance Characteristics

| Operation | Latency | Notes |
|---|---|---|
| BM25 index build (26k chunks) | ~3s | One-time at startup |
| BM25 retrieval (top-5) | <50ms | In-memory |
| Claude 3.5 Sonnet completion | 3–8s | Cloud, varies by length |
| GPT-4o completion | 3–10s | Cloud, varies |
| Ollama llama3.2 (local) | 15–45s | Depends on hardware |
| DB write (message) | <20ms | Async PostgreSQL |
