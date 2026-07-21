import { avatar } from './avatar/avatar.js';
import { checkHealth, sendChatMessage, generateSpeech, transcribeAudio } from './api.js';

const messagesDiv = document.getElementById("messages");
const input = document.getElementById("messageInput");
const typing = document.getElementById("typing");
const recordBtn = document.getElementById("recordBtn");
const playbackBtn = document.getElementById("playbackBtn");

let currentAudio = null;

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

avatar.init('avatarContainer');
avatar.load('avatar/assistant.vrm', 'models/idle.vrma', 'models/talking.vrma')
    .then(() => console.log('Avatar loaded successfully'))
    .catch(err => console.error('Failed to load avatar:', err));

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

    const data = await sendChatMessage(message, currentLanguage);

    typing.style.display = "none";

    addMessage(data.response, "ai");

    // Render GenUI card if present in response
    if (data.ui) {
      renderGenUICard(data.ui);
    }

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
    sendMessage();
  }
});

// Check backend health on startup
(async function init() {
  try {
    const health = await checkHealth();
    console.log("Backend connected:", health);
    addMessage(`System ready. Connected to ${health.services.llm} backend.`, "ai");
  } catch (err) {
    console.warn("Backend not reachable on startup:", err.message);
  }
})();

// Expose functions to window for HTML event handlers
window.togglePlayback = togglePlayback;
window.toggleRecording = toggleRecording;
window.sendMessage = sendMessage;