import os
import requests

print("ElevenLabs TTS ready.")

# Put your key in environment:
# export ELEVENLABS_API_KEY="your_key"

API_KEY = "sk_9d0a2cb939781f1386b8ebb468095d2f70a44534ad46f024" 

# Change to your preferred voice
VOICE_ID = "CwhRBWXzGAHq8TQ4Fs17"  # Bella

MODEL_ID = "eleven_multilingual_v2"

def generate_speech(
    text,
    language="en",
    output_path="response.mp3"
):

    print(
        f"Generating speech ({language})..."
    )

    if not API_KEY:
        raise ValueError(
            "ELEVENLABS_API_KEY not set"
        )

    url = (
        f"https://api.elevenlabs.io/"
        f"v1/text-to-speech/{VOICE_ID}"
    )

    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=60
    )

    print("Status:", response.status_code)

    response.raise_for_status()

    with open(
        output_path,
        "wb"
    ) as f:
        f.write(response.content)

    print("Speech generated.")

    return output_path

