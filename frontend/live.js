/**
 * LiveKit Live Page – Frontend Logic
 *
 * Connects to a LiveKit room via the livekit-client SDK (loaded from CDN).
 * Publishes the user's microphone audio and plays back the agent's audio.
 * Handles transcription display and audio visualization.
 */

// ── DOM Elements ──────────────────────────────────────────────────────────

const connectBtn = document.getElementById("connectBtn");
const btnText = connectBtn.querySelector(".btn-text");
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const orbContainer = document.getElementById("orbContainer");
const orbCore = document.getElementById("orbCore");
const glassContainer = document.getElementById("glassContainer");
const transcriptPanel = document.getElementById("transcriptPanel");
const transcriptEmpty = document.getElementById("transcriptEmpty");

// ── LiveKit SDK (from global UMD namespace) ───────────────────────────────

const { Room, RoomEvent, Track, DisconnectReason } = LivekitClient;

// ── State ─────────────────────────────────────────────────────────────────

let room = null;
let isConnected = false;
let audioContext = null;
let analyser = null;
let animationId = null;

// ── Connect / Disconnect ──────────────────────────────────────────────────

connectBtn.addEventListener("click", async () => {
    if (isConnected) {
        disconnect();
        return;
    }
    await connect();
});

async function connect() {
    setStatus("connecting", "Connecting...");

    try {
        // 1. Get token from our backend
        const res = await fetch("/livekit/token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                room_name: "myagent-room",
                identity: "user-" + Math.random().toString(36).substring(2, 8),
            }),
        });

        const data = await res.json();

        if (data.error) {
            setStatus("disconnected", "Config Error");
            console.error("Token error:", data.error);
            return;
        }

        // 2. Create and configure the Room
        room = new Room({
            adaptiveStream: true,
            dynacast: true,
            audioCaptureDefaults: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            },
        });

        // 3. Set up event handlers
        setupRoomEvents(room);

        // 4. Connect to LiveKit
        await room.connect(data.url, data.token);

        // 5. Publish microphone
        await room.localParticipant.setMicrophoneEnabled(true);

        // 6. Update UI
        isConnected = true;
        setStatus("connected", "Connected");
        connectBtn.classList.add("connected");
        btnText.textContent = "Disconnect";
        orbContainer.classList.add("active");
        glassContainer.classList.add("active");

        // 7. Start audio context for visualization
        setupAudioContext();

    } catch (err) {
        console.error("Connection failed:", err);
        setStatus("disconnected", "Connection Failed");
        disconnect();
    }
}

function disconnect() {
    if (room) {
        room.disconnect();
        room = null;
    }

    isConnected = false;
    setStatus("disconnected", "Disconnected");
    connectBtn.classList.remove("connected");
    btnText.textContent = "Connect & Talk";
    orbContainer.classList.remove("active", "speaking");
    glassContainer.classList.remove("active");

    // Stop visualization
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
    if (audioContext) {
        audioContext.close().catch(() => {});
        audioContext = null;
        analyser = null;
    }
}

// ── Room Event Handlers ───────────────────────────────────────────────────

function setupRoomEvents(room) {
    // Agent audio track subscribed → play it and visualize
    room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
            console.log(`Audio track subscribed from: ${participant.identity}`);

            // Attach the audio element to the DOM for playback
            const audioEl = track.attach();
            audioEl.id = "agent-audio-" + participant.identity;
            audioEl.style.display = "none";
            document.body.appendChild(audioEl);

            // Set up visualization for agent audio
            connectAnalyser(audioEl);

            // Visual feedback: agent is speaking
            orbContainer.classList.add("speaking");
        }
    });

    // Agent audio track unsubscribed → cleanup
    room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
            const elements = track.detach();
            elements.forEach((el) => el.remove());
            orbContainer.classList.remove("speaking");
        }
    });

    // Active speaker changes → visual feedback
    room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentSpeaking = speakers.some(
            (s) => s.identity !== room.localParticipant.identity
        );
        if (agentSpeaking) {
            orbContainer.classList.add("speaking");
        } else {
            orbContainer.classList.remove("speaking");
        }
    });

    // Data messages (e.g. transcriptions from agent)
    room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
        try {
            const decoder = new TextDecoder();
            const text = decoder.decode(payload);
            const msg = JSON.parse(text);

            if (msg.type === "transcription" || msg.type === "transcript") {
                addTranscript(msg.role || "agent", msg.text || msg.content || "");
            }
        } catch (e) {
            // Not JSON or not a transcription, ignore
        }
    });

    // Transcription events from LiveKit's built-in transcription system
    room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        for (const segment of segments) {
            if (segment.final) {
                const role = participant.identity === room.localParticipant.identity
                    ? "user"
                    : "agent";
                addTranscript(role, segment.text);
            }
        }
    });

    // Participant disconnected
    room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        console.log(`Participant disconnected: ${participant.identity}`);
        // Cleanup any audio elements
        const audioEl = document.getElementById("agent-audio-" + participant.identity);
        if (audioEl) audioEl.remove();
    });

    // Room disconnected
    room.on(RoomEvent.Disconnected, (reason) => {
        console.log("Room disconnected:", reason);
        disconnect();
    });

    // Connection quality feedback
    room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
        if (participant.identity === room.localParticipant.identity) {
            console.log("Connection quality:", quality);
        }
    });
}

// ── Audio Visualization ───────────────────────────────────────────────────

function setupAudioContext() {
    if (audioContext) return;
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    audioContext.resume();
}

function connectAnalyser(audioElement) {
    if (!audioContext) setupAudioContext();

    try {
        const source = audioContext.createMediaElementSource(audioElement);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 64;
        analyser.smoothingTimeConstant = 0.8;

        source.connect(analyser);
        analyser.connect(audioContext.destination);

        startVisualization();
    } catch (e) {
        console.warn("Could not set up audio analyser:", e);
    }
}

function startVisualization() {
    if (!analyser) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    function animate() {
        animationId = requestAnimationFrame(animate);

        analyser.getByteFrequencyData(dataArray);

        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        const normalizedVolume = Math.min(avg / 128, 1);

        // Scale the orb based on volume
        const scale = 1 + normalizedVolume * 0.3;
        const glow = 30 + normalizedVolume * 50;
        orbCore.style.transform = `scale(${scale})`;
        orbCore.style.boxShadow = `0 0 ${glow}px rgba(139, 92, 246, ${0.3 + normalizedVolume * 0.4})`;
    }

    animate();
}

// ── Transcript Panel ──────────────────────────────────────────────────────

function addTranscript(role, text) {
    if (!text || text.trim() === "") return;

    // Remove empty state message
    if (transcriptEmpty) {
        transcriptEmpty.style.display = "none";
    }

    const entry = document.createElement("div");
    entry.className = `transcript-entry ${role}`;
    entry.textContent = text;
    transcriptPanel.appendChild(entry);

    // Auto-scroll to bottom
    transcriptPanel.scrollTop = transcriptPanel.scrollHeight;

    // Keep transcript manageable (max 50 entries)
    const entries = transcriptPanel.querySelectorAll(".transcript-entry");
    if (entries.length > 50) {
        entries[0].remove();
    }
}

// ── Status Helper ─────────────────────────────────────────────────────────

function setStatus(state, text) {
    statusBadge.className = `status-badge ${state}`;
    statusText.textContent = text;
}
