"""Cartesia text-to-speech client."""

import os
from pathlib import Path

import requests


VOICE_ID = "86e30c1d-714b-4074-a1f2-1cb6b552fb49"
MODEL_ID = "sonic-2"
CARTESIA_TTS_URL = "https://api.cartesia.ai/tts/bytes"


def generate_speech(text: str, language: str = "hi", output_path: str = "response.wav") -> str:
    """Generate a WAV file with Cartesia and return its path."""
    api_key = os.getenv("CARTESIA_API_KEY")
    if not api_key:
        raise ValueError("CARTESIA_API_KEY is not set")

    response = requests.post(
        CARTESIA_TTS_URL,
        json={
            "model_id": MODEL_ID,
            "transcript": text,
            "voice": {"mode": "id", "id": VOICE_ID},
            "language": language,
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            },
        },
        headers={
            "Cartesia-Version": "2025-04-16",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(f"Cartesia API error {response.status_code}: {response.text}")

    Path(output_path).write_bytes(response.content)
    return output_path
