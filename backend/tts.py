import requests

print("─" * 50)
print("[TTS] Cartesia TTS module loaded.")
print("[TTS]   Voice ID: 86e30c1d-714b-4074-a1f2-1cb6b552fb49")
print("[TTS]   Model: sonic-2")
print("─" * 50)

API_KEY = "sk_car_otVbvKUku6Hhq1bg4EnxRA"

# Hindi-capable voice
VOICE_ID = "86e30c1d-714b-4074-a1f2-1cb6b552fb49"

MODEL_ID = "sonic-2"

def generate_speech(
    text,
    language="hi",
    output_path="response.wav"
):
    print("─" * 50)
    print(f"[TTS] Speech generation request received")
    print(f"[TTS]   Text length: {len(text)} chars")
    print(f"[TTS]   Text preview: \"{text[:100]}...\"")
    print(f"[TTS]   Language: '{language}'")
    print(f"[TTS]   Output file: '{output_path}'")
    print(f"[TTS]   Voice ID: {VOICE_ID}")
    print(f"[TTS]   Model: {MODEL_ID}")
    print("─" * 50)

    if not API_KEY:
        print("[TTS] ❌ ERROR: CARTESIA_API_KEY not set!")
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

    print(f"[TTS]   Sending request to Cartesia API...")
    print(f"[TTS]   URL: {url}")
    print(f"[TTS]   Payload model: {payload['model_id']}, voice: {payload['voice']['id']}, lang: {payload['language']}")

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=60
    )

    print(f"[TTS]   Cartesia API response status: {response.status_code}")
    print(f"[TTS]   Response headers: {dict(response.headers)}")

    if not response.ok:
        try:
            error_text = response.json()
        except Exception:
            error_text = response.text
        print(f"[TTS] ❌ Cartesia API Error {response.status_code}: {error_text}")
        raise RuntimeError(
            f"Cartesia API Error {response.status_code}: {error_text}"
        )

    print(f"[TTS]   Audio data received: {len(response.content)} bytes")

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"[TTS] ✅ Speech audio written to '{output_path}' ({len(response.content)} bytes)")
    print(f"[TTS]   Output format: WAV (PCM s16le, 24kHz)")
    print("─" * 50)

    return output_path