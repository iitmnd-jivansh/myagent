"""
LiveKit Cloud Agent Worker for MyAgent.

This runs as a standalone process (separate from FastAPI).
It connects to LiveKit Cloud, joins rooms when users connect,
and provides a voice AI assistant using STT → LLM → TTS pipeline.

Usage:
    python livekit_agent.py dev
"""

import logging
import os
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import google, deepgram, cartesia, silero, openai

# Import existing MyAgent tools
from weather import get_weather
from news import get_news
from rag import query_knowledge_base

load_dotenv()

logger = logging.getLogger("myagent-livekit")
logger.setLevel(logging.INFO)


def prewarm(proc: JobProcess):
    """Pre-warm step. AgentSession bundles Silero VAD by default."""
    print("─" * 50)
    print("[LIVEKIT-AGENT] Pre-warm step")
    print("[LIVEKIT-AGENT]   AgentSession with Silero VAD ready")
    print("─" * 50)
    pass


class MyAgent(Agent):
    """
    The MyAgent voice assistant.

    Exposes weather, news, and knowledge base tools that the LLM
    can invoke during conversation.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are MyAgent, a helpful and concise voice AI assistant. "
                "You have access to tools for weather, news, and a knowledge base. "
                "ALWAYS use `lookup_knowledge_base` first when asked for any information, "
                "facts, or context. It searches the internal knowledge base and "
                "automatically falls back to web search if needed. "
                "Be conversational, friendly, and keep responses concise for voice."
            ),
        )
        print("─" * 50)
        print("[LIVEKIT-AGENT] MyAgent initialized")
        print("[LIVEKIT-AGENT]   Instructions: Voice AI with weather, news, KB tools")
        print("─" * 50)

    @llm.function_tool
    async def get_weather_info(self, city: str) -> str:
        """Returns the current weather conditions for the specified city."""
        print("[LIVEKIT-AGENT] ⚡ Tool called: get_weather_info")
        print(f"[LIVEKIT-AGENT]   City: '{city}'")
        try:
            result = get_weather(city)
            if result:
                print(f"[LIVEKIT-AGENT]   ✅ Weather result: {result[:100]}...")
            else:
                print(f"[LIVEKIT-AGENT]   ⚠️ Weather returned None")
            return result or "Could not fetch weather data."
        except Exception as e:
            print(f"[LIVEKIT-AGENT]   ❌ Weather tool error: {e}")
            return f"Error fetching weather: {e}"

    @llm.function_tool
    async def get_latest_news(self, topic: str) -> str:
        """Fetches the latest news articles about the given topic."""
        print("[LIVEKIT-AGENT] ⚡ Tool called: get_latest_news")
        print(f"[LIVEKIT-AGENT]   Topic: '{topic}'")
        try:
            result = get_news(topic)
            if result:
                print(f"[LIVEKIT-AGENT]   ✅ News result ({len(result)} chars)")
            else:
                print(f"[LIVEKIT-AGENT]   ⚠️ News returned None")
            return result or "No news found for that topic."
        except Exception as e:
            print(f"[LIVEKIT-AGENT]   ❌ News tool error: {e}")
            return f"Error fetching news: {e}"

    @llm.function_tool
    async def lookup_knowledge_base(self, query: str) -> str:
        """Searches the internal knowledge base. Automatically falls back to web search if no relevant information is found locally."""
        print("[LIVEKIT-AGENT] ⚡ Tool called: lookup_knowledge_base")
        print(f"[LIVEKIT-AGENT]   Query: '{query}'")
        try:
            result = query_knowledge_base(query)
            if result:
                print(f"[LIVEKIT-AGENT]   ✅ KB result ({len(result)} chars): {result[:150]}...")
            else:
                print(f"[LIVEKIT-AGENT]   ⚠️ KB returned None")
            return result or "No relevant information found."
        except Exception as e:
            print(f"[LIVEKIT-AGENT]   ❌ Knowledge base tool error: {e}")
            return f"Error querying knowledge base: {e}"


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the LiveKit agent.

    Called when a user joins a room and the agent is dispatched.
    Sets up the AgentSession with VAD + STT + LLM + TTS, then starts.
    """
    print("=" * 60)
    print("[LIVEKIT-AGENT] entrypoint() called")
    print(f"[LIVEKIT-AGENT]   Room: {ctx.room.name}")
    print(f"[LIVEKIT-AGENT]   Room metadata: {ctx.room.metadata}")
    print("=" * 60)

    logger.info(f"Agent connecting to room: {ctx.room.name}")

    await ctx.connect()
    print("[LIVEKIT-AGENT] ✅ Connected to LiveKit room")

    # Configure pipeline
    print("[LIVEKIT-AGENT]   Configuring agent pipeline:")
    print("[LIVEKIT-AGENT]     STT: Deepgram")
    print("[LIVEKIT-AGENT]     LLM: llama-3.3-70b-versatile (via Groq)")
    print("[LIVEKIT-AGENT]     TTS: Deepgram (aura-asteria-en)")

    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        ),
        tts=deepgram.TTS(model="aura-asteria-en"),
    )

    print("[LIVEKIT-AGENT]   Starting agent session...")
    await session.start(
        room=ctx.room,
        agent=MyAgent(),
    )
    print("[LIVEKIT-AGENT] ✅ Agent session started")

    # Greet the user
    print("[LIVEKIT-AGENT]   Sending greeting to user...")
    await session.say("Hello! I'm MyAgent. How can I help you today?")
    print("[LIVEKIT-AGENT] ✅ Greeting sent")


if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              🎤 MyAgent LiveKit Cloud Worker                ║")
    print("║                                                            ║")
    print("║  This worker connects to LiveKit Cloud and waits for       ║")
    print("║  users to join rooms. It provides a voice AI assistant     ║")
    print("║  with STT (Deepgram) → LLM (Groq/Llama) → TTS (Deepgram). ║")
    print("║                                                            ║")
    print("║  Usage:  python livekit_agent.py dev                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )