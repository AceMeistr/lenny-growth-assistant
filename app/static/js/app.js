/**
 * The Lenny Growth Assistant — Client Application Logic
 * Modern Vanilla JS (ES2022). Zero build tooling required.
 * 
 * SECURITY: Dynamic content is set via textContent or sanitizers.
 * No uncontrolled innerHTML on user-provided strings.
 */

'use strict';

// Application State
let currentSessionId = null;
let currentArtifact = null;
let allArtifacts = [];
let isProcessing = false;

// Memoize formatted markdown to prevent redundant regex passes
const _markdownCache = new Map();

// Local Storage Key for External API / Model Configuration
const SETTINGS_KEY = "lenny_growth_assistant_settings_v3";

function getLocalSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? JSON.parse(raw) : {
      provider: "ollama",
      apiKey: "",
      model: "phi3",
      baseUrl: ""
    };
  } catch {
    return { provider: "ollama", apiKey: "", model: "phi3", baseUrl: "" };
  }
}

function saveLocalSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (err) {
    console.warn("Could not persist settings to localStorage:", err);
  }
}

// DOM Elements - Shell & Navigation
const appContainer = document.getElementById("appContainer");
const sidebarTabChats = document.getElementById("sidebarTabChats");
const sidebarTabArtifacts = document.getElementById("sidebarTabArtifacts");
const sessionListEl = document.getElementById("sessionList");
const artifactListEl = document.getElementById("artifactList");
const sessionCountEl = document.getElementById("sessionCount");
const artifactCountEl = document.getElementById("artifactCount");
const newSessionBtn = document.getElementById("newSessionBtn");

// Chat Pane Elements
const chatMessagesEl = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const providerSelector = document.getElementById("providerSelector");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const promptSuggestionsEl = document.getElementById("promptSuggestions");
const openArtifactBtn = document.getElementById("openArtifactBtn");
const openSettingsBtn = document.getElementById("openSettingsBtn");

// Artifact Studio Elements
const artifactStudio = document.getElementById("artifactStudio");
const artifactTitle = document.getElementById("artifactTitle");
const artifactFileSelect = document.getElementById("artifactFileSelect");
const artifactIframe = document.getElementById("artifactIframe");
const artifactMarkdown = document.getElementById("artifactMarkdown");
const artifactRawContainer = document.getElementById("artifactRawContainer");
const artifactRawCode = document.getElementById("artifactRawCode");
const emptyArtifact = document.getElementById("emptyArtifact");
const tabRendered = document.getElementById("tabRendered");
const tabSource = document.getElementById("tabSource");
const btnCopyArtifact = document.getElementById("btnCopyArtifact");
const btnDownloadArtifact = document.getElementById("btnDownloadArtifact");
const btnCloseArtifact = document.getElementById("btnCloseArtifact");

// Settings Modal Elements
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const modalProviderSelect = document.getElementById("modalProviderSelect");
const modalApiKey = document.getElementById("modalApiKey");
const toggleApiKeyVisibility = document.getElementById("toggleApiKeyVisibility");
const modalModelName = document.getElementById("modalModelName");
const modalBaseUrl = document.getElementById("modalBaseUrl");
const connectionStatus = document.getElementById("connectionStatus");
const btnTestConnection = document.getElementById("btnTestConnection");
const btnSaveSettings = document.getElementById("btnSaveSettings");


// Application Boot
async function initApp() {
  bindEvents();
  initSettingsUI();
  await checkHealth();
  await Promise.all([loadSessions(), loadArtifactsList()]);
  if (!currentSessionId) {
    await createNewSession();
  }
}

function bindEvents() {
  // Sidebar Navigation & Tab Switching
  if (sidebarTabChats) {
    sidebarTabChats.addEventListener("click", () => switchSidebarTab("chats"));
  }
  if (sidebarTabArtifacts) {
    sidebarTabArtifacts.addEventListener("click", () => switchSidebarTab("artifacts"));
  }
  if (newSessionBtn) {
    newSessionBtn.addEventListener("click", createNewSession);
  }

  // Chat Form & Input
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSendMessage();
  });

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

  // Prompt suggestion pills
  document.querySelectorAll(".prompt-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const prompt = pill.getAttribute("data-prompt");
      if (prompt) {
        messageInput.value = prompt;
        messageInput.dispatchEvent(new Event("input"));
        handleSendMessage();
      }
    });
  });

  // Artifact Studio Controls
  tabRendered.addEventListener("click", () => showArtifactView("rendered"));
  tabSource.addEventListener("click", () => showArtifactView("source"));
  btnCopyArtifact.addEventListener("click", handleCopyArtifact);
  btnDownloadArtifact.addEventListener("click", handleDownloadArtifact);
  btnCloseArtifact.addEventListener("click", closeActiveArtifact);

  // File Switcher Dropdown in Studio Header
  if (artifactFileSelect) {
    artifactFileSelect.addEventListener("change", (e) => {
      const selectedId = e.target.value;
      if (selectedId) {
        selectArtifact(selectedId);
      }
    });
  }

  // Toggle Artifact Studio
  if (openArtifactBtn) {
    openArtifactBtn.addEventListener("click", () => {
      if (artifactStudio.classList.contains("collapsed")) {
        openStudio();
        if (currentArtifact) {
          showArtifactView("rendered");
        }
      } else {
        closeStudio();
      }
    });
  }

  // Settings Modal
  if (openSettingsBtn) openSettingsBtn.addEventListener("click", openSettings);
  if (closeSettingsBtn) closeSettingsBtn.addEventListener("click", closeSettings);
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) closeSettings();
    });
  }
  if (toggleApiKeyVisibility) {
    toggleApiKeyVisibility.addEventListener("click", () => {
      const isPwd = modalApiKey.type === "password";
      modalApiKey.type = isPwd ? "text" : "password";
      toggleApiKeyVisibility.textContent = isPwd ? "🔒" : "👁";
    });
  }
  if (modalProviderSelect) {
    modalProviderSelect.addEventListener("change", handleProviderChangeInModal);
  }
  if (btnTestConnection) btnTestConnection.addEventListener("click", testModelConnection);
  if (btnSaveSettings) btnSaveSettings.addEventListener("click", applyAndSaveSettings);

  // Live Provider selector in chat header
  if (providerSelector) {
    providerSelector.addEventListener("change", () => {
      const s = getLocalSettings();
      s.provider = providerSelector.value;
      if (s.provider === "ollama" && !s.model) s.model = "phi3";
      if (s.provider === "anthropic" && !s.model) s.model = "claude-3-5-sonnet-20241022";
      if (s.provider === "openai" && !s.model) s.model = "gpt-4o-mini";
      saveLocalSettings(s);
    });
  }
}

// Sidebar Tab Switcher (Conversations vs Artifacts)
function switchSidebarTab(tab) {
  if (tab === "chats") {
    sidebarTabChats.classList.add("active");
    sidebarTabArtifacts.classList.remove("active");
    sessionListEl.style.display = "flex";
    artifactListEl.style.display = "none";
  } else {
    sidebarTabChats.classList.remove("active");
    sidebarTabArtifacts.classList.add("active");
    sessionListEl.style.display = "none";
    artifactListEl.style.display = "flex";
  }
}

// Health Observability
async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("Health check degraded");
    const data = await res.json();
    statusDot.className = "status-dot " + (data.status === "healthy" ? "" : "degraded");
    statusText.textContent = `DB: ${data.database} | LLM: ${data.active_provider}`;
    
    const saved = getLocalSettings();
    providerSelector.value = saved.provider || data.active_provider;
  } catch {
    statusDot.className = "status-dot degraded";
    statusText.textContent = "System: Degraded / Offline";
  }
}

// Session Lifecycle
async function loadSessions() {
  try {
    const res = await fetch("/sessions");
    if (!res.ok) return;
    const sessions = await res.json();
    if (sessionCountEl) sessionCountEl.textContent = sessions.length;
    renderSessionList(sessions);
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
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", s.id === currentSessionId ? "true" : "false");
    item.tabIndex = 0;

    item.onclick = (e) => {
      if (e.target.closest(".session-delete-btn")) return;
      selectSession(s.id);
    };
    item.onkeydown = (e) => {
      if (e.key === "Enter") selectSession(s.id);
    };

    const title = document.createElement("div");
    title.className = "session-title";
    title.textContent = s.user_metadata?.title || "Growth Conversation";

    const meta = document.createElement("div");
    meta.className = "session-meta";
    const date = s.updated_at
      ? new Date(s.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";
    meta.textContent = `${s.active_provider} · ${date}`;

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "session-delete-btn";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.title = "Delete conversation";
    deleteBtn.setAttribute("aria-label", "Delete conversation");
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      deleteSession(s.id);
    };

    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(deleteBtn);
    sessionListEl.appendChild(item);
  });
}

async function createNewSession() {
  try {
    const saved = getLocalSettings();
    const res = await fetch("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_metadata: { title: "New Conversation" },
        active_provider: saved.provider || providerSelector.value
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

async function deleteSession(sessionId) {
  if (!sessionId) return;
  try {
    const res = await fetch(`/sessions/${sessionId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete session");

    if (currentSessionId === sessionId) {
      currentSessionId = null;
      chatMessagesEl.innerHTML = "";
    }

    const sessionsRes = await fetch("/sessions");
    const sessions = sessionsRes.ok ? await sessionsRes.json() : [];
    renderSessionList(sessions);
    if (sessionCountEl) sessionCountEl.textContent = sessions.length;

    // Refresh artifacts in case session's artifacts were deleted
    await loadArtifactsList();

    if (!currentSessionId) {
      if (sessions.length > 0) {
        await selectSession(sessions[0].id);
      } else {
        await createNewSession();
      }
    }
  } catch (err) {
    console.error("Error deleting session:", err);
  }
}

async function selectSession(sessionId) {
  if (currentSessionId === sessionId) return;
  currentSessionId = sessionId;
  chatMessagesEl.innerHTML = "";

  document.querySelectorAll(".session-item").forEach(el => {
    el.classList.remove("active");
    el.setAttribute("aria-selected", "false");
  });

  try {
    const res = await fetch(`/sessions/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();

    await loadSessions();

    if (data.messages && data.messages.length > 0) {
      if (promptSuggestionsEl) promptSuggestionsEl.style.display = "none";
      data.messages.forEach(m => {
        renderMessage(m.role, m.content, m.metadata || {});
      });
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
  const existing = document.getElementById("welcomeBanner");
  if (existing) existing.remove();

  if (promptSuggestionsEl) promptSuggestionsEl.style.display = "flex";

  const div = document.createElement("div");
  div.id = "welcomeBanner";
  div.className = "welcome-banner";

  const h2 = document.createElement("h2");
  h2.className = "welcome-title";
  h2.textContent = "Welcome to The Lenny Growth Assistant";

  const p = document.createElement("p");
  p.className = "welcome-desc";
  p.textContent = "Ask specific questions about product-led growth, retention, pricing, and frameworks. All answers are strictly cited against Lenny's Podcast transcripts.";

  div.appendChild(h2);
  div.appendChild(p);
  chatMessagesEl.appendChild(div);
}

// Artifact Library Management (Multiple Files Selection)
async function loadArtifactsList() {
  try {
    const res = await fetch("/artifacts");
    if (!res.ok) return;
    allArtifacts = await res.json();
    if (artifactCountEl) artifactCountEl.textContent = allArtifacts.length;
    renderArtifactFilesList(allArtifacts);
    populateArtifactSelectDropdown(allArtifacts);
  } catch (err) {
    console.error("Failed to load artifacts library:", err);
  }
}

function renderArtifactFilesList(artifacts) {
  if (!artifactListEl) return;
  artifactListEl.innerHTML = "";

  if (artifacts.length === 0) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding: 24px 16px; text-align: center; color: var(--ink-muted); font-size: 0.8rem;";
    empty.textContent = "No generated artifacts yet. Ask for a table, essay, or HTML snippet!";
    artifactListEl.appendChild(empty);
    return;
  }

  artifacts.forEach(a => {
    const item = document.createElement("div");
    const isSelected = currentArtifact && currentArtifact.id === a.id;
    item.className = "artifact-file-item " + (isSelected ? "active" : "");
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", isSelected ? "true" : "false");
    item.tabIndex = 0;

    item.onclick = (e) => {
      if (e.target.closest(".session-delete-btn")) return;
      selectArtifact(a.id);
    };

    const title = document.createElement("div");
    title.className = "artifact-file-title";
    title.textContent = a.title || "Generated Artifact";

    const meta = document.createElement("div");
    meta.className = "artifact-file-meta";

    const badge = document.createElement("span");
    badge.className = `file-badge ${a.type}`;
    badge.textContent = a.type.toUpperCase();

    const date = a.created_at
      ? new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";

    const dateSpan = document.createElement("span");
    dateSpan.textContent = date;

    meta.appendChild(badge);
    meta.appendChild(dateSpan);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "session-delete-btn";
    deleteBtn.innerHTML = "&times;";
    deleteBtn.title = "Delete artifact file";
    deleteBtn.setAttribute("aria-label", "Delete artifact file");
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      deleteArtifactFile(a.id);
    };

    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(deleteBtn);
    artifactListEl.appendChild(item);
  });
}

function populateArtifactSelectDropdown(artifacts) {
  if (!artifactFileSelect) return;
  artifactFileSelect.innerHTML = "";

  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = artifacts.length > 0
    ? `-- Switch Artifact File (${artifacts.length}) --`
    : "-- No Artifacts Generated --";
  artifactFileSelect.appendChild(defaultOpt);

  artifacts.forEach(a => {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = `[${a.type.toUpperCase()}] ${a.title || "Artifact"}`;
    if (currentArtifact && currentArtifact.id === a.id) {
      opt.selected = true;
    }
    artifactFileSelect.appendChild(opt);
  });
}

async function selectArtifact(artifactId) {
  if (!artifactId) return;
  try {
    const res = await fetch(`/artifacts/${artifactId}`);
    if (!res.ok) return;
    const artifact = await res.json();
    displayArtifact(artifact);
  } catch (err) {
    console.error("Failed to select artifact:", err);
  }
}

async function deleteArtifactFile(artifactId) {
  if (!artifactId) return;
  try {
    const res = await fetch(`/artifacts/${artifactId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete artifact");

    if (currentArtifact && currentArtifact.id === artifactId) {
      closeActiveArtifact();
    }
    await loadArtifactsList();
  } catch (err) {
    console.error("Error deleting artifact file:", err);
  }
}

// Messaging Flow
async function handleSendMessage() {
  const content = messageInput.value.trim();
  if (!content || !currentSessionId || isProcessing) return;

  const welcome = document.getElementById("welcomeBanner");
  if (welcome) welcome.remove();

  if (promptSuggestionsEl) promptSuggestionsEl.style.display = "none";

  isProcessing = true;
  messageInput.value = "";
  messageInput.style.height = "auto";
  setLoadingState(true);

  renderMessage("user", content, {});

  const thinkingId = "thinking-" + Date.now();
  const thinkingRow = document.createElement("div");
  thinkingRow.id = thinkingId;
  thinkingRow.className = "message-row assistant";

  const thinkingLabel = document.createElement("span");
  thinkingLabel.className = "message-label";
  thinkingLabel.textContent = "The Lenny Assistant";

  const thinkingCard = document.createElement("div");
  thinkingCard.className = "assistant-card thinking-card";
  thinkingCard.innerHTML = '<span class="thinking-dots"><span></span><span></span><span></span></span><span class="thinking-text">Searching transcripts and synthesizing grounded response...</span>';

  thinkingRow.appendChild(thinkingLabel);
  thinkingRow.appendChild(thinkingCard);
  chatMessagesEl.appendChild(thinkingRow);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;

  const saved = getLocalSettings();
  const activeProvider = providerSelector.value || saved.provider;

  const payload = {
    content,
    provider_override: activeProvider,
    api_key_override: saved.apiKey || null,
    model_override: saved.model || null,
    base_url_override: saved.baseUrl || null
  };

  try {
    const res = await fetch(`/sessions/${currentSessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData?.detail?.error?.message || errData?.error?.message || "Failed to process message.";
      renderSystemError(msg);
      return;
    }

    const turn = await res.json();
    renderMessage("assistant", turn.assistant_message.content, {
      citations: turn.citations,
      skill_used: turn.skill_used,
      fallback_used: turn.fallback_used,
      provider_used: turn.provider_used,
      artifact: turn.artifact
    });

    if (turn.artifact) {
      displayArtifact(turn.artifact);
      await loadArtifactsList(); // Refresh artifacts library immediately
    }

    await loadSessions();
  } catch (err) {
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();
    renderSystemError("Network or server connection failed.");
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
  const welcome = document.getElementById("welcomeBanner");
  if (welcome) welcome.remove();

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "The Lenny Assistant";
  row.appendChild(label);

  if (role === "user") {
    const bubble = document.createElement("div");
    bubble.className = "user-bubble";
    bubble.textContent = content;
    row.appendChild(bubble);
  } else {
    const card = document.createElement("div");
    card.className = "assistant-card";

    if (metadata.fallback_used) {
      const banner = document.createElement("div");
      banner.className = "fallback-banner";
      banner.textContent = "[Notice: Primary provider unavailable. Executed via local fallback.]";
      card.appendChild(banner);
    }

    const body = document.createElement("div");
    body.innerHTML = formatMarkdownCached(content);
    card.appendChild(body);

    if (metadata.citations && metadata.citations.length > 0) {
      card.appendChild(buildCitations(metadata.citations));
    }

    if (metadata.artifact) {
      const artPill = document.createElement("button");
      artPill.className = "artifact-open-pill";
      artPill.innerHTML = `<span>📄 Open in Studio:</span> <strong>${escapeHtml(metadata.artifact.title || "Artifact")}</strong> &rarr;`;
      artPill.onclick = () => {
        displayArtifact(metadata.artifact);
      };
      card.appendChild(artPill);
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
  titleEl.textContent = `Verified Sources (${citations.length})`;

  const chips = document.createElement("div");
  chips.className = "citation-chips";

  citations.forEach(c => {
    const chip = document.createElement("a");
    chip.className = "citation-chip";
    chip.href = c.source_url && c.source_url !== "null" ? c.source_url : "#";
    chip.target = "_blank";
    chip.rel = "noopener noreferrer";
    chip.setAttribute("title", c.content_snippet || "");

    const titleSpan = document.createElement("span");
    titleSpan.textContent = c.episode_title;

    const scoreSpan = document.createElement("span");
    scoreSpan.className = "citation-chip-score";
    scoreSpan.textContent = `${Math.round(c.similarity_score * 100)}% match`;

    chip.appendChild(titleSpan);
    chip.appendChild(scoreSpan);
    chips.appendChild(chip);
  });

  wrapper.appendChild(titleEl);
  wrapper.appendChild(chips);
  return wrapper;
}

function renderSystemError(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = "System Notice";

  const badge = document.createElement("div");
  badge.className = "refusal-badge";
  badge.textContent = message;

  row.appendChild(label);
  row.appendChild(badge);
  chatMessagesEl.appendChild(row);
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

// Artifact Studio Functions
function openStudio() {
  artifactStudio.classList.remove("collapsed");
  if (appContainer) appContainer.classList.remove("studio-collapsed");
}

function closeStudio() {
  artifactStudio.classList.add("collapsed");
  if (appContainer) appContainer.classList.add("studio-collapsed");
}

// Close Artifact: clears active artifact, resets controls, and collapses panel
function closeActiveArtifact() {
  currentArtifact = null;
  artifactTitle.textContent = "Artifact Studio";
  if (artifactFileSelect) artifactFileSelect.value = "";
  emptyArtifact.style.display = "flex";
  artifactIframe.style.display = "none";
  artifactMarkdown.style.display = "none";
  artifactRawContainer.style.display = "none";

  // Deselect active state in sidebar list
  document.querySelectorAll(".artifact-file-item").forEach(el => {
    el.classList.remove("active");
    el.setAttribute("aria-selected", "false");
  });

  closeStudio();
}

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
  openStudio();
  emptyArtifact.style.display = "none";
  artifactTitle.textContent = artifact.title || "Generated Artifact";

  // Synchronize dropdown selection
  if (artifactFileSelect) {
    artifactFileSelect.value = artifact.id || "";
  }

  // Synchronize sidebar artifacts list highlight
  document.querySelectorAll(".artifact-file-item").forEach(el => {
    el.classList.remove("active");
    el.setAttribute("aria-selected", "false");
  });
  const activeEl = [...document.querySelectorAll(".artifact-file-item")].find(el =>
    el.querySelector(".artifact-file-title")?.textContent === artifact.title
  );
  if (activeEl) {
    activeEl.classList.add("active");
    activeEl.setAttribute("aria-selected", "true");
  }

  showArtifactView("rendered");
}

function showArtifactView(viewType) {
  tabRendered.className = "studio-tab " + (viewType === "rendered" ? "active" : "");
  tabSource.className = "studio-tab " + (viewType === "source" ? "active" : "");

  if (!currentArtifact) {
    emptyArtifact.style.display = "flex";
    artifactIframe.style.display = "none";
    artifactMarkdown.style.display = "none";
    artifactRawContainer.style.display = "none";
    return;
  }

  emptyArtifact.style.display = "none";

  if (viewType === "rendered") {
    artifactRawContainer.style.display = "none";
    if (currentArtifact.type === "html") {
      artifactIframe.style.display = "block";
      artifactMarkdown.style.display = "none";
      artifactIframe.srcdoc = currentArtifact.content;
    } else {
      artifactIframe.style.display = "none";
      artifactMarkdown.style.display = "block";
      artifactMarkdown.innerHTML = formatMarkdownCached(currentArtifact.content);
    }
  } else {
    // Raw source code view
    artifactIframe.style.display = "none";
    artifactMarkdown.style.display = "none";
    artifactRawContainer.style.display = "block";
    artifactRawCode.textContent = currentArtifact.content;
  }
}

function handleCopyArtifact() {
  if (!currentArtifact || !currentArtifact.content) return;
  navigator.clipboard.writeText(currentArtifact.content).then(() => {
    const originalText = btnCopyArtifact.innerHTML;
    btnCopyArtifact.innerHTML = "<span>✓</span> Copied!";
    btnCopyArtifact.style.color = "#059669";
    setTimeout(() => {
      btnCopyArtifact.innerHTML = originalText;
      btnCopyArtifact.style.color = "";
    }, 2000);
  }).catch(err => {
    console.error("Clipboard copy failed:", err);
  });
}

function handleDownloadArtifact() {
  if (!currentArtifact || !currentArtifact.content) return;

  const isHtml = currentArtifact.type === "html";
  const extension = isHtml ? "html" : "md";
  const mimeType = isHtml ? "text/html;charset=utf-8" : "text/markdown;charset=utf-8";

  const safeTitle = (currentArtifact.title || "artifact")
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, "_")
    .replace(/_+/g, "_")
    .slice(0, 40);

  const filename = `${safeTitle}.${extension}`;
  const blob = new Blob([currentArtifact.content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// External Model & API Settings Modal
function initSettingsUI() {
  const saved = getLocalSettings();
  if (modalProviderSelect) modalProviderSelect.value = saved.provider || "ollama";
  if (modalApiKey) modalApiKey.value = saved.apiKey || "";
  if (modalModelName) modalModelName.value = saved.model || "phi3";
  if (modalBaseUrl) modalBaseUrl.value = saved.baseUrl || "";
  if (providerSelector) providerSelector.value = saved.provider || "ollama";
  updateApiKeyVisibilityState();
}

function openSettings() {
  initSettingsUI();
  connectionStatus.style.display = "none";
  settingsModal.style.display = "flex";
}

function closeSettings() {
  settingsModal.style.display = "none";
}

function handleProviderChangeInModal() {
  const provider = modalProviderSelect.value;
  if (provider === "ollama") {
    modalModelName.value = "phi3";
    modalBaseUrl.value = "http://localhost:11434";
  } else if (provider === "anthropic") {
    modalModelName.value = "claude-3-5-sonnet-20241022";
    modalBaseUrl.value = "";
  } else if (provider === "openai") {
    modalModelName.value = "gpt-4o-mini";
    modalBaseUrl.value = "https://api.openai.com/v1";
  }
  updateApiKeyVisibilityState();
}

function updateApiKeyVisibilityState() {
  const provider = modalProviderSelect.value;
  const apiKeyGroup = document.getElementById("apiKeyGroup");
  if (apiKeyGroup) {
    apiKeyGroup.style.display = (provider === "ollama") ? "none" : "flex";
  }
}

async function testModelConnection() {
  const provider = modalProviderSelect.value;
  const apiKey = modalApiKey.value.trim();
  const model = modalModelName.value.trim();
  const baseUrl = modalBaseUrl.value.trim();

  connectionStatus.style.display = "block";
  connectionStatus.className = "connection-status";
  connectionStatus.textContent = "Testing connection...";

  try {
    const res = await fetch("/config/test-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        api_key: apiKey || null,
        model: model || null,
        base_url: baseUrl || null
      })
    });

    const data = await res.json();
    if (data.status === "success") {
      connectionStatus.className = "connection-status success";
      connectionStatus.textContent = `✓ ${data.message}`;
    } else if (data.status === "unconfigured") {
      connectionStatus.className = "connection-status warning";
      connectionStatus.textContent = `! ${data.message}`;
    } else {
      connectionStatus.className = "connection-status error";
      connectionStatus.textContent = `✗ ${data.message}`;
    }
  } catch (err) {
    connectionStatus.className = "connection-status error";
    connectionStatus.textContent = "✗ Network error verifying model connection.";
  }
}

function applyAndSaveSettings() {
  const settings = {
    provider: modalProviderSelect.value,
    apiKey: modalApiKey.value.trim(),
    model: modalModelName.value.trim(),
    baseUrl: modalBaseUrl.value.trim()
  };

  saveLocalSettings(settings);

  if (providerSelector) {
    providerSelector.value = settings.provider;
  }

  closeSettings();
  checkHealth();
}

// Markdown Formatter
function formatMarkdownCached(text) {
  if (!text) return "";
  if (_markdownCache.has(text)) return _markdownCache.get(text);
  const result = formatMarkdownBasic(text);
  if (_markdownCache.size > 50) _markdownCache.clear();
  _markdownCache.set(text, result);
  return result;
}

function formatMarkdownBasic(text) {
  let esc = escapeHtml(text);

  // Markdown tables formatting
  esc = esc.replace(/\|(.+)\|/g, (match) => {
    const cells = match.split("|").slice(1, -1).map(c => c.trim());
    if (cells.every(c => /^[-:]+$/.test(c))) {
      return "";
    }
    const isHeader = !match.includes("---");
    const tag = isHeader ? "th" : "td";
    return `<tr>${cells.map(c => `<${tag} style="padding: 8px 14px; border: 1px solid var(--border-medium);">${c}</${tag}>`).join("")}</tr>`;
  });

  if (esc.includes("<tr>")) {
    esc = esc.replace(/(<tr>[\s\S]*?<\/tr>)+/g, '<table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.88rem;">$&</table>');
  }

  esc = esc.replace(/^### (.*$)/gim, '<h3 style="margin:14px 0 6px;">$1</h3>');
  esc = esc.replace(/^## (.*$)/gim, '<h2 style="margin:18px 0 8px;">$1</h2>');
  esc = esc.replace(/^# (.*$)/gim, '<h1 style="margin:22px 0 10px;">$1</h1>');
  esc = esc.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  esc = esc.replace(/\*(.*?)\*/g, "<em>$1</em>");
  esc = esc.replace(/^[-*] (.*$)/gim, "<li>$1</li>");

  return esc.split("\n\n").map(p => {
    if (p.trim().startsWith("<h") || p.trim().startsWith("<li>") || p.trim().startsWith("<table")) return p;
    return `<p>${p.replace(/\n/g, "<br>")}</p>`;
  }).join("");
}

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
