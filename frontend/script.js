import { avatar } from './avatar/avatar.js';
import { checkHealth, sendChatMessageV2, generateSpeech, transcribeAudio, getUserConversations, getConversationMessages } from './api.js';
import { subscribeToMessages } from './supabase_client.js';
import {
  initAuth,
  isAuthenticated,
  getUser,
  signIn,
  signUp,
  signOut as authSignOut,
  getLastConversationId,
  setLastConversationId,
} from './auth.js';

const messagesDiv = document.getElementById("messages");
const input = document.getElementById("messageInput");
const typing = document.getElementById("typing");
const recordBtn = document.getElementById("recordBtn");
const playbackBtn = document.getElementById("playbackBtn");
const conversationListEl = document.getElementById("conversationList");
const newChatBtn = document.getElementById("newChatBtn");

let currentAudio = null;
let _currentConversationId = null;
let _conversations = [];
let _unsubscribeMessages = null;

function togglePlayback() {
  if (!currentAudio) return;
  if (currentAudio.paused) {
    currentAudio.play();
  } else {
    currentAudio.pause();
  }
}

const canvas = document.getElementById("visualizer");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
}

resizeCanvas();

window.addEventListener("resize", resizeCanvas);

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

let currentLanguage = "en";

function clearVisualizer() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

clearVisualizer();

function setAgentState(state) {

  const el =
    document.getElementById(
      "agentState"
    );

  if (!el) return;

  switch (state) {

    case "idle":
      el.innerHTML =
        "🟢 Idle";
      break;

    case "listening":
      el.innerHTML =
        "🎤 Listening";
      break;

    case "thinking":
      el.innerHTML =
        "🧠 Thinking";
      break;

    case "speaking":
      el.innerHTML =
        "🔊 Speaking";
      break;
  }
}

setAgentState("idle");

try {
  avatar.init('avatarContainer');
  avatar.load('avatar/assistant.vrm', 'models/idle.vrma', 'models/talking.vrma')
      .then(() => console.log('Avatar loaded successfully'))
      .catch(err => console.error('Failed to load avatar:', err));
} catch (err) {
  console.error('Avatar init failed — continuing without avatar:', err);
}

const englishBtn =
  document.getElementById("englishBtn");

const hindiBtn =
  document.getElementById("hindiBtn");

if (englishBtn && hindiBtn) {

  englishBtn.addEventListener(
    "click",
    () => {

      currentLanguage = "en";

      englishBtn.classList.add(
        "active"
      );

      hindiBtn.classList.remove(
        "active"
      );

      input.placeholder =
        "Ask something...";
    }
  );

  hindiBtn.addEventListener(
    "click",
    () => {

      currentLanguage = "hi";

      hindiBtn.classList.add(
        "active"
      );

      englishBtn.classList.remove(
        "active"
      );

      input.placeholder =
        "कुछ पूछें...";
    }
  );
}

function addMessage(text, type) {

  const div = document.createElement("div");

  div.className = `message ${type}`;

  div.textContent = text;

  messagesDiv.appendChild(div);

  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  return div;
}

// ── GenUI Card Renderers ────────────────────────────────────────────────────

function renderGenUICard(uiData) {
  if (!uiData || !uiData.type) return;

  switch (uiData.type) {
    case "weather_card":
      renderWeatherCard(uiData);
      break;
    case "news_list":
      renderNewsList(uiData);
      break;
    case "search_card":
      renderSearchCard(uiData);
      break;
    case "knowledge_card":
      renderKnowledgeCard(uiData);
      break;
    case "rag_card":
      renderRagCard(uiData);
      break;
    case "answer_panel":
      renderAnswerPanel(uiData);
      break;
    case "ui_preview":
      renderUIPreview(uiData);
      break;
    default:
      // Unknown type — fall back to a minimal summary card
      renderAnswerPanel(uiData);
      break;
  }
}

function renderWeatherCard(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let html = '<div class="genui-card-header">';
  html += `<div class="genui-card-title">${escapeHtml(ui.title || "Weather")}</div>`;
  if (ui.subtitle) {
    html += `<div class="genui-card-subtitle">${escapeHtml(ui.subtitle)}</div>`;
  }
  html += '</div>';
  html += '<div class="genui-card-body"><div class="weather-fields">';

  if (ui.fields && Array.isArray(ui.fields)) {
    for (const field of ui.fields) {
      html += '<div class="weather-field">';
      html += `<span class="weather-field-label">${escapeHtml(field.label || "")}</span>`;
      html += `<span class="weather-field-value">${escapeHtml(field.value || "")}</span>`;
      html += '</div>';
    }
  }

  html += '</div></div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderNewsList(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let html = '<div class="genui-card-header">';
  html += `<div class="genui-card-title">${escapeHtml(ui.title || "News")}</div>`;
  html += '</div>';
  html += '<div class="genui-card-body"><div class="news-items">';

  if (ui.items && Array.isArray(ui.items)) {
    for (const item of ui.items) {
      html += '<div class="news-item">';
      html += `<div class="news-item-title">${escapeHtml(item.title || "")}</div>`;
      if (item.description) {
        html += `<div class="news-item-desc">${escapeHtml(item.description)}</div>`;
      }
      html += '</div>';
    }
  }

  html += '</div></div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderSearchCard(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let html = '<div class="genui-card-header">';
  html += '<div class="genui-card-header-row">';
  html += '<span class="genui-card-icon">🌐</span>';
  html += `<div class="genui-card-title">${escapeHtml(ui.title || "Web Search")}</div>`;
  html += '</div>';
  if (ui.subtitle) {
    html += `<div class="genui-card-subtitle">${escapeHtml(ui.subtitle)}</div>`;
  }
  html += '</div>';
  html += '<div class="genui-card-body">';
  html += `<div class="genui-card-response">${escapeHtml(ui.response || ui.summary || "")}</div>`;
  html += '</div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderKnowledgeCard(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let html = '<div class="genui-card-header">';
  html += '<div class="genui-card-header-row">';
  html += '<span class="genui-card-icon">📚</span>';
  html += `<div class="genui-card-title">${escapeHtml(ui.title || "Knowledge Base")}</div>`;
  html += '</div>';
  if (ui.subtitle) {
    html += `<div class="genui-card-subtitle">${escapeHtml(ui.subtitle)}</div>`;
  }
  html += '</div>';
  html += '<div class="genui-card-body">';
  html += `<div class="genui-card-response">${escapeHtml(ui.response || ui.summary || "")}</div>`;
  html += '</div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderRagCard(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let html = '<div class="genui-card-header">';
  html += '<div class="genui-card-header-row">';
  html += '<span class="genui-card-icon">🧠</span>';
  html += `<div class="genui-card-title">${escapeHtml(ui.title || "Assistant")}</div>`;
  html += '</div>';
  html += '</div>';
  html += '<div class="genui-card-body">';
  html += `<div class="genui-card-response">${escapeHtml(ui.response || ui.summary || "")}</div>`;
  html += '</div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderAnswerPanel(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  let icon = "💬";
  if (ui.type === "answer_panel") {
    icon = "🧠";
  }

  let html = '<div class="genui-card-body"><div class="answer-panel">';
  html += `<div class="answer-panel-icon">${icon}</div>`;
  html += '<div class="answer-panel-content">';

  if (ui.title) {
    html += `<div class="genui-card-title" style="margin-bottom:6px;">${escapeHtml(ui.title)}</div>`;
  }
  if (ui.summary) {
    html += `<div class="answer-panel-summary">${escapeHtml(ui.summary)}</div>`;
  }

  html += '</div></div></div>';
  card.innerHTML = html;
  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderUIPreview(ui) {
  const card = document.createElement("div");
  card.className = "genui-card";

  // Build header HTML safely
  let headerHtml = '<div class="genui-card-header">';
  headerHtml += `<div class="genui-card-title">🎨 ${escapeHtml(ui.title || "Generated UI")}</div>`;
  headerHtml += '</div>';

  // Build body container HTML (but NOT the iframe — we'll create that directly)
  let bodyHtml = '<div class="genui-card-body">';
  bodyHtml += '<div class="ui-preview-container">';
  // iframe placeholder — we insert a div and replace it with a real iframe element later
  bodyHtml += '<div id="ui-preview-placeholder"></div>';
  bodyHtml += '</div>';

  if (ui.filename) {
    const fileUrl = `generated/${ui.filename}`;
    bodyHtml += `<div style="margin-top:10px;text-align:center;">`;
    bodyHtml += `<a href="${fileUrl}" target="_blank" class="ui-open-btn" style="display:inline-block;padding:10px 20px;background:#947dff;color:white;text-decoration:none;border-radius:12px;">↗ Open in new tab</a>`;
    bodyHtml += `</div>`;
  }
  bodyHtml += '</div>';

  card.innerHTML = headerHtml + bodyHtml;

  // Create the iframe element programmatically and set srcdoc via JS property
  const iframe = document.createElement('iframe');
  iframe.className = 'ui-preview-iframe';
  iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');
  // Direct JS property assignment — avoids HTML attribute encoding issues
  iframe.srcdoc = ui.html || '';

  // Replace the placeholder div with the real iframe
  const placeholder = card.querySelector('#ui-preview-placeholder');
  if (placeholder && placeholder.parentNode) {
    placeholder.parentNode.replaceChild(iframe, placeholder);
  }

  messagesDiv.appendChild(card);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function drawVisualizer(dataArray) {

  ctx.clearRect(
    0,
    0,
    canvas.width,
    canvas.height
  );

  const bars = Math.max(
    14,
    Math.floor(canvas.width / 12)
  );

  const centerY =
    canvas.height / 2;

  const spacing =
    canvas.width / bars;

  const barWidth =
    Math.max(
      3,
      spacing * 0.65
    );

  ctx.fillStyle = "white";

  for (
    let i = 0;
    i < bars;
    i++
  ) {

    const sourceIndex =
      Math.floor(
        i *
        dataArray.length /
        bars
      );

    const value =
      dataArray[sourceIndex] || 0;

    const height =
      Math.max(
        4,
        value * 0.75
      );

    const x =
      i * spacing;

    ctx.fillRect(
      x,
      centerY - height / 2,
      barWidth,
      height
    );
  }
}

// ── Conversation List ──────────────────────────────────────────────────────

/**
 * Format a unix timestamp to a relative time string.
 */
function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/**
 * Render the conversation list in the sidebar.
 */
function renderConversationList(conversations) {
  if (!conversationListEl) return;
  _conversations = conversations;

  if (!conversations || conversations.length === 0) {
    conversationListEl.innerHTML = '<div class="conversation-empty">No conversations yet</div>';
    return;
  }

  let html = '';
  for (const conv of conversations) {
    const isActive = conv.id === _currentConversationId;
    const title = conv.title || 'New Conversation';
    const preview = conv.last_preview || '';
    const time = formatTime(conv.updated_at);

    html += `
      <div class="conversation-item ${isActive ? 'active' : ''}" data-conv-id="${conv.id}">
        <div class="conversation-item-title">${escapeHtml(title)}</div>
        <div class="conversation-item-preview">${escapeHtml(preview)}</div>
        <div class="conversation-item-time">${time}</div>
      </div>
    `;
  }

  conversationListEl.innerHTML = html;

  // Attach click handlers
  conversationListEl.querySelectorAll('.conversation-item').forEach(el => {
    el.addEventListener('click', () => {
      const convId = parseInt(el.dataset.convId, 10);
      if (convId && convId !== _currentConversationId) {
        switchConversation(convId);
      }
    });
  });
}

/**
 * Switch to a different conversation, loading its messages.
 */
async function switchConversation(conversationId) {
  if (!conversationId) return;

  // Unsubscribe from real-time for previous conversation
  if (_unsubscribeMessages) {
    _unsubscribeMessages();
    _unsubscribeMessages = null;
  }

  _currentConversationId = conversationId;
  setLastConversationId(conversationId);

  // Clear messages and show loading
  messagesDiv.innerHTML = '';

  try {
    const data = await getConversationMessages(conversationId);
    if (data.messages) {
      for (const msg of data.messages) {
        addMessage(msg.content, msg.role === 'user' ? 'user' : 'ai');
        // Render GenUI card if present in metadata
        if (msg.metadata && msg.metadata.integration) {
          // We don't have the full ui data here, so skip card rendering for loaded messages
        }
      }
    }

    // Update conversation list highlight
    renderConversationList(_conversations);

    // Subscribe to real-time updates for this conversation
    subscribeToConversation(conversationId);

  } catch (err) {
    console.error('Failed to load conversation:', err);
    addMessage('Could not load conversation messages.', 'ai');
  }
}

/**
 * Start a new conversation.
 */
async function startNewConversation() {
  // Clear the current conversation ID so the next send creates a new one
  _currentConversationId = null;
  setLastConversationId(null);

  // Clear messages
  messagesDiv.innerHTML = '';
  addMessage('Hello. I am your local AI assistant.', 'ai');

  // Unsubscribe from real-time
  if (_unsubscribeMessages) {
    _unsubscribeMessages();
    _unsubscribeMessages = null;
  }

  // Update conversation list highlight
  renderConversationList(_conversations);
}

// ── Supabase Real-time Subscription ────────────────────────────────────────

/**
 * Subscribe to real-time messages for a given conversation.
 * Unsubscribes from any previous conversation first.
 */
function subscribeToConversation(conversationId) {
  // Unsubscribe from previous conversation
  if (_unsubscribeMessages) {
    _unsubscribeMessages();
    _unsubscribeMessages = null;
  }

  if (!conversationId) return;

  _unsubscribeMessages = subscribeToMessages(conversationId, (message) => {
    // Only add messages from "assistant" role (user messages are already added by sendMessage)
    if (message.role === 'assistant' && message.content) {
      addMessage(message.content, 'ai');
    }
  });
}

// ── Send Message (v2 with conversation persistence) ────────────────────────

async function sendMessage() {

  const message = input.value.trim();

  if (!message) return;

  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
    if (playbackBtn) {
      playbackBtn.disabled = true;
      playbackBtn.textContent = "⏸ Pause";
    }
  }

  addMessage(message, "user");

  input.value = "";

  typing.style.display = "block";
  setAgentState("thinking");

  try {

    const data = await sendChatMessageV2(message, currentLanguage, _currentConversationId);

    typing.style.display = "none";

    // Update current conversation ID
    if (data.conversation_id) {
      _currentConversationId = data.conversation_id;
      setLastConversationId(data.conversation_id);
    }

    addMessage(data.response, "ai");

    // Render GenUI card if present in response
    if (data.ui) {
      renderGenUICard(data.ui);
    }

    // Refresh conversation list
    loadConversations();

    speakResponse(data.response);

  } catch (error) {

    typing.style.display = "none";

    addMessage("Could not connect to backend.", "ai");

    console.error(error);
  }
}

async function speakResponse(text) {

  try {

    const audioBlob = await generateSpeech(text, currentLanguage);

    const audioUrl = URL.createObjectURL(audioBlob);

    const audio = new Audio(audioUrl);
    currentAudio = audio;

    if (playbackBtn) {
      playbackBtn.disabled = false;
      playbackBtn.textContent = "⏸ Pause";
    }

    audio.crossOrigin = "anonymous";

    const audioContext =
      new (window.AudioContext ||
        window.webkitAudioContext)();

    await audioContext.resume();

    const analyser =
      audioContext.createAnalyser();

    analyser.fftSize = 128;

    const source =
      audioContext.createMediaElementSource(audio);

    source.connect(analyser);

    analyser.connect(audioContext.destination);

    const dataArray =
      new Uint8Array(
        analyser.frequencyBinCount
      );

    function animate() {

      if (audio.paused || audio.ended) {
        if (audio.ended) {
          clearVisualizer();
        }
        avatar.stopSpeaking();
        return;
      }

      analyser.getByteFrequencyData(dataArray);

      drawVisualizer(dataArray);
      avatar.setAnalyzerData(dataArray);

      requestAnimationFrame(animate);
    }

    audio.onplay = () => {

      setAgentState("speaking");
      if (playbackBtn) playbackBtn.textContent = "⏸ Pause";
      avatar.resume();
      avatar.startSpeaking();
      animate();
    };

    audio.onpause = () => {
      if (!audio.ended) {
        setAgentState("idle");
        if (playbackBtn) playbackBtn.textContent = "▶ Resume";
        avatar.pause();
      }
    };

    audio.onended = () => {

      setAgentState("idle");

      clearVisualizer();

      avatar.stopSpeaking();
      avatar.resume(); // Keep running idle animation

      audioContext.close();
      currentAudio = null;
      if (playbackBtn) {
        playbackBtn.disabled = true;
        playbackBtn.textContent = "⏸ Pause";
      }
    };

    await audio.play();

  } catch (err) {

    setAgentState("idle");

    console.error(err);

    clearVisualizer();

    avatar.stopSpeaking();
    avatar.resume();

    currentAudio = null;
    if (playbackBtn) {
      playbackBtn.disabled = true;
      playbackBtn.textContent = "⏸ Pause";
    }
  }
}

async function toggleRecording() {

  if (!isRecording) {
    startRecording();
  } else {
    stopRecording();
  }
}

async function startRecording() {

  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
    if (playbackBtn) {
      playbackBtn.disabled = true;
      playbackBtn.textContent = "⏸ Pause";
    }
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: true
  });

  mediaRecorder = new MediaRecorder(stream);

  audioChunks = [];

  mediaRecorder.ondataavailable = event => {
    audioChunks.push(event.data);
  };

  mediaRecorder.onstop = async () => {

    const audioBlob = new Blob(audioChunks, {
      type: "audio/wav"
    });

    typing.style.display = "block";
    setAgentState("thinking");

    try {
      const data = await transcribeAudio(audioBlob, currentLanguage);

      typing.style.display = "none";

      input.value = data.text;
    } catch (error) {
      typing.style.display = "none";
      console.error("Transcription failed:", error);
      addMessage("Could not transcribe audio.", "ai");
    }
  };

  mediaRecorder.start();

  setAgentState("listening");

  isRecording = true;

  recordBtn.classList.add("recording");
}

function stopRecording() {

  mediaRecorder.stop();

  isRecording = false;

  recordBtn.classList.remove("recording");
}

input.addEventListener("keydown", function (event) {

  if (event.key === "Enter") {
    window.sendMessage();
  }
});

// ── Load Conversations ─────────────────────────────────────────────────────

async function loadConversations() {
  try {
    const data = await getUserConversations(50, 0);
    const conversations = data.conversations || [];

    // Enrich with last message preview (the API already returns message_count)
    // We'll use the title as-is
    renderConversationList(conversations);

    return conversations;
  } catch (err) {
    console.error('Failed to load conversations:', err);
    return [];
  }
}

// ── Auth UI Logic ──────────────────────────────────────────────────────────

const authModal = document.getElementById("authModal");
const authActions = document.getElementById("authActions");
const showSignInBtn = document.getElementById("showSignInBtn");
const showSignUpBtn = document.getElementById("showSignUpBtn");
const authCloseBtn = document.getElementById("authCloseBtn");
const authTabSignIn = document.getElementById("authTabSignIn");
const authTabSignUp = document.getElementById("authTabSignUp");
const signInForm = document.getElementById("signInForm");
const signUpForm = document.getElementById("signUpForm");
const signInError = document.getElementById("signInError");
const signUpError = document.getElementById("signUpError");
const userProfile = document.getElementById("userProfile");
const signOutBtn = document.getElementById("signOutBtn");
const userDisplayName = document.getElementById("userDisplayName");
const userUsername = document.getElementById("userUsername");

/**
 * Show the auth modal.
 */
function showAuthModal(mode = "signin") {
  authModal.hidden = false;
  mode === "signup" ? switchToSignUp() : switchToSignIn();
}

/**
 * Hide the auth modal.
 */
function hideAuthModal() {
  authModal.hidden = true;
  signInError.style.display = "none";
  signUpError.style.display = "none";
}

/**
 * Switch to the Sign In tab.
 */
function switchToSignIn() {
  authTabSignIn.classList.add("active");
  authTabSignUp.classList.remove("active");
  signInForm.hidden = false;
  signUpForm.hidden = true;
  signInError.style.display = "none";
  signUpError.style.display = "none";
}

/**
 * Switch to the Sign Up tab.
 */
function switchToSignUp() {
  authTabSignUp.classList.add("active");
  authTabSignIn.classList.remove("active");
  signUpForm.hidden = false;
  signInForm.hidden = true;
  signInError.style.display = "none";
  signUpError.style.display = "none";
}

/**
 * Update the UI to reflect the current auth state.
 */
function updateAuthUI(authed = isAuthenticated()) {
  const user = getUser();

  if (authed && user) {
    // Show the compact signed-in header state.
    userProfile.hidden = false;
    authActions.hidden = true;
    userDisplayName.textContent = user.display_name || user.username;
    userUsername.textContent = `@${user.username}`;
  } else {
    // Show the sign-in and sign-up actions.
    userProfile.hidden = true;
    authActions.hidden = false;
  }
}

// ── Auth Event Handlers ────────────────────────────────────────────────────

// Show auth modal
showSignInBtn.addEventListener("click", () => showAuthModal("signin"));
showSignUpBtn.addEventListener("click", () => showAuthModal("signup"));

// Close auth modal
authCloseBtn.addEventListener("click", hideAuthModal);

// Close modal when clicking outside
authModal.addEventListener("click", (e) => {
  if (e.target === authModal) {
    hideAuthModal();
  }
});

// Tab switching
authTabSignIn.addEventListener("click", switchToSignIn);
authTabSignUp.addEventListener("click", switchToSignUp);

// Sign In form submission
signInForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  signInError.style.display = "none";

  const username = document.getElementById("signInUsername").value.trim();
  const password = document.getElementById("signInPassword").value;

  if (!username || !password) {
    signInError.textContent = "Please fill in all fields.";
    signInError.style.display = "block";
    return;
  }

  const submitBtn = signInForm.querySelector(".auth-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Signing in...";

  try {
    await signIn(username, password);
    hideAuthModal();
    updateAuthUI();
    addMessage(`Welcome back, ${getUser().display_name || getUser().username}!`, "ai");
    // Load user's conversations after sign in
    await loadAndRestoreConversation();
  } catch (err) {
    signInError.textContent = err.message;
    signInError.style.display = "block";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Sign In";
  }
});

// Sign Up form submission
signUpForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  signUpError.style.display = "none";

  const username = document.getElementById("signUpUsername").value.trim();
  const displayName = document.getElementById("signUpDisplayName").value.trim();
  const password = document.getElementById("signUpPassword").value;

  if (!username || !password) {
    signUpError.textContent = "Please fill in all required fields.";
    signUpError.style.display = "block";
    return;
  }

  if (username.length < 3) {
    signUpError.textContent = "Username must be at least 3 characters.";
    signUpError.style.display = "block";
    return;
  }

  if (password.length < 4) {
    signUpError.textContent = "Password must be at least 4 characters.";
    signUpError.style.display = "block";
    return;
  }

  const submitBtn = signUpForm.querySelector(".auth-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating account...";

  try {
    await signUp(username, password, displayName);
    hideAuthModal();
    updateAuthUI();
    addMessage(`Welcome, ${getUser().display_name || getUser().username}! Your account has been created.`, "ai");
    // Load user's conversations after sign up
    await loadAndRestoreConversation();
  } catch (err) {
    signUpError.textContent = err.message;
    signUpError.style.display = "block";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create Account";
  }
});

// Sign Out
signOutBtn.addEventListener("click", () => {
  authSignOut();
  updateAuthUI();
  addMessage("You have been signed out.", "ai");
  // Clear conversation state
  _currentConversationId = null;
  setLastConversationId(null);
  messagesDiv.innerHTML = '';
  addMessage('Hello. I am your local AI assistant.', 'ai');
  renderConversationList([]);
});

// New Chat button
if (newChatBtn) {
  newChatBtn.addEventListener('click', startNewConversation);
}

// ── Load and Restore Conversation ──────────────────────────────────────────

/**
 * Load conversations and restore the last active conversation.
 * Called on startup and after sign-in/sign-up.
 */
async function loadAndRestoreConversation() {
  const conversations = await loadConversations();

  // Try to restore the last conversation ID from localStorage
  let targetConvId = getLastConversationId();

  // If no stored ID, use the most recent conversation
  if (!targetConvId && conversations.length > 0) {
    targetConvId = conversations[0].id;
  }

  // If we have a target conversation, load its messages
  if (targetConvId) {
    // Check if the conversation still exists in the list
    const exists = conversations.some(c => c.id === targetConvId);
    if (exists) {
      await switchConversation(targetConvId);
    } else {
      // Conversation was deleted, start fresh
      startNewConversation();
    }
  } else {
    // No conversations exist, show welcome
    messagesDiv.innerHTML = '';
    addMessage('Hello. I am your local AI assistant.', 'ai');
  }
}

// ── Initialize on Startup ──────────────────────────────────────────────────

(async function initWithAuth() {
  try {
    // Check auth state
    const authed = await initAuth();
    updateAuthUI(authed);

    if (authed) {
      console.log("[Auth] User is signed in:", getUser().username);
    } else {
      console.log("[Auth] User is not signed in");
    }

    const health = await checkHealth();
    console.log("Backend connected:", health);
    addMessage(`System ready. Connected to ${health.services.llm} backend.`, "ai");

    // Load conversations and restore the last active one
    await loadAndRestoreConversation();

  } catch (err) {
    console.warn("Backend not reachable on startup:", err.message);
  }
})();

// Expose functions to window for HTML event handlers
window.togglePlayback = togglePlayback;
window.toggleRecording = toggleRecording;
window.sendMessage = sendMessage;