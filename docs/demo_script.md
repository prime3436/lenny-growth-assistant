# Demo Video Script — Lenny Growth Assistant
**Duration:** ~2:45 min | **Format:** Screen recording with narration

---

## [0:00–0:15] HOOK — Start Strong

> **Say:** "This is the Lenny Growth Assistant — an AI that's read every episode of Lenny's Podcast so you don't have to. Let me show you what it can do in under three minutes."

*Screen: Open the app. The dark UI loads with the welcome screen visible.*

---

## [0:15–0:35] ARCHITECTURE CALLOUT (30 sec)

> **Say:** "Before I demo, quick architecture note. The backend is FastAPI with a BM25 retrieval index over 26,000 transcript chunks. Every answer is grounded in the actual podcast — not hallucinated. And critically, this runs entirely locally using Ollama with Qwen3."

*Screen: Briefly show `http://localhost:8000/docs` — the auto-generated API docs with all endpoints visible.*

---

## [0:35–1:05] CORE CHAT — LIVE RAG (30 sec)

*Screen: Type and send a question. Watch tokens stream in real-time.*

> **Ask:** `"How do the best B2B SaaS companies find their first 10 customers?"`

> **Say:** "Watch — tokens stream live as the model generates. At the bottom you'll see the source citations: which episodes, which guests. This isn't GPT making things up — every claim traces back to a real Lenny episode."

*Highlight the source chips that appear below the response.*

---

## [1:05–1:35] SHIP 30 FOR 30 ESSAY (30 sec)

*Screen: Click the "Ship 30" button → Modal appears → Type topic → Click Generate*

> **Ask topic:** `"Why most PMs never build products people love"`

> **Say:** "Now watch the artifact panel on the right. I'm generating a full Ship 30 for 30 essay — 1,250 words in the format that's actually publishable on LinkedIn or Substack. The hook, the body callouts, the takeaway — all grounded in Lenny's interviews."

*Show the essay streaming into the iframe preview. Scroll through it.*

> **Say:** "I can copy it, download it as Markdown, or view the raw source. One click."

*Click export button — show download.*

---

## [1:35–1:55] MODEL SWITCHING — OLLAMA (20 sec)

*Screen: Sidebar → Click Qwen3 8B model option*

> **Say:** "This is the key demo requirement: switching to a local model. I'm now running on Qwen3 8B through Ollama — zero cloud API calls, completely private. Let me ask the same question."

*Send: `"What metrics actually predict product-market fit?"`*

> **Say:** "Same RAG pipeline, same citations, now running entirely on local hardware."

*Show the streamed response with source chips.*

---

## [1:55–2:20] MULTI-TURN MEMORY (25 sec)

*Screen: Continue the conversation in the same session*

> **Ask:** `"Give me a concrete example from the episodes you cited"`

> **Say:** "The assistant remembers the full conversation. I'm asking a follow-up — no context repetition needed — and it pulls the right episode detail."

*Show the grounded follow-up response.*

---

## [2:20–2:35] TRAJECTORY LOGS (15 sec)

*Screen: Open browser → `http://localhost:8000/api/trajectories`*

> **Say:** "Every interaction is logged as a structured agent trajectory — session ID, turn index, model used, latency in milliseconds, sources retrieved, response preview. This is how you audit what the agent actually did."

*Briefly show the JSON response.*

---

## [2:35–2:45] CLOSE

> **Say:** "RAG-grounded chat, Ship 30 essays, live streaming, local Ollama support, full session persistence in PostgreSQL, and trajectory logging. One command to start. All the code is in the repo."

*Screen: Terminal showing `uvicorn app.main:app` startup log with the BM25 index chunk count.*

---

## Recording Checklist

- [ ] Dark terminal (use Windows Terminal)
- [ ] Browser zoom at 110% for readability
- [ ] Ollama running: `ollama serve`
- [ ] Backend running: `uvicorn app.main:app --reload --port 8000`
- [ ] PostgreSQL running (Docker)
- [ ] Frontend open in Chrome/Edge at `localhost:3000` or via file://
- [ ] Record at 1920×1080, 30fps
- [ ] No personal info visible on screen

## Key Technical Points to Mention

1. **BM25 over 26,000+ chunks** from 300+ episodes — no GPU, no embeddings needed
2. **Ollama + Qwen3 8B** — fully local, private, no API key required
3. **SSE streaming** — tokens pushed live, not waiting for full response
4. **Bleach sanitization + sandboxed iframe** — secure artifact rendering
5. **PostgreSQL persistence** — sessions survive restarts
6. **Trajectory logging** — every turn logged with latency, sources, model
