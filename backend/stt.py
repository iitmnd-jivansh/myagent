from faster_whisper import WhisperModel

model = None

def get_model():
    global model
    if model is None:
        print("─" * 50)
        print("[STT] Loading Whisper model 'medium' (CPU, int8)...")
        print("[STT]   This may take a few seconds on first load...")
        model = WhisperModel(
            "medium",
            device="cpu",
            compute_type="int8"
        )
        print("[STT] ✅ Whisper model 'medium' loaded successfully on CPU.")
        print("─" * 50)
    return model


def transcribe_audio(
    audio_path,
    language="en"
):
    print("─" * 50)
    print(f"[STT] Transcribe request received")
    print(f"[STT]   Audio file: '{audio_path}'")
    print(f"[STT]   Language: '{language}'")
    print(f"[STT]   Loading Whisper model...")

    m = get_model()

    print(f"[STT]   Starting transcription with faster-whisper...")
    print(f"[STT]   Model: medium | Device: CPU | Compute: int8")

    segments, info = m.transcribe(
        audio_path,
        language=language
    )

    print(f"[STT]   Audio duration: {info.duration:.2f}s")
    print(f"[STT]   Detected language: {info.language} (probability: {info.language_probability:.2%})")
    print(f"[STT]   Input audio info:")
    print(f"[STT]     - Sample rate: {info.sample_rate} Hz")
    print(f"[STT]     - Duration: {info.duration:.2f} seconds")
    print(f"[STT]   Processing segments...")

    text = ""
    segment_count = 0

    for segment in segments:
        segment_count += 1
        text += segment.text + " "
        print(f"[STT]   Segment {segment_count}: [{segment.start:.2f}s -> {segment.end:.2f}s] \"{segment.text.strip()}\"")

    result = text.strip()
    print(f"[STT]   Total segments processed: {segment_count}")
    print(f"[STT]   Final transcript ({len(result.split())} words):")
    print(f"[STT]   \"{result}\"")
    print(f"[STT] ✅ Transcription complete.")
    print("─" * 50)

    return result