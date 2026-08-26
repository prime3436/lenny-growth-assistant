# Manual Test Plan & QA Verification Suite

**Project:** Lenny Growth Assistant  
**Date:** August 2026  
**Scope:** Frontend UI, REST API, Database Persistence, RAG Retrieval, LLM Integration, Artifact Sandboxing

---

## 1. Overview

This document specifies the end-to-end manual testing procedures, test cases, inputs, expected outcomes, and pass/fail criteria for verifying the Lenny Growth Assistant web application.

---

## 2. Test Environment Matrix

| Component | Target Environment | Port / Endpoint |
|---|---|---|
| Web Frontend | Chromium / Firefox / Safari | http://localhost:3000 |
| REST API & Swagger | FastAPI / Uvicorn | http://localhost:8000/docs |
| Relational DB | PostgreSQL 16 (Docker) | localhost:5432 |
| Local LLM | Ollama (qwen3:4b) | http://localhost:11434 |
| Cloud LLMs | Anthropic (claude-3-5-sonnet), OpenAI (gpt-4o) | External APIs via secure env keys |

---

## 3. Test Cases & Verification Checklist

### Suite 1: Application Bootstrapping & Health Checks

| Test ID | Test Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| **TC-BOOT-01** | Container orchestration | Run `docker compose up -d` | All 3 containers (`db`, `backend`, `frontend`) start up and enter `healthy` status. | ✅ PASS |
| **TC-BOOT-02** | System health endpoint | `GET http://localhost:8000/health` | Returns `HTTP 200` with JSON containing `status: "ok"`, `db: true`, `rag_index_size: 10083`. | ✅ PASS |
| **TC-BOOT-03** | Localhost Web UI routing | Navigate to `http://localhost:3000` | Nginx serves `index.html` with full dark mode theme and sidebars intact. | ✅ PASS |

---

### Suite 2: RAG Grounding & Chat Interactions

| Test ID | Test Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| **TC-CHAT-01** | Session creation | Click "+ New Conversation" in UI | Unique UURD session created, conversation thread cleared, session persisted in PostgreSQL. | ✅ PASS |
| **TC-CHAT-02** | RAG query with citations | Ask: *"What are the most effective tactics for finding product-market fit?"* | Assistant returns structured answer citing specific guest names (e.g., Brian Chesky, Superhuman / Rahul Vohra) and episode titles. | ✅ PASS |
| **TC-CHAT-03** | Suggestion chips | Click any preset chip (e.g., *"First 10 customers in B2B SaaS"*) | Query auto-fills into textarea, sends immediately, and displays streaming response. | ✅ PASS |
| **TC-CHAT-04** | Multi-turn conversation memory | Send follow-up: *"How does that apply to enterprise vs consumer startups?"* | Assistant retains previous conversation turn context and answers comparatively. | ✅ PASS |
| **TC-CHAT-05** | Streaming SSE tokens | Watch response generation | Tokens render in real time via Server-Sent Events without UI freezing or flickering. | ✅ PASS |

---

### Suite 3: Model Selection & Dynamic Switching

| Test ID | Test Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| **TC-MOD-01** | Local model switch | Select `Qwen3 4B ⁐ (Ollama µ Local)` from sidebar | Status badge updates, subsequent messages route to local Ollama instance on port 11434. | ✅ PASS |
| **TC-MOD-02** | Cloud model switch | Select `Claude 3.5 Sonnet` or `GPT-4o` with API key | Provider switches cleanly without container reboot; `/api/models/current` reflects active model. | ✅ PASS |
| **TC-MOD-03** | Graceful fallback on missing keys | Select Anthropic without API key configured | Returns clear, user-friendly notification prompt without crashing backend. | ✅ PASS |

---

### Suite 4: Ship 30 for 30 Artifact Generation & Security

| Test ID | Test Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| **TC-ART-01** | Ship 30 modal trigger | Click "Ship 30" button beside input box | Modal dialog opens with topic prompt and guidance. | ✅ PASS |
| **TC-ART-02** | Atomic essay synthesis | Enter *"The Cold Start Problem in B2B Marketplaces"* & submit | Generates ~1,250-word structured atomic essay following hook, setup, core idea, bulleted insights, and conclusion CTA. | ✅ PASS |
| **TC-ART-03** | Side-by-side artifact split view | Inspect right-side panel | Artifact renders alongside chat window without obscuring conversation history. | ✅ PASS |
| **TC-ART-04** | Dual view tabs (Preview & Raw) | Switch between "Preview" tab and "Raw" tab | "Preview" renders styled HTML; "Raw" shows plain Markdown source. | ✅ PASS |
| **TC-ART-05** | HTML sanitization & iframe isolation | Render artifact containing custom tags | Backend filters dangerous scripts via `bleach` and iframe enforces `sandbox="allow-same-origin"`. | ✅ PASS |
| **TC-ART-06** | Export artifact | Click "Download as Markdown" button | Downloads `.md` file with essay title and timestamped citations. | ✅ PASS |

---

### Suite 5: Error Handling & Resilience

| Test ID | Test Scenario | Steps | Expected Result | Status |
|---|---|---|---|---|
| **TC-ERR-01** | Offline / disconnected Ollama | Stop Ollama process and send chat query | Frontend displays toast warning: *"Ollama is not running. Start it with `ollama serve`"*. | ✅ PASS |
| **TC-ERR-02** | Out of domain queries | Ask: *"What is the capital of Mars?"* | Assistant clearly indicates the query is outside Lenny podcast transcript context. | ✅ PASS |
| **TC-ERR-03** | Database recovery | Restart `db` container while app is running | Backend reconnects via async connection pool upon next request. | ✅ PASS |

---

## 4. Automated Regression Execution

To execute automated tests backing this manual test plan:

```bash
# Run backend pytest suite (25 test cases)
pytest backend/tests/ -v

# Check API health
curl -s ��i��hq�a��|�M?�楶�