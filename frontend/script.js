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

function clearVisualizer() {
  ctx.clearRect(0,0,canvas.width,canvas.height);
}

clearVisualizer();

const MOUTHS = [
`<path d="M122,210 C129,206 135,207 140,209 C145,207 151,206 158,210 C151,213 140,213 129,213 Z" fill="#C06868"/>`,
`<ellipse cx="140" cy="212" rx="17" ry="2.5" fill="#2C0808"/>`,
`<path d="M122,211 Q140,213 158,211 L158,215 Q140,213 122,215 Z" fill="#2A0808"/>`,
`<path d="M119,208 Q140,211 161,208 L161,221 Q140,218 119,221 Z" fill="#2A0808"/>`,
`<ellipse cx="140" cy="213" rx="10" ry="10" fill="#2A0808"/>`,
`<rect x="116" y="211" width="48" height="4" rx="1.5" fill="#F2EEE8"/>`,
`<path d="M122,211 Q140,213 158,211 L158,215 Q140,213 122,215 Z" fill="#2A0808"/>`,
`<path d="M124,212 Q140,213 156,212 L156,213 Q140,214 124,213 Z" fill="#340A0A"/>`
];

function buildSVG(mi) {
return `
<svg viewBox="0 0 280 360" xmlns="http://www.w3.org/2000/svg">
<rect width="280" height="360" fill="#BFD0E0"/>
<path d="M-5,360 L-5,298 C16,277 50,262 90,253 L118,247 L140,253 L162,247 C210,262 244,277 285,298 L285,360 Z" fill="#222232"/>
<path d="M120,247 L140,253 L160,247 L156,360 L124,360 Z" fill="#F2F2F2"/>
<path d="M120,244 Q117,279 121,285 Q130,293 140,293 Q150,293 159,285 Q163,279 160,244 Q152,237 140,237 Q128,237 120,244 Z" fill="#D08860"/>
<ellipse cx="140" cy="159" rx="73" ry="94" fill="#D49068"/>
<path d="M70,149 Q67,114 82,86 Q108,47 140,43 Q172,47 198,86 Q213,114 210,149" fill="#180A04"/>
<path d="M70,149 Q63,178 66,202" stroke="#160802" stroke-width="22" fill="none" stroke-linecap="round"/>
<path d="M210,149 Q217,178 214,202" stroke="#160802" stroke-width="22" fill="none" stroke-linecap="round"/>
<ellipse cx="112" cy="157" rx="17" ry="10" fill="#F8F5F2"/>
<ellipse cx="168" cy="157" rx="17" ry="10" fill="#F8F5F2"/>
<circle cx="112" cy="157" r="8" fill="#3C2512"/>
<circle cx="168" cy="157" r="8" fill="#3C2512"/>
<circle cx="112" cy="157" r="4" fill="#080404"/>
<circle cx="168" cy="157" r="4" fill="#080404"/>
${MOUTHS[mi]}
</svg>
`;
}

const preview = document.getElementById("preview");

let currentFrame = 0;
let talkingInterval = null;

function setIdle() {
  preview.innerHTML = buildSVG(0);
}

function startTalkingAnimation() {

  stopTalkingAnimation();

  talkingInterval = setInterval(() => {

    currentFrame = (currentFrame + 1) % 8;

    preview.innerHTML = buildSVG(currentFrame);

  }, 120);
}

function stopTalkingAnimation() {

  clearInterval(talkingInterval);

  currentFrame = 0;

  setIdle();
}

setIdle();

function addMessage(text, type) {

  const div = document.createElement("div");

  div.className = `message ${type}`;

  div.textContent = text;

  messagesDiv.appendChild(div);

  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function drawVisualizer(dataArray) {

  ctx.clearRect(0,0,canvas.width,canvas.height);

  const bars = 48;
  const spacing = canvas.width / bars;
  const centerY = canvas.height / 2;

  ctx.fillStyle = "white";

  for (let i = 0; i < bars; i++) {

    const value = dataArray[i] || 0;

    const height = Math.max(12, value * 2.2);

    const x = i * spacing;

    ctx.fillRect(
      x,
      centerY - height / 2,
      10,
      height
    );
  }
}

async function sendMessage() {

  const message = input.value.trim();

  if (!message) return;

  addMessage(message, "user");

  input.value = "";

  typing.style.display = "block";

  try {

    const response = await fetch(
      "http://127.0.0.1:8000/chat",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: message
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
          message: text
        })
      }
    );

    const audioBlob = await response.blob();

    const audioUrl = URL.createObjectURL(audioBlob);

    const audio = new Audio(audioUrl);

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

    startTalkingAnimation();

    function animate() {

      if (audio.paused || audio.ended) {

        clearVisualizer();

        stopTalkingAnimation();

        return;
      }

      analyser.getByteFrequencyData(dataArray);

      drawVisualizer(dataArray);

      requestAnimationFrame(animate);
    }

    audio.onplay = () => {
      animate();
    };

    audio.onended = () => {

      clearVisualizer();

      stopTalkingAnimation();

      audioContext.close();
    };

    await audio.play();

  } catch (err) {

    console.error(err);

    clearVisualizer();

    stopTalkingAnimation();
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

    typing.style.display = "block";

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

  isRecording = true;

  recordBtn.classList.add("recording");
}

function stopRecording() {

  mediaRecorder.stop();

  isRecording = false;

  recordBtn.classList.remove("recording");
}

input.addEventListener("keydown", function(event) {

  if (event.key === "Enter") {
    sendMessage();
  }
});
