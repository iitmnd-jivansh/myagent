import requests

print("Cartesia TTS ready.")

API_KEY = "sk_car_otVbvKUku6Hhq1bg4EnxRA"

# Hindi-capable voice
VOICE_ID = "86e30c1d-714b-4074-a1f2-1cb6b552fb49"

MODEL_ID = "sonic-2"

def generate_speech(
    text,
    language="hi",
    output_path="response.wav"
):
    print(f"Generating speech ({language})...")

    if not API_KEY:
        raise ValueError("CARTESIA_API_KEY not set")

    url = "https://api.cartesia.ai/tts/bytes"

    headers = {
        "Cartesia-Version": "2025-04-16",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "model_id": MODEL_ID,
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": VOICE_ID
        },
        "language": language,
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 24000
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=60
    )

    print("Status:", response.status_code)

    if not response.ok:
        try:
            error_text = response.json()
        except Exception:
            error_text = response.text

        raise RuntimeError(
            f"Cartesia API Error {response.status_code}: {error_text}"
        )

    with open(output_path, "wb") as f:
        f.write(response.content)

    print("Speech generated.")

    return output_path
