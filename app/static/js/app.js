/**
 * The Lenny Growth Assistant — Client Application Logic
 * Pure modern ES modules. Runs in any browser without build tooling.
 * 
 * SECURITY: All dynamic content injected via .textContent or explicit DOM methods.
 *           Never .innerHTML on user/LLM-derived strings except after explicit escaping.
 */

'use strict';

let currentSessionId = null;
let currentArtifact = null;
let isProcessing = false;
// Memoize formatted markdown to avoid re-running regex on the same content (P5)
const _markdownCache = new Map();

// DOM Elements
const sessionListEl = document.getElementById("sessionList");
const newSessionBtn = document.getElementById("newSessionBtn");
const chatMessagesEl = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const providerSelector = document.getElementById("providerSelector");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const promptSuggestionsEl = document.getElementById("promptSuggestions");
const openArtifactBtn = document.getElementById("openArtifactBtn");

// Artifact Studio Elements
const artifactStudio = document.getElementById("artifactStudio");
const artifactTitle = document.getElementById("artifactTitle");
const artifactIframe = document.getElementById("artifactIframe");
const artifactMarkdown = document.getElementById("artifactMarkdown");
const emptyArtifact = document.getElementById("emptyArtifact");
const tabRendered = document.getElementById("tabRendered");
const tabSource = document.getElementById("tabSource");
const tabClose = document.getElementById("tabClose");

// Initialize application
async function initApp() {
  bindEvents();
  await checkHealth();
  await loadSessions();
  if (!currentSessionId) {
    await createNewSession();
  }
}

function bindEvents() {
  newSessionBtn.addEventListener("click", createNewSession);

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSendMessage();
  });

  // Auto-resize textarea as user types (U1)
  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
  });

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Prompt suggestions — dismissed after first send (U3)
  document.querySelectorAll(".prompt-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const prompt = pill.getAttribute("data-prompt");
      if (prompt) {
        messageInput.value = prompt;
        messageInput.dispatchEvent(new Event("input")); // Trigger resize
        handleSendMessage();
      }
    });
  });

  // Artifact tabs
  tabRendered.addEventListener("click", () => showArtifactView("rendered"));
  tabSource.addEventListener("click", () => showArtifactView("source"));
  tabClose.addEventListener("click", () => {
    artifactStudio.classList.add("collapsed");
  });

  // Reopen artifact panel if one is loaded (U4)
  if (openArtifactBtn) {
    openArtifactBtn.addEventListener("click", () => {
      if (currentArtifact) {
        artifactStudio.classList.remove("collapsed");
      }
    });
  }
}

// Health & System Observability
async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("Health check degraded");
    const data = await res.json();
    statusDot.className = "status-dot " + (data.status === "healthy" ? "" : "degraded");
    // Use safe DOM text assignments — not string interpolation into innerHTML
    statusText.textContent = `DB: ${data.database} | LLM: ${data.active_provider}`;
    providerSelector.value = data.active_provider;
  } catch {
    statusDot.className = "status-dot degraded";
    statusText.textContent = "System: Degraded / Offline";
  }
}

// Sessions — P1: No longer reloads full session list on every click
async function loadSessions() {
  try {
    const res = await fetch("/sessions");
    if (!res.ok) return;
    const sessions = await res.json();
    renderSessionList(sessions);
    // Auto-select first session if none active
    if (!currentSessionId && sessions.length > 0) {
      currentSessionId = sessions[0].id;
    }
  } catch (err) {
    console.error("Failed to load sessions:", err);
  }
}

function renderSessionList(sessions) {
  sessionListEl.innerHTML = "";
  sessions.forEach(s => {
    const item = document.createElement("div");
    item.className = "session-item " + (s.id === currentSessionId ? "active" : "");
    item.setAttribute("role", "option"); // U5: accessibility
    item.setAttribute("aria-selected", s.id === currentSessionId ? "true" : "false");
    item.tabIndex = 0;
    item.onclick = () => selectSession(s.id);
    item.onkeydown = (e) => { if (e.key === "Enter") selectSession(s.id); };

    const title = document.createElement("div");
    title.className = "session-title";
    title.textContent = s.user_metadata?.title || "Growth Conversation"; // Safe: textContent

    const meta = document.createElement("div");
    meta.className = "session-meta";
    const date = s.updated_at
      ? new Date(s.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = `${s.active_provider} · ${date}`; // Safe: textContent

    item.appendChild(title);
    item.appendChild(meta);
    sessionListEl.appendChild(item);
  });
}

async function createNewSession() {
  try {
    const res = await fetch("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_metadata: { title: "New Conversation" },
        active_provider: providerSelector.value
      })
    });
    if (!res.ok) throw new Error("Failed to create session");
    const newSession = await res.json();
    currentSessionId = newSession.id;
    await loadSessions();
    chatMessagesEl.innerHTML = "";
    renderWelcomeState();
  } catch (err) {
    renderSystemError("Could not start new session: " + escapeHtml(err.message));
  }
}

async function selectSession(sessionId) {
  if (currentSessionId === sessionId) return; // P1: Skip reload if already active
  currentSessionId = sessionId;
  chatMessagesEl.innerHTML = "";

  // Update active class without full re-render
  document.querySelectorAll(".session-item").forEach(el => {
    el.classList.remove("active");
    el.setAttribute("aria-selected", "false");
  });
  const targetItem = [...document.querySelectorAll(".session-item")].find(el =>
    el.querySelector(".session-meta")?.textContent
  );

  try {
    const res = await fetch(`/sessions/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();

    await loadSessions(); // Refresh after select (updating active highlights)

    if (data.messages && data.messages.length > 0) {
      // Hide prompt suggestions on sessions with messages (U3 applied on load)
      if (promptSuggestionsEl) promptSuggestionsEl.style.display = "none";
      data.messages.forEach(m => renderMessage(m.role, m.content, m.metadata || {}));
    } else {
      renderWelcomeState();
    }

    if (data.artifacts && data.artifacts.length > 0) {
      await loadArtifact(data.artifacts[0].id);
    }
  } catch (err) {
    console.error("Failed to fetch session messages:", err);
  }
}

function renderWelcomeState() {
  if (promptSuggestionsEl) promptSuggestionsEl.style.display = "flex";
  const div = document.createElement("div");
  div.style.cssText = "text-align: center; margin: 40px auto; max-width: 540px; color: var(--ink-secondary);";

  const h2 = document.createElement("h2");
  h2.style.cssText = "font-family: var(--font-editorial); font-size: 1.4rem; color: var(--ink-primary); margin-bottom: 8px;";
  h2.textContent = "Welcome to The Lenny Growth Assistant";

  const p = document.createElement("p");
  p.style.cssText = "font-size: 0.95rem; line-height: 1.6;";
  p.textContent = "Ask specific questions about product-led growth, retention, pricing, and frameworks. All answers are strictly cited against Lenny's Podcast transcripts.";

  div.appendChild(h2);
  div.appendChild(p);
  chatMessagesEl.appendChild(div);
}

// Messaging
async function handleSendMessage() {
  const content = messageInput.value.trim();
  if (!content || !currentSessionId || isProcessing) return;

  // Hide prompt suggestions after first message (U3)
  if (promptSuggestionsEl) promptSuggestionsEl.style.display = "none";

  isProcessing = true;
  messageInput.value = "";
  messageInput.style.height = "auto";
  setLoadingState(true);

  // Render User Message
  renderMessage("user", content, {});

  // Render Thinking State with animated dots (U2)
  const thinkingId = "thinking-" + Date.now();
  const thinkingRow = document.createElement("div");
  thinkingRow.id = thinkingId;
  thinkingRow.className = "message-row assistant";

  const thinkingLabel = document.createElement("span");
  thinkingLabel.className = "message-label";
  thinkingLabel.textContent = "Assistant";

  const thinkingCard = document.createElement("div");
  thinkingCard.className = "assistant-card thinking-card";
  thinkingCard.innerHTML = '<span class="thinking-dots"><span></span><span></span><span></span></span><span class="thinking-text">Searching transcripts and verifying citations</span>';

  thinkingRow.appendChild(thinkingLabel);
  thinkingRow.appendChild(thinkingCard);
  chatMessagesEl.appendChild(thinkingRow);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

  try {
    const res = await fetch(`/sessions/${currentSessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, provider_override: providerSelector.value })
    });

    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData?.detail?.error?.message || errData?.error?.message || "Failed to process message.";
      renderSystemError(msg); // S2: no longer injects into innerHTML directly
      return;
    }

    const turn = await res.json();
    renderMessage("assistant", turn.assistant_message.content, {
      citations: turn.citations,
      skill_used: turn.skill_used,
      fallback_used: turn.fallback_used,
      provider_used: turn.provider_used
    });

    if (turn.artifact) {
      displayArtifact(turn.artifact);
    }

    // Refresh session list to update timestamps (A4 surfacing in UI)
    await loadSessions();
  } catch (err) {
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();
    renderSystemError("Network or server connection failed."); // S2: no user-derived string injected
  } finally {
    isProcessing = false;
    setLoadingState(false);
    messageInput.focus();
  }
}

function setLoadingState(loading) {
  sendBtn.disabled = loading;
  sendBtn.textContent = loading ? "..." : "Send";
}

function renderMessage(role, content, metadata = {}) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "The Lenny Assistant"; // Safe
  row.appendChild(label);

  if (role === "user") {
    const bubble = document.createElement("div");
    bubble.className = "user-bubble";
    bubble.textContent = content; // S5: textContent, never innerHTML for user input
    row.appendChild(bubble);
  } else {
    const card = document.createElement("div");
    card.className = "assistant-card";

    if (metadata.fallback_used) {
      const banner = document.createElement("div");
      banner.className = "fallback-banner";
      banner.textContent = "[Notice: Primary provider unavailable. Executed via local fallback.]"; // Safe
      card.appendChild(banner);
    }

    const body = document.createElement("div");
    body.innerHTML = formatMarkdownCached(content); // Server-generated text, escaped then formatted
    card.appendChild(body);

    if (metadata.citations && metadata.citations.length > 0) {
      card.appendChild(buildCitations(metadata.citations));
    }

    row.appendChild(card);
  }

  chatMessagesEl.appendChild(row);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function buildCitations(citations) {
  const wrapper = document.createElement("div");
  wrapper.className = "citations-wrapper";

  const titleEl = document.createElement("div");
  titleEl.className = "citations-title";
  titleEl.textContent = `Verified Sources (${citations.length})`; // Safe

  const chips = document.createElement("div");
  chips.className = "citation-chips";

  citations.forEach(c => {
    const chip = document.createElement("a");
    chip.className = "citation-chip";
    chip.href = c.source_url && c.source_url !== "null" ? c.source_url : "#";
    chip.target = "_blank";
    chip.rel = "noopener noreferrer"; // Security: prevent tabnapping
    chip.setAttribute("title", c.content_snippet || "");

    const titleSpan = document.createElement("span");
    titleSpan.textContent = c.episode_title; // S5: textContent, NOT innerHTML

    const scoreSpan = document.createElement("span");
    scoreSpan.className = "citation-chip-score";
    scoreSpan.textContent = `${Math.round(c.similarity_score * 100)}% match`; // Safe

    chip.appendChild(titleSpan);
    chip.appendChild(scoreSpan);
    chips.appendChild(chip);
  });

  wrapper.appendChild(titleEl);
  wrapper.appendChild(chips);
  return wrapper;
}

// S2 fix: renderSystemError never injects raw strings via innerHTML
function renderSystemError(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = "System Notice";

  const badge = document.createElement("div");
  badge.className = "refusal-badge";
  badge.textContent = message; // Safe: textContent only

  row.appendChild(label);
  row.appendChild(badge);
  chatMessagesEl.appendChild(row);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// Artifact Studio
async function loadArtifact(artifactId) {
  try {
    const res = await fetch(`/artifacts/${artifactId}`);
    if (!res.ok) return;
    const data = await res.json();
    displayArtifact(data);
  } catch (err) {
    console.error("Failed to load artifact:", err);
  }
}

function displayArtifact(artifact) {
  currentArtifact = artifact;
  artifactStudio.classList.remove("collapsed");
  emptyArtifact.style.display = "none";
  artifactTitle.textContent = artifact.title || "Generated Artifact"; // Safe
  showArtifactView("rendered");
}

function showArtifactView(viewType) {
  if (!currentArtifact) return;

  tabRendered.className = "studio-tab " + (viewType === "rendered" ? "active" : "");
  tabSource.className = "studio-tab " + (viewType === "source" ? "active" : "");

  if (viewType === "rendered") {
    if (currentArtifact.type === "html") {
      artifactIframe.style.display = "block";
      artifactMarkdown.style.display = "none";
      // ADR-2: srcdoc isolates content inside sandbox; no JS can escape the iframe
      artifactIframe.srcdoc = currentArtifact.content;
    } else {
      artifactIframe.style.display = "none";
      artifactMarkdown.style.display = "block";
      artifactMarkdown.innerHTML = formatMarkdownCached(currentArtifact.content);
    }
  } else {
    artifactIframe.style.display = "none";
    artifactMarkdown.style.display = "block";
    artifactMarkdown.textContent = currentArtifact.content; // Safe: raw source view
  }
}

// P5: Memoized markdown formatter (no redundant re-processing of same content)
function formatMarkdownCached(text) {
  if (!text) return "";
  if (_markdownCache.has(text)) return _markdownCache.get(text);
  const result = formatMarkdownBasic(text);
  if (_markdownCache.size > 50) _markdownCache.clear(); // Bound cache size
  _markdownCache.set(text, result);
  return result;
}

function formatMarkdownBasic(text) {
  // Always HTML-escape first before any further substitution
  let esc = escapeHtml(text);

  esc = esc.replace(/^### (.*$)/gim, '<h3 style="margin:14px 0 6px;">$1</h3>');
  esc = esc.replace(/^## (.*$)/gim, '<h2 style="margin:18px 0 8px;">$1</h2>');
  esc = esc.replace(/^# (.*$)/gim, '<h1 style="margin:22px 0 10px;">$1</h1>');
  esc = esc.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  esc = esc.replace(/\*(.*?)\*/g, "<em>$1</em>");
  esc = esc.replace(/^[-*] (.*$)/gim, "<li>$1</li>");

  return esc.split("\n\n").map(p => {
    if (p.trim().startsWith("<h") || p.trim().startsWith("<li>")) return p;
    return `<p>${p.replace(/\n/g, "<br>")}</p>`;
  }).join("");
}

// XSS-safe HTML escape utility
function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

document.addEventListener("DOMContentLoaded", initApp);
