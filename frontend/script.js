import { avatar } from './avatar/avatar.js';

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

    const response = await fetch(
      "http://127.0.0.1:8000/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: message,
          language: currentLanguage
        })
      }
    );

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

async function speakResponse(text) {

  try {

    const response = await fetch(
      "http://127.0.0.1:8000/speak",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: text,
          language: currentLanguage
        })
      }
    );

    const audioBlob = await response.blob();

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

    const formData = new FormData();

    formData.append(
      "file",
      audioBlob,
      "recording.wav"
    );

    formData.append(
      "language",
      currentLanguage
    );

    typing.style.display = "block";
    setAgentState("thinking");

    const response = await fetch(
      "http://127.0.0.1:8000/transcribe",
      {
        method: "POST",
        body: formData
      }
    );

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

input.addEventListener("keydown", function (event) {

  if (event.key === "Enter") {
    sendMessage();
  }
});

// Expose functions to window for HTML event handlers
window.togglePlayback = togglePlayback;
window.toggleRecording = toggleRecording;
window.sendMessage = sendMessage;