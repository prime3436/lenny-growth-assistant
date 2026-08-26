# PRD: Lenny Growth Assistant

**Version:** 1.0 | **Date:** August 2026 | **Author:** Forward Deployed Engineer Candidate

---

## 1. Problem Statement

Product managers, founders, and growth practitioners spend hours combing through 300+ Lenny's Podcast episodes to extract actionable insights. There's no easy way to:
- Ask a specific question and get a cited, trustworthy answer
- Transform those insights into polished written content
- Access the information without an internet connection or cloud API dependency

---

## 2. User Persona

**Primary: "Busy PM / Founder"**
- 28–45 years old, senior IC or founder
- Has listened to 20–50 Lenny episodes but can't recall specifics
- Needs: fast, cited answers + publishable content
- Context: prep for board meeting, writing LinkedIn posts, building strategy decks

**Secondary: "Growth Writer"**
- Writes about product for Substack, LinkedIn, or company blog
- Needs: Ship 30-style atomic essays grounded in credible sources
- Values: originality, skimmability, actionable takeaways

---

## 3. Discovery Brief

The opportunity: Lenny's Podcast is one of the highest-quality repositories of product knowledge in the world. 300+ episodes × ~90 minutes = ~450 hours of expert insight. The bottleneck is retrieval — humans can't efficiently search across all episodes.

Solution: A RAG-powered assistant that ingests, indexes, and retrieves transcript chunks, then uses an LLM to synthesize grounded answers with explicit citations.

---

## 4. Success Metrics

| Metric | Target |
|---|---|
| Answer grounding rate | >90% of answers include at least 1 cited source |
| Retrieval relevance (BM25 top-1 precision) | >70% on manual test set |
| Ship 30 essay word count | 1,100–1,400 words |
| p95 response latency (cloud) | <8s |
| p95 response latency (Ollama local) | <30s |
| Session persistence | 100% — no data lost across refreshes |

---

## 5. Feature Requirements

### Must Have (MVP)
- [x] RAG-grounded chat with source citations
- [x] Multi-turn session memory (PostgreSQL)
- [x] Ship 30 for 30 essay generation skill
- [x] Side-by-side artifact viewer (Preview + Raw)
- [x] Cloud LLM support (Anthropic + OpenAI)
- [x] Local LLM support (Ollama)
- [x] Runtime model switching
- [x] One-command Docker startup

### Should Have
- [x] Streaming responses (SSE)
- [ ] Fuzzy search / semantic ranking (vector embeddings)
- [ ] Export artifact as PDF / Markdown file

### Won't Have (v1)
- [ ] User authentication / multi-user
- [ ] Fine-tuned models
- [ ] Mobile-native app

---

## 6. Assumptions

1. The ChatPRD/lennys-podcast-transcripts repo is publicly available and accurate
2. BM25 is sufficient for MVP retrieval quality (no GPU/embeddings required)
3. Users have sufficient disk space for local Ollama models (~4GB+)
4. The app is single-user for the MVP (no auth needed)

---

## 7. Risks & Trade-offs

| Risk | Mitigation |
|---|---|
| BM25 retrieval misses semantic matches | Add vector embeddings in v2 |
| Ollama latency may frustrate users | Show streaming + latency warning in UI |
| Transcript quality varies | `_clean_text()` removes timestamps/labels |
| LLM hallucination | Strict system prompt + source citation requirement |
| API key exposure | `.env` in `.gitignore`, `.env.example` provided |

---

## 8. Scope

**In scope:** Chat, RAG, Ship 30 essays, artifact viewer, model switching, Docker, tests, docs

**Out of scope:** Auth, billing, mobile, vector DB, fine-tuning
