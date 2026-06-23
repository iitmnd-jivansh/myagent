from faster_whisper import WhisperModel

model = None

def get_model():
    global model
    if model is None:
        print("Loading Whisper...")
        model = WhisperModel(
            "medium",
            device="cpu",
            compute_type="int8"
        )
        print("Whisper loaded.")
    return model


def transcribe_audio(
    audio_path,
    language="en"
):

    print(
        f"Transcribing ({language})..."
    )

    m = get_model()

    segments, info = m.transcribe(
        audio_path,
        language=language
    )

    text = ""

    for segment in segments:
        text += segment.text + " "

    result = text.strip()

    print("Transcript:", result)

    return result