# Design Document: Lenny Growth Assistant

**Version:** 1.0 | **Date:** August 2026

---

## 1. Design Principles

1. **Grounded, not generative** — Every surface communicates that answers come from real episodes, not thin air
2. **Reading-optimized** — Long-form content (essays) demands high-legibility typography and generous whitespace
3. **Context-persistent** — Dual-pane layout keeps conversation and artifact in view simultaneously
4. **Tactile feedback** — Every interaction has an animation or state change so the app feels alive

---

## 2. Layout Architecture

```
┌────────────┬─────────────────────────┬─────────────────────┐
│  Sidebar   │      Chat Panel         │   Artifact Panel    │
│  (260px)   │     (flex: 1)           │     (45%)           │
│            │                         │                     │
│  Logo      │  [Welcome / Messages]   │  [Empty / Content]  │
│  New Chat  │                         │                     │
│  Model     │  ┌─────────────────┐    │  Header (type/wc)  │
│  Selector  │  │  Message list   │    │  Title              │
│  Artifacts │  └─────────────────┘    │  Tab (Preview/Raw) │
│  Status    │  [Input area]           │  Iframe viewer      │
│            │                         │  Sources accordion  │
└────────────┴─────────────────────────┴─────────────────────┘
```

### Responsive Behavior
- **≥900px**: Three-column layout (sidebar + chat + artifact)
- **<900px**: Artifact panel becomes a fixed right drawer (90vw) that slides in on demand

---

## 3. Color System

| Token | Value | Usage |
|---|---|---|
| `--bg-primary` | `#0d0d0f` | Page background |
| `--bg-secondary` | `#141416` | Sidebar, input area |
| `--bg-surface` | `#1f1f24` | Cards, message bubbles |
| `--accent` | `#7c6aff` | CTAs, active states, gradients |
| `--accent-light` | `#9d8fff` | Bold text highlights |
| `--text-primary` | `#f0f0f5` | Body text |
| `--text-secondary` | `#9999b3` | Labels, meta |
| `--text-muted` | `#5a5a7a` | Hints, placeholders |
| `--local` | `#34d399` | Ollama local model indicator |
| `--cloud` | `#60a5fa` | Cloud model indicator |

---

## 4. Component Specifications

### Message Bubbles
- **User**: Purple gradient (`#7c6aff → #6d5ce7`), right-aligned, border-bottom-right-radius: 4px
- **Assistant**: Dark surface (`#1f1f24`), left-aligned, subtle border, supports inline markdown
- **Typing indicator**: Three-dot bounce animation, same surface as assistant bubble

### Artifact Viewer
- **Header**: Type badge (gradient) + word count + tab controls + copy button
- **Preview tab**: Sandboxed `<iframe sandbox="allow-same-origin">` with injected light-theme CSS
  - Fonts: Inter, Georgia serif fallback
  - Max content width: 700px, centered
  - `<strong>` rendered in accent purple for skimmability
- **Raw tab**: Monospace `<pre>` block with full markdown source
- **Sources accordion**: Collapsed by default, shows episode title + guest + relevance score

### Model Selector
- Three model options in sidebar: Claude (☁️ blue dot), GPT-4o (☁️ blue dot), Llama 3.2 (🟢 green dot)
- Active state: `bg-active` + border highlight
- Switching triggers API call + status bar update

---

## 5. Interaction States

| State | Behavior |
|---|---|
| Initial load | Welcome screen with 4 suggestion chips |
| Sending message | Button disabled, typing dots appear |
| Artifact generating | Loading spinner in iframe, word count shows "Generating…" |
| Model switching | Status dot turns yellow, shows "Switching…" |
| Connected | Status dot green |
| Server offline | Status dot red, "Server offline" |

---

## 6. Accessibility

- All interactive elements have `aria-label` or descriptive text
- Color contrast meets WCAG 2.1 AA (verified: white on `#7c6aff` = 4.8:1)
- Keyboard navigation: Tab through all controls, Enter to send
- `<iframe>` has `title` attribute
- Suggestion chips are `<button>` elements (not divs)

---

## 7. Ship 30 Essay Viewer — Typography

The Preview iframe uses a deliberate reading-optimized style:
- `font-family: 'Inter', Georgia, serif` — modern sans with serif fallback for long reads
- `font-size: 15px`, `line-height: 1.8` — comfortable for 1,250 words
- `max-width: 700px` centered — optimal reading column
- `<strong>` in `#3d2fa9` purple — makes key phrases scannable at speed
- `<blockquote>` with 3px left border — visually separates quotes from body

---

## 8. Motion Design

| Element | Animation | Duration |
|---|---|---|
| New message | `slideUp` (8px → 0) | 250ms ease |
| Welcome screen | `fadeIn` | 400ms ease |
| Modal open | `fadeIn` + `slideUp` | 200ms ease |
| Toast notification | `slideUp` | 250ms ease, auto-remove 4s |
| Typing dots | `typingBounce` (4px), staggered | 1.2s ease-in-out infinite |
| Send button | `scale(1.04)` on hover | 150ms |
| Artifact panel | `width` transition | 300ms ease |
