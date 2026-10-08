/**
 * Zeus AI — Frontend
 * ====================
 * Cliente leve (HTML/CSS/JS puro) para a API do Zeus. A voz (fala e
 * escuta) é feita inteiramente pelo navegador via Web Speech API —
 * nenhum áudio é enviado ao backend.
 */

const API_BASE = window.location.origin.includes("5500") || window.location.protocol === "file:"
  ? "http://localhost:8000"
  : ""; // mesmo host quando servido pelo próprio backend

const state = {
  token: localStorage.getItem("zeus_token") || null,
  refreshToken: localStorage.getItem("zeus_refresh_token") || null,
  username: localStorage.getItem("zeus_username") || null,
  isAdmin: false,
  conversationId: null,
  conversations: [],
  language: localStorage.getItem("zeus_language") || "pt-BR",
};

const SUPPORTED_LANGUAGES = [
  { code: "pt-BR", label: "PT-BR" },
  { code: "en-US", label: "EN-US" },
  { code: "es-ES", label: "ES-ES" },
];

// ---------------------------------------------------------------------
// Helpers de segurança / DOM
// ---------------------------------------------------------------------
// Nunca interpolar texto vindo do usuário (ou de documentos/anotações)
// diretamente em innerHTML — isso permitiria XSS caso o conteúdo contenha
// HTML/script. Toda construção dinâmica de DOM abaixo usa textContent ou
// esta função de escape.
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Helpers de API (com renovação automática do access token)
// ---------------------------------------------------------------------
function persistTokens() {
  if (state.token) localStorage.setItem("zeus_token", state.token);
  if (state.refreshToken) localStorage.setItem("zeus_refresh_token", state.refreshToken);
}

function clearSession() {
  state.token = null;
  state.refreshToken = null;
  state.username = null;
  state.isAdmin = false;
  localStorage.removeItem("zeus_token");
  localStorage.removeItem("zeus_refresh_token");
  localStorage.removeItem("zeus_username");
}

async function tryRefreshToken() {
  if (!state.refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    state.token = data.access_token;
    state.refreshToken = data.refresh_token;
    persistTokens();
    return true;
  } catch {
    return false;
  }
}

async function api(path, options = {}, _retried = false) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (response.status === 401 && state.refreshToken && !_retried) {
    // Access token expirado (dura só 30 minutos) — tenta renovar em
    // silêncio com o refresh token antes de desistir e pedir novo login.
    const refreshed = await tryRefreshToken();
    if (refreshed) return api(path, options, true);
    clearSession();
    updateUserChip();
    openAuthModal("login");
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || "Erro na API do Zeus");
  }
  return response.status === 204 ? null : response.json();
}

// ---------------------------------------------------------------------
// Autenticação — modal com abas de login e cadastro
// ---------------------------------------------------------------------
const authOverlay = document.getElementById("auth-overlay");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");

function openAuthModal(tab = "login") {
  authOverlay.hidden = false;
  loginError.textContent = "";
  registerError.textContent = "";
  switchAuthTab(tab);
}

function closeAuthModal() {
  authOverlay.hidden = true;
}

function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("tab-login").classList.toggle("active", isLogin);
  document.getElementById("tab-register").classList.toggle("active", !isLogin);
  loginForm.hidden = !isLogin;
  registerForm.hidden = isLogin;
  document.getElementById("auth-title").textContent = isLogin ? "Entrar no Zeus" : "Criar sua conta Zeus";
}

async function submitLogin(username, password) {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Usuário ou senha inválidos." }));
    throw new Error(err.detail);
  }
  const data = await res.json();
  state.token = data.access_token;
  state.refreshToken = data.refresh_token;
  state.username = username;
  persistTokens();
  localStorage.setItem("zeus_username", username);
}

async function onAuthenticated() {
  closeAuthModal();
  await loadCurrentUser();
  updateUserChip();
  loadConversations();
  loadPlugins();
  loadReminders();
}

function handleLogin() {
  if (state.token) {
    clearSession();
    updateUserChip();
    document.getElementById("chat").innerHTML = "";
    document.getElementById("conv-list").innerHTML = '<p class="section-label">Conversas recentes</p>';
    return;
  }
  openAuthModal("login");
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.textContent = "";
  const submitBtn = loginForm.querySelector(".modal-submit");
  submitBtn.disabled = true;
  try {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    await submitLogin(username, password);
    await onAuthenticated();
  } catch (err) {
    loginError.textContent = err.message.includes("Failed to fetch")
      ? "Não foi possível conectar ao servidor do Zeus. Verifique se o backend está rodando."
      : err.message;
  } finally {
    submitBtn.disabled = false;
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  registerError.textContent = "";
  const submitBtn = registerForm.querySelector(".modal-submit");
  submitBtn.disabled = true;
  try {
    const username = document.getElementById("register-username").value.trim();
    const email = document.getElementById("register-email").value.trim();
    const password = document.getElementById("register-password").value;

    await api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    // Após criar a conta, faz login automaticamente.
    await submitLogin(username, password);
    await onAuthenticated();
  } catch (err) {
    registerError.textContent = err.message.includes("Failed to fetch")
      ? "Não foi possível conectar ao servidor do Zeus. Verifique se o backend está rodando."
      : err.message;
  } finally {
    submitBtn.disabled = false;
  }
});

document.getElementById("tab-login").addEventListener("click", () => switchAuthTab("login"));
document.getElementById("tab-register").addEventListener("click", () => switchAuthTab("register"));
document.getElementById("auth-close").addEventListener("click", closeAuthModal);
authOverlay.addEventListener("click", (e) => {
  if (e.target === authOverlay) closeAuthModal();
});

async function loadCurrentUser() {
  if (!state.token) return;
  try {
    const me = await api("/api/auth/me");
    state.username = me.username;
    state.isAdmin = me.is_admin;
    localStorage.setItem("zeus_username", me.username);
  } catch (e) {
    console.error(e);
  }
}

function updateUserChip() {
  document.getElementById("user-name").textContent = state.username || "visitante";
  document.getElementById("login-btn").textContent = state.token ? "Sair" : "Entrar";
  document.getElementById("nav-admin").hidden = !state.isAdmin;
}

// ---------------------------------------------------------------------
// Trocar senha (mini-modal reaproveitando o padrão de modal existente)
// ---------------------------------------------------------------------
const passwordOverlay = document.getElementById("password-overlay");
const passwordForm = document.getElementById("password-form");
const passwordError = document.getElementById("password-error");

document.getElementById("change-password-btn").addEventListener("click", () => {
  if (!state.token) {
    openAuthModal("login");
    return;
  }
  passwordError.textContent = "";
  passwordForm.reset();
  passwordOverlay.hidden = false;
});
document.getElementById("password-close").addEventListener("click", () => (passwordOverlay.hidden = true));
passwordOverlay.addEventListener("click", (e) => {
  if (e.target === passwordOverlay) passwordOverlay.hidden = true;
});
passwordForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  passwordError.textContent = "";
  try {
    const current_password = document.getElementById("current-password").value;
    const new_password = document.getElementById("new-password").value;
    const data = await api("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    });
    state.token = data.access_token;
    state.refreshToken = data.refresh_token;
    persistTokens();
    passwordOverlay.hidden = true;
    logActivity("Senha alterada com sucesso.");
  } catch (err) {
    passwordError.textContent = err.message;
  }
});

// ---------------------------------------------------------------------
// Núcleo visual (indicador de estado: espera / ouvindo / pensando)
// ---------------------------------------------------------------------
function setCoreState(mode, caption) {
  const stage = document.getElementById("core-stage");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  stage.className = `core-stage ${mode}`;
  document.getElementById("core-caption").textContent = caption;

  statusDot.className = `status-dot ${mode}`;
  const labels = { idle: "ZEUS EM ESPERA", listening: "OUVINDO...", thinking: "PROCESSANDO..." };
  statusText.textContent = labels[mode] || "ZEUS EM ESPERA";
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------
function appendMessage(role, content, meta = "") {
  const chat = document.getElementById("chat");
  const wrapper = document.createElement("div");
  wrapper.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = content;
  wrapper.appendChild(bubble);

  if (meta) {
    const metaEl = document.createElement("span");
    metaEl.className = "msg-meta";
    metaEl.textContent = meta;
    wrapper.appendChild(metaEl);
  }

  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

async function sendMessage(text) {
  if (!text.trim()) return;
  if (!state.token) {
    openAuthModal("login");
    return;
  }

  appendMessage("user", text);
  document.getElementById("message-input").value = "";
  setCoreState("thinking", "Zeus está processando sua solicitação...");

  const bubble = appendMessage("assistant", "");
  let fullReply = "";
  let source = "llm";

  try {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify({
        conversation_id: state.conversationId,
        message: text,
        language: state.language,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error("Não foi possível iniciar a resposta em streaming.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop(); // pedaço incompleto fica guardado para a próxima leitura

      for (const rawEvent of events) {
        const lines = rawEvent.split("\n");
        const eventType = (lines.find((l) => l.startsWith("event:")) || "").replace("event:", "").trim();
        const dataLine = (lines.find((l) => l.startsWith("data:")) || "").replace("data:", "").trim();
        if (!dataLine) continue;
        const payload = JSON.parse(dataLine);

        if (eventType === "start") {
          state.conversationId = payload.conversation_id;
        } else if (eventType === "chunk") {
          fullReply += payload.text;
          bubble.textContent = fullReply;
          document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
        } else if (eventType === "done") {
          source = payload.source;
        } else if (eventType === "error") {
          throw new Error(payload.detail || "Erro ao gerar resposta.");
        }
      }
    }

    const metaEl = document.createElement("span");
    metaEl.className = "msg-meta";
    metaEl.textContent = `fonte: ${source}`;
    bubble.parentElement.appendChild(metaEl);

    logActivity(`Zeus respondeu (${source}).`);
    speakText(fullReply);
    loadContext(text);
    loadConversations();
    if (text.match(/lembr/i)) loadReminders();
  } catch (e) {
    bubble.textContent = `⚠ ${e.message}`;
  } finally {
    setCoreState("idle", 'Diga "Zeus" ou digite um comando para começar.');
  }
}

// ---------------------------------------------------------------------
// Conversas (barra lateral)
// ---------------------------------------------------------------------
async function loadConversations() {
  if (!state.token) return;
  try {
    const list = await api("/api/chat/conversations");
    state.conversations = list;
    const container = document.getElementById("conv-list");
    container.innerHTML = '<p class="section-label">Conversas recentes</p>';
    list.forEach((conv) => {
      const item = document.createElement("div");
      item.className = `conv-item ${conv.id === state.conversationId ? "active" : ""}`;
      item.textContent = conv.title || "Conversa sem título";
      item.onclick = () => openConversation(conv.id);
      container.appendChild(item);
    });
  } catch (e) {
    console.error(e);
  }
}

async function openConversation(id) {
  state.conversationId = id;
  document.getElementById("chat").innerHTML = "";
  const messages = await api(`/api/chat/conversations/${id}/messages`);
  messages.forEach((m) => appendMessage(m.role, m.content));
  loadConversations();
}

// ---------------------------------------------------------------------
// Contexto de memória (painel direito) e plugins
// ---------------------------------------------------------------------
async function loadContext(query) {
  try {
    const results = await api("/api/memory/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 4 }),
    });
    const container = document.getElementById("context-list");
    container.innerHTML = "";
    if (!results.length) {
      const hint = document.createElement("p");
      hint.className = "empty-hint";
      hint.textContent = "Nenhum contexto semântico relevante encontrado.";
      container.appendChild(hint);
      return;
    }
    results.forEach((r) => {
      const div = document.createElement("div");
      div.className = "context-item";

      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = r.metadata.type || "memória";
      div.appendChild(tag);

      // O texto vem do próprio conteúdo do usuário (mensagens, documentos,
      // anotações) e nunca deve ser injetado como HTML — só como texto.
      div.appendChild(document.createTextNode(`${r.text.slice(0, 120)}...`));
      container.appendChild(div);
    });
  } catch (e) {
    console.error(e);
  }
}

async function loadPlugins() {
  try {
    const plugins = await api("/api/plugins");
    const container = document.getElementById("plugin-list");
    container.innerHTML = "";
    plugins.forEach((p) => {
      const div = document.createElement("div");
      div.className = "plugin-item";

      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = "ativo";
      div.appendChild(tag);
      div.appendChild(document.createTextNode(`${p.name} — ${p.description}`));
      container.appendChild(div);
    });
  } catch (e) {
    console.error(e);
  }
}

function logActivity(text) {
  const log = document.getElementById("activity-log");
  const div = document.createElement("div");
  div.className = "activity-item";
  div.textContent = `> ${text}`;
  log.prepend(div);
  while (log.children.length > 8) log.removeChild(log.lastChild);
}

// ---------------------------------------------------------------------
// Lembretes (mini-lista no painel de contexto)
// ---------------------------------------------------------------------
async function loadReminders() {
  if (!state.token) return;
  try {
    const reminders = await api("/api/reminders");
    const container = document.getElementById("reminder-list");
    container.innerHTML = "";
    if (!reminders.length) {
      const hint = document.createElement("p");
      hint.className = "empty-hint";
      hint.textContent = "Nenhum lembrete pendente.";
      container.appendChild(hint);
      return;
    }
    reminders.forEach((r) => {
      const row = document.createElement("div");
      row.className = "reminder-item";

      const text = document.createElement("span");
      text.textContent = r.content;
      row.appendChild(text);

      const doneBtn = document.createElement("button");
      doneBtn.className = "mini-btn";
      doneBtn.textContent = "✓";
      doneBtn.title = "Marcar como feito";
      doneBtn.onclick = async () => {
        await api(`/api/reminders/${r.id}/done`, { method: "PATCH" });
        loadReminders();
      };
      row.appendChild(doneBtn);

      container.appendChild(row);
    });
  } catch (e) {
    console.error(e);
  }
}

// ---------------------------------------------------------------------
// Painel de Anotações
// ---------------------------------------------------------------------
const notesOverlay = document.getElementById("notes-overlay");
const notesForm = document.getElementById("notes-form");
const notesListEl = document.getElementById("notes-list");

async function openNotesPanel() {
  if (!state.token) return openAuthModal("login");
  notesOverlay.hidden = false;
  await refreshNotesList();
}

async function refreshNotesList() {
  notesListEl.innerHTML = '<p class="empty-hint">Carregando...</p>';
  try {
    const notes = await api("/api/memory/notes");
    notesListEl.innerHTML = "";
    if (!notes.length) {
      notesListEl.innerHTML = '<p class="empty-hint">Nenhuma anotação ainda.</p>';
      return;
    }
    notes.forEach((n) => {
      const item = document.createElement("div");
      item.className = "panel-list-item";

      const title = document.createElement("strong");
      title.textContent = n.title;
      item.appendChild(title);

      if (n.content) {
        const content = document.createElement("p");
        content.textContent = n.content;
        item.appendChild(content);
      }

      const delBtn = document.createElement("button");
      delBtn.className = "mini-btn";
      delBtn.textContent = "Excluir";
      delBtn.onclick = async () => {
        await api(`/api/memory/notes/${n.id}`, { method: "DELETE" });
        refreshNotesList();
      };
      item.appendChild(delBtn);

      notesListEl.appendChild(item);
    });
  } catch (e) {
    notesListEl.innerHTML = "";
    const err = document.createElement("p");
    err.className = "field-error";
    err.textContent = e.message;
    notesListEl.appendChild(err);
  }
}

notesForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const title = document.getElementById("note-title").value.trim();
    const content = document.getElementById("note-content").value.trim();
    if (!title) return;
    await api("/api/memory/notes", { method: "POST", body: JSON.stringify({ title, content }) });
    notesForm.reset();
    refreshNotesList();
  } catch (err) {
    console.error(err);
  }
});

document.getElementById("nav-notes").addEventListener("click", openNotesPanel);
document.getElementById("notes-close").addEventListener("click", () => (notesOverlay.hidden = true));
notesOverlay.addEventListener("click", (e) => {
  if (e.target === notesOverlay) notesOverlay.hidden = true;
});

// ---------------------------------------------------------------------
// Painel de Documentos
// ---------------------------------------------------------------------
const docsOverlay = document.getElementById("docs-overlay");
const docsForm = document.getElementById("docs-form");
const docsListEl = document.getElementById("docs-list");
const docsError = document.getElementById("docs-error");

async function openDocsPanel() {
  if (!state.token) return openAuthModal("login");
  docsOverlay.hidden = false;
  await refreshDocsList();
}

async function refreshDocsList() {
  docsListEl.innerHTML = '<p class="empty-hint">Carregando...</p>';
  try {
    const docs = await api("/api/documents");
    docsListEl.innerHTML = "";
    if (!docs.length) {
      docsListEl.innerHTML = '<p class="empty-hint">Nenhum documento enviado ainda.</p>';
      return;
    }
    docs.forEach((d) => {
      const item = document.createElement("div");
      item.className = "panel-list-item";

      const title = document.createElement("strong");
      title.textContent = d.filename;
      item.appendChild(title);

      const status = document.createElement("p");
      status.textContent = d.indexed
        ? d.summary || "Documento indexado."
        : "Não foi possível extrair texto deste arquivo.";
      item.appendChild(status);

      const delBtn = document.createElement("button");
      delBtn.className = "mini-btn";
      delBtn.textContent = "Excluir";
      delBtn.onclick = async () => {
        await api(`/api/documents/${d.id}`, { method: "DELETE" });
        refreshDocsList();
      };
      item.appendChild(delBtn);

      docsListEl.appendChild(item);
    });
  } catch (e) {
    docsListEl.innerHTML = "";
    const err = document.createElement("p");
    err.className = "field-error";
    err.textContent = e.message;
    docsListEl.appendChild(err);
  }
}

docsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  docsError.textContent = "";
  const fileInput = document.getElementById("doc-file");
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  try {
    await api("/api/documents/upload", { method: "POST", body: formData });
    docsForm.reset();
    refreshDocsList();
  } catch (err) {
    docsError.textContent = err.message;
  }
});

document.getElementById("nav-docs").addEventListener("click", openDocsPanel);
document.getElementById("docs-close").addEventListener("click", () => (docsOverlay.hidden = true));
docsOverlay.addEventListener("click", (e) => {
  if (e.target === docsOverlay) docsOverlay.hidden = true;
});

// ---------------------------------------------------------------------
// Painel Admin
// ---------------------------------------------------------------------
const adminOverlay = document.getElementById("admin-overlay");
const adminStatsEl = document.getElementById("admin-stats");
const adminUsersEl = document.getElementById("admin-users");

async function openAdminPanel() {
  if (!state.token || !state.isAdmin) return;
  adminOverlay.hidden = false;
  try {
    const [stats, users] = await Promise.all([api("/api/admin/stats"), api("/api/admin/users")]);

    adminStatsEl.innerHTML = "";
    Object.entries(stats).forEach(([key, value]) => {
      const card = document.createElement("div");
      card.className = "admin-stat";
      const num = document.createElement("strong");
      num.textContent = value;
      const label = document.createElement("span");
      label.textContent = key.replaceAll("_", " ");
      card.append(num, label);
      adminStatsEl.appendChild(card);
    });

    adminUsersEl.innerHTML = "";
    users.forEach((u) => {
      const row = document.createElement("div");
      row.className = "panel-list-item";

      const title = document.createElement("strong");
      title.textContent = `${u.username} ${u.is_admin ? "(admin)" : ""}`;
      row.appendChild(title);

      const email = document.createElement("p");
      email.textContent = u.email;
      row.appendChild(email);

      const toggleBtn = document.createElement("button");
      toggleBtn.className = "mini-btn";
      toggleBtn.textContent = u.is_active ? "Desativar" : "Ativar";
      toggleBtn.onclick = async () => {
        await api(`/api/admin/users/${u.id}/toggle-active`, { method: "PATCH" });
        openAdminPanel();
      };
      row.appendChild(toggleBtn);

      adminUsersEl.appendChild(row);
    });
  } catch (e) {
    adminStatsEl.innerHTML = "";
    adminUsersEl.innerHTML = `<p class="field-error">${escapeHtml(e.message)}</p>`;
  }
}

document.getElementById("nav-admin").addEventListener("click", openAdminPanel);
document.getElementById("admin-close").addEventListener("click", () => (adminOverlay.hidden = true));
adminOverlay.addEventListener("click", (e) => {
  if (e.target === adminOverlay) adminOverlay.hidden = true;
});

// ---------------------------------------------------------------------
// Seletor de idioma (afeta voz e o idioma em que o Zeus responde)
// ---------------------------------------------------------------------
function updateLangButton() {
  const current = SUPPORTED_LANGUAGES.find((l) => l.code === state.language) || SUPPORTED_LANGUAGES[0];
  document.getElementById("lang-btn").textContent = current.label;
}

document.getElementById("lang-btn").addEventListener("click", () => {
  const idx = SUPPORTED_LANGUAGES.findIndex((l) => l.code === state.language);
  const next = SUPPORTED_LANGUAGES[(idx + 1) % SUPPORTED_LANGUAGES.length];
  state.language = next.code;
  localStorage.setItem("zeus_language", next.code);
  updateLangButton();
  logActivity(`Idioma alterado para ${next.label}.`);
});

// ---------------------------------------------------------------------
// Voz — 100% no navegador via Web Speech API (zero downloads, zero backend)
// ---------------------------------------------------------------------
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let isListening = false;

function speakText(text) {
  if (!("speechSynthesis" in window) || !text) return;
  window.speechSynthesis.cancel(); // evita sobrepor falas
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = state.language || "pt-BR";
  window.speechSynthesis.speak(utterance);
}

function toggleRecording() {
  const micBtn = document.getElementById("mic-btn");

  if (!SpeechRecognitionAPI) {
    alert("Seu navegador não suporta reconhecimento de voz. Tente Chrome ou Edge.");
    return;
  }

  if (isListening) {
    recognizer.stop();
    return;
  }

  recognizer = new SpeechRecognitionAPI();
  recognizer.lang = state.language || "pt-BR";
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  recognizer.onstart = () => {
    isListening = true;
    micBtn.classList.add("recording");
    setCoreState("listening", "Zeus está ouvindo...");
  };

  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    sendMessage(transcript);
  };

  recognizer.onerror = (event) => {
    appendMessage("assistant", `⚠ Não foi possível entender o áudio (${event.error}).`);
    setCoreState("idle", 'Diga "Zeus" ou digite um comando para começar.');
  };

  recognizer.onend = () => {
    isListening = false;
    micBtn.classList.remove("recording");
  };

  recognizer.start();
}

// ---------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------
document.getElementById("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(document.getElementById("message-input").value);
});

document.getElementById("mic-btn").addEventListener("click", toggleRecording);
document.getElementById("login-btn").addEventListener("click", handleLogin);
document.getElementById("new-chat-btn").addEventListener("click", () => {
  state.conversationId = null;
  document.getElementById("chat").innerHTML = "";
  closeSidebar();
});

// ---------------------------------------------------------------------
// Menu mobile (gaveta lateral)
// ---------------------------------------------------------------------
const sidebarEl = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const menuBtn = document.getElementById("menu-btn");
const sidebarCloseBtn = document.getElementById("sidebar-close");

function openSidebar() {
  sidebarEl.classList.add("open");
  sidebarBackdrop.classList.add("open");
  menuBtn.setAttribute("aria-expanded", "true");
}
function closeSidebar() {
  sidebarEl.classList.remove("open");
  sidebarBackdrop.classList.remove("open");
  menuBtn.setAttribute("aria-expanded", "false");
}
menuBtn.addEventListener("click", () => {
  sidebarEl.classList.contains("open") ? closeSidebar() : openSidebar();
});
sidebarCloseBtn.addEventListener("click", closeSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);

// Fecha a gaveta ao escolher uma conversa ou item de navegação no mobile
document.getElementById("conv-list").addEventListener("click", (e) => {
  if (e.target.closest(".conv-item") && window.innerWidth <= 760) closeSidebar();
});
["nav-notes", "nav-docs", "nav-admin"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("click", closeSidebar);
});

// ---------------------------------------------------------------------
// PWA — permite "Adicionar à tela inicial" no celular
// ---------------------------------------------------------------------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch((e) => console.warn("Service worker falhou:", e));
  });
}

updateUserChip();
updateLangButton();
setCoreState("idle", 'Diga "Zeus" ou digite um comando para começar.');
if (state.token) {
  loadCurrentUser().then(updateUserChip);
  loadConversations();
  loadPlugins();
  loadReminders();
}
