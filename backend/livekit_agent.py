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
from livekit.plugins import google, deepgram, cartesia, silero

# Import existing MyAgent tools
from weather import get_weather
from news import get_news
from rag import query_knowledge_base

load_dotenv()

logger = logging.getLogger("myagent-livekit")
logger.setLevel(logging.INFO)


def prewarm(proc: JobProcess):
    """Pre-warm step. AgentSession bundles Silero VAD by default."""
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

    @llm.function_tool
    async def get_weather_info(self, city: str) -> str:
        """Returns the current weather conditions for the specified city."""
        logger.info(f"Tool called: get_weather({city})")
        try:
            result = get_weather(city)
            return result or "Could not fetch weather data."
        except Exception as e:
            logger.error(f"Weather tool error: {e}")
            return f"Error fetching weather: {e}"

    @llm.function_tool
    async def get_latest_news(self, topic: str) -> str:
        """Fetches the latest news articles about the given topic."""
        logger.info(f"Tool called: get_news({topic})")
        try:
            result = get_news(topic)
            return result or "No news found for that topic."
        except Exception as e:
            logger.error(f"News tool error: {e}")
            return f"Error fetching news: {e}"

    @llm.function_tool
    async def lookup_knowledge_base(self, query: str) -> str:
        """Searches the internal knowledge base. Automatically falls back to web search if no relevant information is found locally."""
        logger.info(f"Tool called: query_knowledge_base({query})")
        try:
            result = query_knowledge_base(query)
            return result or "No relevant information found."
        except Exception as e:
            logger.error(f"Knowledge base tool error: {e}")
            return f"Error querying knowledge base: {e}"


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the LiveKit agent.

    Called when a user joins a room and the agent is dispatched.
    Sets up the AgentSession with VAD + STT + LLM + TTS, then starts.
    """
    logger.info(f"Agent connecting to room: {ctx.room.name}")

    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(),
        vad=silero.VAD.load(),
        llm=google.LLM(
            model="gemini-2.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
        ),
        tts=cartesia.TTS(voice="86e30c1d-714b-4074-a1f2-1cb6b552fb49"),
    )

    await session.start(
        room=ctx.room,
        agent=MyAgent(),
    )

    # Greet the user
    await session.say("Hello! I'm MyAgent. How can I help you today?")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
