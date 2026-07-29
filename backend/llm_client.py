"""
Unified LLM Client for MyAgent.

Provides a common interface for multiple LLM providers:
  - Groq (via groq library)
  - OpenAI-compatible (OpenAI, together, deepseek, etc.)
  - Anthropic (via anthropic library)
  - Google Gemini (via google-genai library)

Users can configure which provider and API key to use via the user_preferences
table (llm_provider, llm_api_key). Falls back to the default Groq + .env key.
"""

import os
import json
import re
from typing import Optional

from database import get_preference

_THINKING_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

# Env var keys for each provider
_ENV_KEY_MAP = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Base URLs for providers that use OpenAI-compatible API
_OPENAI_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com",
}

# Default models per provider
_DEFAULT_MODELS = {
    "groq": "qwen/qwen3.6-27b",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "gemini": "gemini-2.0-flash-lite",
}


def strip_thinking(text: str) -> str:
    """Remove model reasoning blocks from user-visible responses."""
    return _THINKING_RE.sub("", text or "").strip()


def _get_api_key(provider: str) -> Optional[str]:
    """
    Resolve the API key for a provider.
    Priority: user_preference (llm_api_key) > env var > None
    """
    # Check user preference first
    pref_key = get_preference("llm_api_key", None)
    if pref_key:
        return pref_key

    # Fall back to environment variable
    env_key = _ENV_KEY_MAP.get(provider)
    if env_key:
        return os.getenv(env_key, None)

    return None


def _build_system_prompt(language: str = "en") -> str:
    """Build the system prompt including language instruction."""
    if language == "hi":
        return "You are a helpful AI assistant. Answer only in Hindi."
    return "You are a helpful AI assistant. Answer only in English."


def _groq_chat(messages: list, model: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Call Groq API."""
    from groq import Groq

    api_key = _get_api_key("groq")
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return strip_thinking(response.choices[0].message.content)


def _groq_vision(image_base64: str, prompt: str, model: str, mime_type: str = "image/jpeg") -> str:
    """Call Groq vision model."""
    from groq import Groq

    api_key = _get_api_key("groq")
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    client = Groq(api_key=api_key)
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
    return strip_thinking(response.choices[0].message.content)


def _openai_chat(messages: list, model: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Call OpenAI-compatible API."""
    from openai import OpenAI

    api_key = _get_api_key("openai")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _anthropic_chat(messages: list, model: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Call Anthropic API."""
    from anthropic import Anthropic

    api_key = _get_api_key("anthropic")
    client = Anthropic(api_key=api_key)

    # Extract system message if present
    system_msg = None
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            chat_messages.append(m)

    kwargs = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_msg:
        kwargs["system"] = system_msg

    response = client.messages.create(**kwargs)
    return response.content[0].text.strip()


def _gemini_chat(messages: list, model: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Call Google Gemini API."""
    from google import genai
    from google.genai import types

    api_key = _get_api_key("gemini")
    client = genai.Client(api_key=api_key)

    # Convert messages to Gemini format
    gemini_contents = []
    system_instruction = None
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
        elif m["role"] == "user":
            gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m["content"])]))
        elif m["role"] == "assistant":
            gemini_contents.append(types.Content(role="model", parts=[types.Part.from_text(text=m["content"])]))

    if not gemini_contents:
        gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text="Hello")]))

    kwargs = {
        "model": model,
        "contents": gemini_contents,
        "config": types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    }
    if system_instruction:
        kwargs["config"].system_instruction = types.Content(
            parts=[types.Part.from_text(text=system_instruction)]
        )

    response = client.models.generate_content(**kwargs)
    return response.text.strip()


# Provider dispatch table
_PROVIDER_HANDLERS = {
    "groq": _groq_chat,
    "openai": _openai_chat,
    "anthropic": _anthropic_chat,
    "gemini": _gemini_chat,
}

_VISION_HANDLERS = {
    "groq": _groq_vision,
    # OpenAI, Anthropic, Gemini also support vision, but for now only Groq is wired
}


def get_current_provider() -> str:
    """Get the user's configured LLM provider (falls back to 'groq')."""
    provider = get_preference("llm_provider", "groq")
    if provider not in _PROVIDER_HANDLERS:
        provider = "groq"
    return provider


def get_current_model(provider: str = None) -> str:
    """Get the default model for a given provider (falls back to groq)."""
    if provider is None:
        provider = get_current_provider()
    if provider not in _DEFAULT_MODELS:
        provider = "groq"
    return _DEFAULT_MODELS[provider]


def llm_chat(messages: list, provider: str = None, model: str = None,
             temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """
    Unified chat completion. Routes to the configured/provided provider.

    Args:
        messages: List of {"role": "...", "content": "..."} dicts
        provider: One of "groq", "openai", "anthropic", "gemini". If None, uses user preference.
        model: Model name override. If None, uses default for provider.
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Response text string
    """
    if provider is None:
        provider = get_current_provider()

    if provider not in _PROVIDER_HANDLERS:
        print(f"[LLM] Unknown provider '{provider}', falling back to groq")
        provider = "groq"

    if model is None:
        model = get_current_model(provider)

    print("=" * 60)
    print(f"[LLM] Chat completion request")
    print(f"[LLM]   Provider: {provider}")
    print(f"[LLM]   Model: {model}")
    print(f"[LLM]   Messages: {len(messages)}")
    print(f"[LLM]   Last message length: {len(messages[-1]['content']) if messages else 0} chars")
    print("=" * 60)

    handler = _PROVIDER_HANDLERS[provider]
    content = handler(messages, model, temperature, max_tokens)

    print(f"[LLM] ✅ Response received ({len(content)} chars)")
    print(f"[LLM]   Preview: {content[:200]}...")
    print("=" * 60)
    return content


def llm_vision(image_base64: str, prompt: str, provider: str = None, model: str = None,
               mime_type: str = "image/jpeg") -> str:
    """
    Unified vision completion. Routes to the configured/provided provider.

    Currently only Groq supports vision. Falls back to Groq if the selected
    provider doesn't have vision support wired up.
    """
    if provider is None:
        provider = get_current_provider()

    if provider not in _VISION_HANDLERS:
        print(f"[LLM] Provider '{provider}' has no vision handler, falling back to groq")
        provider = "groq"

    if model is None:
        model = get_current_model(provider)

    print("=" * 60)
    print(f"[LLM] Vision request")
    print(f"[LLM]   Provider: {provider}")
    print(f"[LLM]   Model: {model}")
    print(f"[LLM]   Image base64 length: {len(image_base64)} chars")
    print(f"[LLM]   Prompt: '{prompt[:100]}...'")
    print("=" * 60)

    handler = _VISION_HANDLERS[provider]
    content = handler(image_base64, prompt, model, mime_type)

    print(f"[LLM] ✅ Vision response received ({len(content)} chars)")
    print(f"[LLM]   Preview: {content[:200]}...")
    print("=" * 60)
    return content