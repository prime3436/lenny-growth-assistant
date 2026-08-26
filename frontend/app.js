/* ─────────────────────────────────────────────────────────────
   Lenny Growth Assistant — Frontend Application Logic
   ───────────────────────────────────────────────────────────── */

const API_BASE = 'http://localhost:8000';

// ── State ─────────────────────────────────────────────────────
const state = {
  sessionId: null,
  activeProvider: 'anthropic',
  activeModel: 'claude-3-5-sonnet-20241022',
  currentArtifact: null,
  artifactPanelOpen: true,
  artifacts: [],
  isLoading: false,
};

// ── DOM refs ──────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const chatInput        = $('chatInput');
const sendBtn          = $('sendBtn');
const messagesList     = $('messagesList');
const welcomeScreen    = $('welcomeScreen');
const artifactPanel    = $('artifactPanel');
const artifactEmpty    = $('artifactEmpty');
const artifactContent  = $('artifactContent');
const artifactTitle    = $('artifactTitle');
const artifactTypeBadge= $('artifactTypeBadge');
const artifactWordCount= $('artifactWordCount');
const artifactIframe   = $('artifactIframe');
const rawContent       = $('rawContent');
const sourcesList      = $('sourcesList');
const sourcesToggle    = $('sourcesToggle');
const sourcesSection   = $('sourcesSection');
const ship30Modal      = $('ship30Modal');
const ship30Topic      = $('ship30Topic');
const statusDot        = $('statusDot');
const statusText       = $('statusText');
const statusModel      = $('statusModel');
const artifactsList    = $('artifactsList');
const toastContainer   = $('toastContainer');

// ── API helpers ───────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Session management ────────────────────────────────────────

async function ensureSession() {
  if (state.sessionId) return;
  const session = await apiFetch('/api/sessions', { method: 'POST', body: JSON.stringify({}) });
  state.sessionId = session.id;
  state.activeProvider = session.model_provider;
  state.activeModel = session.model_name;
}

// ── Health check / status ─────────────────────────────────────

async function checkHealth() {
  try {
    const h = await apiFetch('/health');
    statusDot.className = 'status-dot ok';
    statusText.textContent = 'Connected';
    statusModel.textContent = `${h.llm_provider} · ${h.rag_index_size.toLocaleString()} chunks`;
  } catch {
    statusDot.className = 'status-dot err';
    statusText.textContent = 'Server offline';
    statusModel.textContent = '';
  }
}

// ── Send message (SSE streaming) ─────────────────────────────

async function sendMessage(text) {
  if (!text.trim() || state.isLoading) return;
  state.isLoading = true;
  sendBtn.disabled = true;

  try {
    await ensureSession();
    hideWelcome();
    appendMessage('user', text);
    chatInput.value = '';
    autoResize(chatInput);

    // Create streaming message bubble
    const { bubble, sourcesContainer } = appendStreamingMessage();
    let fullText = '';

    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        message: text,
        model_provider: state.activeProvider,
        model_name: state.activeModel,
        stream: true,
      }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Stream failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.token) {
            fullText += data.token;
            bubble.innerHTML = formatMarkdown(fullText) + '<span class="cursor-blink">▊</span>';
            scrollToBottom();
          } else if (data.error) {
            bubble.innerHTML = `⚠️ ${escHtml(data.error)}`;
          } else if (data.done) {
            // Remove cursor, render final
            bubble.innerHTML = formatMarkdown(fullText);
            // Show sources
            if (data.sources && data.sources.length > 0) {
              sourcesContainer.innerHTML = data.sources.map(s =>
                `<span class="source-chip" title="${escHtml((s.chunk_text || '').slice(0, 120))}">
                  ${escHtml((s.episode_title || '').slice(0, 40))}${s.guest ? ` · ${escHtml(s.guest)}` : ''}
                </span>`
              ).join('');
            }
          }
        } catch { /* skip malformed lines */ }
      }
    }

    scrollToBottom();
  } catch (err) {
    appendMessage('assistant', `⚠️ Error: ${err.message}`);
    showToast(err.message, 'error');
  } finally {
    state.isLoading = false;
    sendBtn.disabled = false;
  }
}

function appendStreamingMessage() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  const sourcesContainer = document.createElement('div');
  sourcesContainer.className = 'message-sources';
  div.innerHTML = `
    <div class="message-avatar">L</div>
    <div class="message-content">
      <div class="message-bubble" id="streamBubble"></div>
    </div>`;
  div.querySelector('.message-content').appendChild(sourcesContainer);
  messagesList.appendChild(div);
  scrollToBottom();
  const bubble = div.querySelector('#streamBubble');
  bubble.removeAttribute('id');
  return { bubble, sourcesContainer };
}

// ── Message rendering ─────────────────────────────────────────

function hideWelcome() {
  welcomeScreen.style.display = 'none';
}

function appendMessage(role, content, sources = []) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const initials = role === 'user' ? 'U' : 'L';
  const formattedContent = formatMarkdown(content);

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `<div class="message-sources">${
      sources.map(s =>
        `<span class="source-chip" title="${escHtml(s.chunk_text.slice(0, 120))}…">
          ${escHtml(s.episode_title.slice(0, 40))}${s.guest ? ` · ${escHtml(s.guest)}` : ''}
        </span>`
      ).join('')
    }</div>`;
  }

  div.innerHTML = `
    <div class="message-avatar">${initials}</div>
    <div class="message-content">
      <div class="message-bubble">${formattedContent}${sourcesHtml}</div>
    </div>`;

  messagesList.appendChild(div);
  scrollToBottom();
  return div;
}

function appendTyping() {
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typingIndicator';
  div.innerHTML = `
    <div class="message-avatar">L</div>
    <div class="message-content">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>`;
  messagesList.appendChild(div);
  scrollToBottom();
  return div;
}

function removeTyping() {
  const el = $('typingIndicator');
  if (el) el.remove();
}

function scrollToBottom() {
  const container = $('messagesContainer');
  container.scrollTop = container.scrollHeight;
}

// ── Simple markdown formatter ─────────────────────────────────

function formatMarkdown(text) {
  let html = escHtml(text);
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Paragraphs
  html = html.split('\n\n').map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
  return html;
}

function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Artifact generation ───────────────────────────────────────

async function generateArtifact(topic, type = 'ship30') {
  if (state.isLoading) return;
  state.isLoading = true;

  showToast('Generating essay… this may take 15-30s', 'info');

  try {
    await ensureSession();
    hideWelcome();

    // Show loading state in artifact panel
    showArtifactLoading(topic, type);

    const artifact = await apiFetch('/api/artifacts/generate', {
      method: 'POST',
      body: JSON.stringify({
        session_id: state.sessionId,
        topic,
        artifact_type: type,
        model_provider: state.activeProvider,
        model_name: state.activeModel,
      }),
    });

    state.currentArtifact = artifact;
    state.artifacts.unshift(artifact);
    renderArtifact(artifact);
    updateArtifactsSidebar();

    // Open panel if hidden
    if (!state.artifactPanelOpen) toggleArtifactPanel();

    // Add a chat message to confirm
    appendMessage('assistant',
      `✅ I've generated a Ship 30 for 30 essay: **${artifact.title}**\n\nYou can view it in the artifact panel →`,
      artifact.sources
    );

    showToast('Essay generated!', 'success');
  } catch (err) {
    clearArtifactLoading();
    showToast(`Generation failed: ${err.message}`, 'error');
    appendMessage('assistant', `⚠️ Could not generate artifact: ${err.message}`);
  } finally {
    state.isLoading = false;
  }
}

function showArtifactLoading(topic, type) {
  artifactEmpty.style.display = 'none';
  artifactContent.style.display = 'flex';
  artifactTitle.textContent = topic;
  artifactTypeBadge.textContent = type === 'ship30' ? 'Ship 30' : type;
  artifactWordCount.textContent = 'Generating…';
  setIframeContent('<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:Inter,sans-serif;color:#666;gap:12px;"><div style="width:20px;height:20px;border:2px solid #ddd;border-top:2px solid #7c6aff;border-radius:50%;animation:spin 0.7s linear infinite"></div>Generating your essay…</div><style>@keyframes spin{to{transform:rotate(360deg)}}</style>');
}

function clearArtifactLoading() {
  artifactEmpty.style.display = 'flex';
  artifactContent.style.display = 'none';
}

function renderArtifact(artifact) {
  artifactEmpty.style.display = 'none';
  artifactContent.style.display = 'flex';

  artifactTitle.textContent = artifact.title;
  artifactTypeBadge.textContent = artifact.artifact_type === 'ship30' ? 'Ship 30' : artifact.artifact_type;
  artifactWordCount.textContent = `${artifact.word_count.toLocaleString()} words`;

  // Iframe: inject sanitized HTML with styling
  const styledHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
      <style>
        body { font-family: 'Inter', Georgia, serif; color: #1a1a2e; max-width: 700px; margin: 0 auto; padding: 28px 32px 48px; font-size: 15px; line-height: 1.8; }
        h1,h2,h3 { color: #0f0e17; font-weight: 600; }
        h2 { font-size: 17px; margin: 28px 0 10px; }
        p  { margin: 0 0 16px; }
        strong { color: #3d2fa9; }
        blockquote { border-left: 3px solid #7c6aff; margin: 20px 0; padding: 8px 16px; color: #444; font-style: italic; }
        ul,ol { padding-left: 20px; margin: 0 0 16px; }
        li { margin-bottom: 6px; }
        code { background: #f0f0f8; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
      </style>
    </head>
    <body>${artifact.sanitized_html || ''}</body>
    </html>`;

  setIframeContent(styledHtml);
  rawContent.textContent = artifact.content;

  // Sources
  if (artifact.sources && artifact.sources.length > 0) {
    sourcesSection.style.display = 'block';
    sourcesList.innerHTML = artifact.sources.map(s => `
      <div class="source-item">
        <div class="source-item-title">${escHtml(s.episode_title)}</div>
        <div class="source-item-meta">${s.guest ? escHtml(s.guest) : ''}${s.episode_number ? ` · Ep #${s.episode_number}` : ''}</div>
        <div class="source-item-text">${escHtml(s.chunk_text.slice(0, 160))}…</div>
        <div class="source-item-score">Relevance: ${s.score.toFixed(2)}</div>
      </div>`).join('');
  } else {
    sourcesSection.style.display = 'none';
  }
}

function setIframeContent(html) {
  const doc = artifactIframe.contentDocument || artifactIframe.contentWindow.document;
  doc.open();
  doc.write(html);
  doc.close();
}

// ── Artifact sidebar ──────────────────────────────────────────

function updateArtifactsSidebar() {
  if (state.artifacts.length === 0) {
    artifactsList.innerHTML = '<div class="empty-state-mini">No artifacts yet</div>';
    return;
  }
  artifactsList.innerHTML = state.artifacts.map((a, i) => `
    <div class="artifact-item ${i === 0 ? 'active' : ''}"
         data-index="${i}"
         title="${escHtml(a.title)}">
      ${escHtml(a.title.slice(0, 45))}${a.title.length > 45 ? '…' : ''}
    </div>`).join('');

  artifactsList.querySelectorAll('.artifact-item').forEach(el => {
    el.addEventListener('click', () => {
      const idx = parseInt(el.dataset.index);
      state.currentArtifact = state.artifacts[idx];
      renderArtifact(state.currentArtifact);
      if (!state.artifactPanelOpen) toggleArtifactPanel();
      artifactsList.querySelectorAll('.artifact-item').forEach(e => e.classList.remove('active'));
      el.classList.add('active');
    });
  });
}

// ── Toggle artifact panel ─────────────────────────────────────

function toggleArtifactPanel() {
  state.artifactPanelOpen = !state.artifactPanelOpen;
  artifactPanel.classList.toggle('hidden', !state.artifactPanelOpen);
}

// ── Model switching ───────────────────────────────────────────

async function switchModel(provider, model) {
  state.activeProvider = provider;
  state.activeModel = model;

  // Update UI
  document.querySelectorAll('.model-option').forEach(el => {
    el.classList.toggle('active', el.dataset.provider === provider && el.dataset.model === model);
  });

  // Update status
  statusDot.className = 'status-dot warn';
  statusText.textContent = `Switching to ${provider}…`;

  try {
    const res = await apiFetch('/api/models/switch', {
      method: 'POST',
      body: JSON.stringify({ provider, model_name: model }),
    });

    if (res.status === 'ok' || res.status === 'warning') {
      statusDot.className = 'status-dot ok';
      statusText.textContent = 'Model switched';
      statusModel.textContent = `${provider} · ${model}`;
      showToast(`Switched to ${model}`, 'success');
    } else {
      showToast(`Switch warning: ${res.message}`, 'warning');
      statusDot.className = 'status-dot warn';
    }
  } catch (err) {
    showToast(`Could not switch: ${err.message}`, 'error');
    statusDot.className = 'status-dot err';
    statusText.textContent = 'Switch failed';
  }
}

// ── Tab switching ─────────────────────────────────────────────

function switchTab(tab) {
  const isPreview = tab === 'preview';
  $('tabPreview').classList.toggle('active', isPreview);
  $('tabRaw').classList.toggle('active', !isPreview);
  $('panePreview').style.display = isPreview ? 'block' : 'none';
  $('paneRaw').style.display    = isPreview ? 'none'  : 'block';
}

// ── Toast notifications ───────────────────────────────────────

function showToast(message, type = 'info') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${escHtml(message)}</span>`;
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Auto-resize textarea ──────────────────────────────────────

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

// ── Event listeners ───────────────────────────────────────────

// Send on Enter (Shift+Enter for newline)
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(chatInput.value);
  }
});

chatInput.addEventListener('input', () => autoResize(chatInput));

sendBtn.addEventListener('click', () => sendMessage(chatInput.value));

// Suggestion chips
document.querySelectorAll('.suggestion-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    chatInput.value = btn.dataset.query;
    autoResize(chatInput);
    sendMessage(btn.dataset.query);
  });
});

// Ship30 button
$('ship30Btn').addEventListener('click', () => {
  ship30Topic.value = chatInput.value.trim() || '';
  ship30Modal.style.display = 'flex';
  setTimeout(() => ship30Topic.focus(), 100);
});

$('generateDemoBtn').addEventListener('click', () => {
  ship30Modal.style.display = 'flex';
  ship30Topic.value = 'Why most startups die before finding product-market fit';
  setTimeout(() => ship30Topic.focus(), 100);
});

// Ship30 modal
$('confirmShip30').addEventListener('click', async () => {
  const topic = ship30Topic.value.trim();
  if (!topic) { ship30Topic.focus(); return; }
  ship30Modal.style.display = 'none';
  await generateArtifact(topic, 'ship30');
});

$('cancelShip30').addEventListener('click', () => { ship30Modal.style.display = 'none'; });
$('closeShip30Modal').addEventListener('click', () => { ship30Modal.style.display = 'none'; });

ship30Topic.addEventListener('keydown', e => {
  if (e.key === 'Enter') $('confirmShip30').click();
  if (e.key === 'Escape') $('closeShip30Modal').click();
});

// Toggle artifact panel
$('toggleArtifactBtn').addEventListener('click', toggleArtifactPanel);

// Model selector
document.querySelectorAll('.model-option').forEach(opt => {
  opt.addEventListener('click', () => {
    switchModel(opt.dataset.provider, opt.dataset.model);
  });
});

// Tab switching
$('tabPreview').addEventListener('click', () => switchTab('preview'));
$('tabRaw').addEventListener('click', () => switchTab('raw'));

// Sources toggle
sourcesToggle.addEventListener('click', () => {
  const open = sourcesList.classList.toggle('open');
  sourcesToggle.classList.toggle('open', open);
});

// Copy artifact
$('copyArtifactBtn').addEventListener('click', () => {
  if (!state.currentArtifact) return;
  navigator.clipboard.writeText(state.currentArtifact.content)
    .then(() => showToast('Copied to clipboard!', 'success'))
    .catch(() => showToast('Copy failed', 'error'));
});

// Export artifact as markdown file
$('exportArtifactBtn').addEventListener('click', () => {
  if (!state.currentArtifact) return;
  const filename = state.currentArtifact.title
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 60) + '.md';
  const blob = new Blob([state.currentArtifact.content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  showToast(`Downloaded ${filename}`, 'success');
});

// Sidebar toggle
$('sidebarToggle').addEventListener('click', () => {
  $('sidebar').classList.toggle('collapsed');
});

// New chat
$('newChatBtn').addEventListener('click', () => {
  state.sessionId = null;
  messagesList.innerHTML = '';
  welcomeScreen.style.display = 'flex';
  chatInput.value = '';
  showToast('New conversation started', 'info');
});

// Modal backdrop close
ship30Modal.addEventListener('click', e => {
  if (e.target === ship30Modal) ship30Modal.style.display = 'none';
});

// ── Init ──────────────────────────────────────────────────────

(async function init() {
  // Check server health
  await checkHealth();

  // Poll health every 30s
  setInterval(checkHealth, 30_000);

  // Focus input
  chatInput.focus();

  console.log('%c🎙️ Lenny Growth Assistant', 'font-size:16px;font-weight:bold;color:#7c6aff');
  console.log('%cAPI:', 'font-weight:bold', API_BASE);
})();
