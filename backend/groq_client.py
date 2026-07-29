"""
Groq API client for MyAgent.
Uses Groq's LLM and vision models for chat with optional image support.
"""
import os
import base64
import re
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_CHAT_MODEL = "qwen/qwen3.6-27b"
_client = None
_THINKING_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove model reasoning blocks from user-visible responses."""
    return _THINKING_RE.sub("", text or "").strip()

def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client

def groq_chat(messages, model=DEFAULT_CHAT_MODEL, temperature=0.7, max_tokens=4096):
    """Send a chat completion request to Groq."""
    print("=" * 60)
    print(f"[GROQ] Chat completion request")
    print(f"[GROQ]   Model: {model}")
    print(f"[GROQ]   Messages: {len(messages)}")
    print(f"[GROQ]   Last message length: {len(messages[-1]['content']) if messages else 0} chars")
    print("=" * 60)
    
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    content = strip_thinking(response.choices[0].message.content)
    print(f"[GROQ] ✅ Response received ({len(content)} chars)")
    print(f"[GROQ]   Preview: {content[:200]}...")
    print("=" * 60)
    return content

def groq_vision(image_base64, prompt, model=DEFAULT_CHAT_MODEL, mime_type="image/jpeg"):
    """Send an image with a text prompt to Groq's vision model."""
    print("=" * 60)
    print(f"[GROQ] Vision request")
    print(f"[GROQ]   Model: {model}")
    print(f"[GROQ]   Image base64 length: {len(image_base64)} chars")
    print(f"[GROQ]   Prompt: '{prompt[:100]}...'")
    print("=" * 60)
    
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.5,
        max_tokens=1024,
    )
    
    content = strip_thinking(response.choices[0].message.content)
    print(f"[GROQ] ✅ Vision response received ({len(content)} chars)")
    print(f"[GROQ]   Preview: {content[:200]}...")
    print("=" * 60)
    return content
