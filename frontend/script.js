const messagesDiv = document.getElementById("messages");
const input = document.getElementById("messageInput");
const typing = document.getElementById("typing");
const recordBtn = document.getElementById("recordBtn");

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

// ─── Agent state ────────────────────────────────────────────────────────────

function setAgentState(state) {

  const el = document.getElementById("agentState");

  if (!el) return;

  switch (state) {

    case "idle":
      el.innerHTML = "🟢 Idle";
      break;

    case "listening":
      el.innerHTML = "🎤 Listening";
      break;

    case "thinking":
      el.innerHTML = "🧠 Thinking";
      break;

    case "speaking":
      el.innerHTML = "🔊 Speaking";
      break;
  }
}

setAgentState("idle");

// ─── Language toggle ─────────────────────────────────────────────────────────

const englishBtn = document.getElementById("englishBtn");
const hindiBtn   = document.getElementById("hindiBtn");

if (englishBtn && hindiBtn) {

  englishBtn.addEventListener("click", () => {
    currentLanguage = "en";
    englishBtn.classList.add("active");
    hindiBtn.classList.remove("active");
    input.placeholder = "Ask something...";
  });

  hindiBtn.addEventListener("click", () => {
    currentLanguage = "hi";
    hindiBtn.classList.add("active");
    englishBtn.classList.remove("active");
    input.placeholder = "कुछ पूछें...";
  });
}

// ─── Chat messages ───────────────────────────────────────────────────────────

function addMessage(text, type) {

  const div = document.createElement("div");

  div.className = `message ${type}`;

  div.textContent = text;

  messagesDiv.appendChild(div);

  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ─── TTS visualizer ──────────────────────────────────────────────────────────

function drawVisualizer(dataArray) {

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const bars    = Math.max(14, Math.floor(canvas.width / 12));
  const centerY = canvas.height / 2;
  const spacing = canvas.width / bars;
  const barWidth = Math.max(3, spacing * 0.65);

  ctx.fillStyle = "white";

  for (let i = 0; i < bars; i++) {

    const sourceIndex = Math.floor(i * dataArray.length / bars);
    const value       = dataArray[sourceIndex] || 0;
    const height      = Math.max(4, value * 0.75);
    const x           = i * spacing;

    ctx.fillRect(x, centerY - height / 2, barWidth, height);
  }
}

// ─── Send message ────────────────────────────────────────────────────────────

async function sendMessage() {

  const message = input.value.trim();

  if (!message) return;

  addMessage(message, "user");

  input.value = "";

  typing.style.display = "block";
  setAgentState("thinking");

  try {

    const response = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, language: currentLanguage })
    });

    const data = await response.json();

    typing.style.display = "none";

    addMessage(data.response, "ai");

    speakResponse(data.response);

  } catch (error) {

    typing.style.display = "none";

    addMessage("Could not connect to backend.", "ai");

    console.error(error);
  }
}

// ─── Speak / TTS playback ────────────────────────────────────────────────────

async function speakResponse(text) {

  try {

    const response = await fetch("http://127.0.0.1:8000/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, language: currentLanguage })
    });

    const audioBlob = await response.blob();
    const audioUrl  = URL.createObjectURL(audioBlob);
    const audio     = new Audio(audioUrl);

    audio.crossOrigin = "anonymous";

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    await audioContext.resume();

    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;

    const source = audioContext.createMediaElementSource(audio);
    source.connect(analyser);
    analyser.connect(audioContext.destination);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    // Start Kei talking animation (implemented in kei.js)
    window.keiAvatar?.startTalking();

    function animate() {

      if (audio.paused || audio.ended) {
        clearVisualizer();
        // Stop Kei talking animation
        window.keiAvatar?.stopTalking();
        return;
      }

      analyser.getByteFrequencyData(dataArray);
      drawVisualizer(dataArray);
      requestAnimationFrame(animate);
    }

    audio.onplay = () => {
      setAgentState("speaking");
      animate();
    };

    audio.onended = () => {
      setAgentState("idle");
      clearVisualizer();
      // Stop Kei talking animation
      window.keiAvatar?.stopTalking();
      audioContext.close();
    };

    await audio.play();

  } catch (err) {

    setAgentState("idle");
    clearVisualizer();
    // Ensure animation stops on error too
    window.keiAvatar?.stopTalking();
    console.error(err);
  }
}

// ─── Voice recording ─────────────────────────────────────────────────────────

async function toggleRecording() {
  if (!isRecording) {
    startRecording();
  } else {
    stopRecording();
  }
}

async function startRecording() {

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  mediaRecorder = new MediaRecorder(stream);
  audioChunks   = [];

  mediaRecorder.ondataavailable = event => {
    audioChunks.push(event.data);
  };

  mediaRecorder.onstop = async () => {

    const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
    const formData  = new FormData();

    formData.append("file",     audioBlob, "recording.wav");
    formData.append("language", currentLanguage);

    typing.style.display = "block";
    setAgentState("thinking");

    const response = await fetch("http://127.0.0.1:8000/transcribe", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    typing.style.display = "none";

    input.value = data.text;
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

// ─── Live2D / Kei initialisation ─────────────────────────────────────────────
//
//  avatar.js is gone.  All avatar work now lives in kei.js which exposes:
//
//    initializeKei()              — mounts Cubism SDK onto #live2dCanvas
//                                   and sets window.keiAvatar
//
//    window.keiAvatar = {
//      startTalking()             — lip-sync / talking expression
//      stopTalking()              — return to idle expression
//      setExpression(name)        — e.g. "thinking", "happy"  [TODO in kei.js]
//    }
//
//  setKeiState(state) helper (defined in kei.js):
//    setKeiState("idle")          — neutral idle motion loop
//    setKeiState("thinking")      — thinking expression / motion
//    setKeiState("speaking")      — driven by startTalking / stopTalking

async function loadLive2D() {

  // Delegate fully to kei.js once it is implemented.
  // initializeKei() will load the model JSON, set up the Cubism renderer,
  // run the idle motion loop, and assign window.keiAvatar.

  if (typeof initializeKei === "function") {
    await initializeKei();
  } else {
    console.warn(
      "loadLive2D: initializeKei() not found — " +
      "make sure kei.js is loaded before script.js."
    );
  }
}

// ─── Keyboard shortcut ───────────────────────────────────────────────────────

input.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    sendMessage();
  }
});

// ─── Boot ────────────────────────────────────────────────────────────────────

loadLive2D();