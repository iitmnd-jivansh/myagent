from faster_whisper import WhisperModel

print("Loading Whisper...")

model = WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded.")


def transcribe_audio(
    audio_path,
    language="en"
):

    print(
        f"Transcribing ({language})..."
    )

    segments, info = model.transcribe(
        audio_path,
        language=language
    )

    text = ""

    for segment in segments:
        text += segment.text + " "

    result = text.strip()

    print("Transcript:", result)

    return result