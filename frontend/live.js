const btn = document.getElementById("connectBtn");
const statusEl = document.getElementById("status");
const visualizer = document.getElementById("visualizer");

let socket;
let audioContext;
let processor;
let source;
let isConnected = false;

// Queue timing for seamless audio playback
let nextStartTime = 0;

btn.addEventListener("click", async () => {
    if (isConnected) {
        disconnect();
        return;
    }

    statusEl.textContent = "Connecting...";
    statusEl.className = "status-badge connecting";

    try {
        socket = new WebSocket(`ws://${window.location.host}/ws/live`);
        socket.binaryType = "arraybuffer";

        socket.onopen = async () => {
            isConnected = true;
            statusEl.textContent = "Connected";
            statusEl.className = "status-badge connected";
            btn.querySelector('.btn-text').textContent = "Disconnect";
            visualizer.classList.add("active");

            if (audioContext) {
                nextStartTime = audioContext.currentTime;
            }
            
            await startMicrophone();
        };

        socket.onmessage = async (event) => {
            playPCM(event.data);
        };

        socket.onclose = () => {
            disconnect();
        };

        socket.onerror = (err) => {
            console.error("WebSocket error:", err);
            statusEl.textContent = "Error connecting";
            statusEl.className = "status-badge disconnected";
            disconnect();
        };

    } catch (e) {
        console.error(e);
        statusEl.textContent = "Error";
        statusEl.className = "status-badge disconnected";
    }
});

function disconnect() {
    isConnected = false;
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }
    
    if (processor) {
        processor.disconnect();
        processor = null;
    }
    
    if (source) {
        source.disconnect();
        source = null;
    }
    
    statusEl.textContent = "Disconnected";
    statusEl.className = "status-badge disconnected";
    btn.querySelector('.btn-text').textContent = "Connect & Start Talking";
    visualizer.classList.remove("active");
}

async function startMicrophone() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 16000
            }
        });

        audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000
        });
        
        nextStartTime = audioContext.currentTime;

        source = audioContext.createMediaStreamSource(stream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);

        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (event) => {
            if (!isConnected || socket.readyState !== WebSocket.OPEN) return;

            const input = event.inputBuffer.getChannelData(0);
            const pcm = convertFloat32ToInt16(input);

            // Using the same JSON structure as before to remain compatible with backend logic
            socket.send(
                JSON.stringify({
                    type: "audio",
                    data: Array.from(new Uint8Array(pcm.buffer))
                })
            );
        };
    } catch (e) {
        console.error("Microphone access denied or error:", e);
        disconnect();
    }
}

function convertFloat32ToInt16(buffer) {
    const l = buffer.length;
    const out = new Int16Array(l);
    for (let i = 0; i < l; i++) {
        let s = Math.max(-1, Math.min(1, buffer[i]));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
}

function playPCM(arrayBuffer) {
    if (!audioContext) return;

    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);

    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
    }

    // Gemini Live audio is returned at 24kHz
    const buffer = audioContext.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const src = audioContext.createBufferSource();
    src.buffer = buffer;
    src.connect(audioContext.destination);

    // Queue audio to prevent overlap
    if (nextStartTime < audioContext.currentTime) {
        nextStartTime = audioContext.currentTime;
    }

    src.start(nextStartTime);
    nextStartTime += buffer.duration;
}
