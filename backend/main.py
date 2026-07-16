import os

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from stt import transcribe_audio
from tts import generate_speech
from genui import build_genui_response

from integrations import (
    execute_chat_request,
    execute_knowledge_query,
    execute_news_lookup,
    execute_search_query,
    execute_weather_lookup,
    list_tools,
)
from mcp_runtime import create_streamable_http_app

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

load_dotenv()

app = FastAPI(title="MyAgent API", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

mcp_asgi_app = create_streamable_http_app()


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    language: str = "en"


class SearchRequest(BaseModel):
    query: str


# ── Health & Status ────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    """Check if the backend and its dependencies are running."""
    print("=" * 60)
    print("[API] GET /api/health — Health check requested")
    print("=" * 60)
    result = {
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "stt": "whisper",
            "llm": "qwen3:4b",
            "tts": "cartesia",
            "search": "searxng",
            "knowledge_base": "chromadb",
            "mcp": "official-streamable-http" if mcp_asgi_app is not None else "missing-sdk"
        }
    }
    print(f"[API] Health check response: {result}")
    return result


@app.get("/api/tools")
async def tools():
    """List registered agent tools."""
    print("=" * 60)
    print("[API] GET /api/tools — Registered tools requested")
    print("=" * 60)
    registered_tools = list_tools()
    print(f"[API]   Tool count: {len(registered_tools)}")
    for tool in registered_tools:
        print(f"[API]   Tool: {tool['name']} | default={tool['default']}")
    print(f"[API] GET /api/tools — Response sent")
    return {
        "tools": registered_tools
    }


# ── MCP-Compatible Tool Server ──────────────────────────────────────────────


if mcp_asgi_app is not None:
    print("=" * 60)
    print("[API] Mounting official MCP Streamable HTTP server at /mcp")
    print("=" * 60)
    app.mount("/mcp", mcp_asgi_app, name="mcp")
else:
    print("=" * 60)
    print("[API] Official MCP SDK not installed; /mcp is unavailable")
    print("[API] Install with: pip install -r backend/requirements.txt")
    print("=" * 60)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def mcp_missing_dependency():
    """Helpful fallback when the official MCP SDK is not installed."""
    if mcp_asgi_app is not None:
        return {
            "error": "MCP route is mounted but fallback handler was reached."
        }

    print("=" * 60)
    print("[API] /mcp — Official MCP SDK missing")
    print("=" * 60)
    return {
        "error": "Official MCP SDK is not installed.",
        "install": "pip install -r backend/requirements.txt",
        "status": "missing_dependency",
    }


@app.get("/mcp-status")
async def mcp_status():
    """Return official MCP availability for this backend process."""
    print("=" * 60)
    print("[API] GET /mcp-status — MCP status requested")
    print("=" * 60)
    installed = mcp_asgi_app is not None
    result = {
        "status": "available" if installed else "missing_dependency",
        "official_mcp_endpoint": "/mcp" if installed else None,
        "transport": "streamable-http",
        "tools": ["weather", "news", "search", "knowledge", "rag"],
        "install_hint": None if installed else "pip install -r backend/requirements.txt",
    }
    print(f"[API]   MCP status: {result['status']}")
    print("[API] GET /mcp-status — Response sent")
    return result


# ── Chat ────────────────────────────────────────────────────────────────────


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message to the AI assistant and get a response."""
    print("=" * 60)
    print(f"[API] POST /api/chat — Request received")
    print(f"[API]   Message: '{req.message}'")
    print(f"[API]   Language: '{req.language}'")
    print("=" * 60)

    print(f"[API]   Delegating to agent tool router...")
    result = execute_chat_request(req.message, req.language)
    print(f"[API]   Integration completed: {result.integration}")
    print(f"[API]   Response length: {len(result.response)} chars")
    print(f"[API]   Response preview: {result.response[:120]}...")
    ui = build_genui_response(
        result.integration,
        result.response,
        result.metadata,
    )
    print(f"[API]   GenUI type: {ui['type']}")
    print(f"[API] POST /api/chat — Response sent ({result.integration})")
    return {
        "response": result.response,
        "ui": ui,
    }


# ── Weather ─────────────────────────────────────────────────────────────────


@app.get("/api/weather")
async def weather(city: str = Query("Delhi", description="City name")):
    """Get current weather for a city."""
    print("=" * 60)
    print(f"[API] GET /api/weather — Request received")
    print(f"[API]   Query param — city='{city}'")
    print("=" * 60)
    result = execute_weather_lookup(city)
    ui = build_genui_response(result.integration, result.response, result.metadata)
    print(f"[API]   Weather data fetched for '{city}': {result.response[:80]}...")
    print(f"[API]   GenUI type: {ui['type']}")
    print(f"[API] GET /api/weather — Response sent")
    return {
        "city": city,
        "response": result.response,
        "ui": ui
    }


# ── News ────────────────────────────────────────────────────────────────────


@app.get("/api/news")
async def news(topic: str = Query("india", description="News topic")):
    """Get latest news for a topic."""
    print("=" * 60)
    print(f"[API] GET /api/news — Request received")
    print(f"[API]   Query param — topic='{topic}'")
    print("=" * 60)
    result = execute_news_lookup(topic)
    ui = build_genui_response(result.integration, result.response, result.metadata)
    print(f"[API]   News data fetched for '{topic}': {len(result.response)} chars")
    print(f"[API]   GenUI type: {ui['type']}")
    print(f"[API] GET /api/news — Response sent")
    return {
        "topic": topic,
        "response": result.response,
        "ui": ui
    }


# ── Web Search ──────────────────────────────────────────────────────────────


@app.post("/api/search")
async def web_search(req: SearchRequest):
    """Search the web using SearXNG."""
    print("=" * 60)
    print(f"[API] POST /api/search — Request received")
    print(f"[API]   Query: '{req.query}'")
    print("=" * 60)
    result = execute_search_query(req.query)
    ui = build_genui_response(result.integration, result.response, result.metadata)
    print(f"[API]   Search result: {result.response[:120] if result.response else 'None'}")
    print(f"[API]   GenUI type: {ui['type']}")
    print(f"[API] POST /api/search — Response sent")
    return {
        "query": req.query,
        "response": result.response,
        "ui": ui
    }


# ── Knowledge Base ──────────────────────────────────────────────────────────


@app.post("/api/knowledge")
async def knowledge_base_query(req: SearchRequest):
    """Query the local knowledge base (ChromaDB + RAG)."""
    print("=" * 60)
    print(f"[API] POST /api/knowledge — Request received")
    print(f"[API]   Query: '{req.query}'")
    print("=" * 60)
    result = execute_knowledge_query(req.query)
    ui = build_genui_response(result.integration, result.response, result.metadata)
    print(f"[API]   KB result length: {len(result.response) if result.response else 0} chars")
    print(f"[API]   KB result preview: {result.response[:120] if result.response else 'None'}...")
    print(f"[API]   GenUI type: {ui['type']}")
    print(f"[API] POST /api/knowledge — Response sent")
    return {
        "query": req.query,
        "response": result.response,
        "ui": ui
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("en")
):
    print("=" * 60)
    print(f"[API] POST /transcribe — Request received")
    print(f"[API]   Audio file: '{file.filename}' (size: {file.size} bytes)")
    print(f"[API]   Language: '{language}'")
    print("=" * 60)

    temp_path = "temp_audio.wav"
    print(f"[API]   Saving uploaded audio to '{temp_path}'...")

    with open(temp_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    print(f"[API]   Audio saved ({len(content)} bytes). Calling transcribe_audio()...")

    text = transcribe_audio(
        temp_path,
        language
    )

    print(f"[API]   Transcription result: '{text}'")
    print(f"[API] POST /transcribe — Response sent")
    return {
        "text": text
    }

@app.post("/speak")
async def speak(req: ChatRequest):
    print("=" * 60)
    print(f"[API] POST /speak — Request received")
    print(f"[API]   Text to speak: '{req.message[:80]}...' ({len(req.message)} chars)")
    print(f"[API]   Language: '{req.language}'")
    print("=" * 60)

    audio_path = generate_speech(
        req.message,
        req.language,
        "response.mp3"
    )

    print(f"[API]   Audio generated at: '{audio_path}'")
    print(f"[API] POST /speak — Returning FileResponse (audio/mpeg)")
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="response.mp3"
    )

@app.get("/live.css")
async def live_css():
    print(f"[API] GET /live.css — Serving static file")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "live.css"),
        media_type="text/css"
    )


@app.get("/live.js")
async def live_js():
    print(f"[API] GET /live.js — Serving static file")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "live.js"),
        media_type="application/javascript"
    )


@app.get("/live")
async def live_page():
    print(f"[API] GET /live — Serving live.html frontend page")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "live.html")
    )


# ── LiveKit Cloud Integration ──────────────────────────────────────────────

class TokenRequest(BaseModel):
    room_name: str = "myagent-room"
    identity: str = "web-user"


@app.post("/livekit/token")
async def livekit_token(req: TokenRequest):
    """Generate a LiveKit room access token for the frontend client."""
    print("=" * 60)
    print(f"[API] POST /livekit/token — Request received")
    print(f"[API]   Room: '{req.room_name}', Identity: '{req.identity}'")
    print("=" * 60)

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret or not livekit_url:
        print(f"[API]   ERROR: LiveKit credentials not configured")
        print(f"[API]   LIVEKIT_API_KEY={'set' if api_key else 'MISSING'}")
        print(f"[API]   LIVEKIT_API_SECRET={'set' if api_secret else 'MISSING'}")
        print(f"[API]   LIVEKIT_URL={'set' if livekit_url else 'MISSING'}")
        return {"error": "LiveKit credentials not configured in .env"}

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(req.identity)
        .with_name(req.identity)
        .with_grants(VideoGrants(
            room_join=True,
            room=req.room_name,
        ))
    )

    jwt_token = token.to_jwt()
    print(f"[API]   LiveKit token generated successfully for room '{req.room_name}'")
    print(f"[API]   LiveKit URL: {livekit_url}")
    print(f"[API]   Token (first 50 chars): {jwt_token[:50]}...")
    print(f"[API] POST /livekit/token — Response sent")

    return {
        "token": jwt_token,
        "url": livekit_url,
    }


# ── Frontend Static App ────────────────────────────────────────────────────

print("=" * 60)
print("[API] Mounting frontend static app at /")
print(f"[API]   Directory: {FRONTEND_DIR}")
print("=" * 60)
app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)


# ── Server Startup Banner ──────────────────────────────────────────────────

def print_startup_banner():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    🚀 MyAgent API Server                     ║")
    print("║                    Version 1.0.0                             ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Registered API Routes:                                     ║")
    print("║                                                            ║")
    print("║  GET    /                   — Main frontend app             ║")
    print("║  GET    /api/health         — System health check           ║")
    print("║  GET    /api/tools          — Registered agent tools        ║")
    print("║  ANY    /mcp                — Official MCP endpoint         ║")
    print("║  GET    /mcp-status         — MCP availability status       ║")
    print("║  POST   /api/chat           — AI chat / RAG / tools         ║")
    print("║  GET    /api/weather        — Get weather for a city        ║")
    print("║  GET    /api/news           — Get news for a topic          ║")
    print("║  POST   /api/search         — Web search via SearXNG        ║")
    print("║  POST   /api/knowledge      — Query knowledge base          ║")
    print("║  POST   /transcribe         — Speech-to-text (Whisper)      ║")
    print("║  POST   /speak              — Text-to-speech (Cartesia)     ║")
    print("║  GET    /live               — LiveKit voice frontend page   ║")
    print("║  POST   /livekit/token      — Generate LiveKit token        ║")
    print("║                                                            ║")
    print("║  Services:                                                  ║")
    print("║    STT : Whisper (faster-whisper)                           ║")
    print("║    LLM : Ollama (smollm2:1.7b) / Gemini 2.5 Flash          ║")
    print("║    TTS : Cartesia (sonic-2)                                 ║")
    print("║    Search : SearXNG (localhost:8888)                        ║")
    print("║    Knowledge Base : ChromaDB (local)                        ║")
    print("║    Vector Model : nomic-embed-text (Ollama)                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

# Call startup banner when module loads
print_startup_banner()
