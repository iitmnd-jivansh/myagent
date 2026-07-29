import os
import sys
import time
from typing import Any, Optional


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, UploadFile, File, Form, Query, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stt import transcribe_audio
from tts import generate_speech
from genui import build_genui_response
from codegen import generate_ui as codegen_ui
from groq_client import strip_thinking

from integrations import (
    execute_chat_request,
    execute_knowledge_query,
    execute_news_lookup,
    execute_search_query,
    execute_weather_lookup,
    list_tools,
)
from mcp_runtime import create_streamable_http_app
from database import (
    init_db,
    create_conversation,
    create_conversation_for_user,
    list_conversations,
    list_conversations_for_user,
    get_conversation,
    delete_conversation,
    add_message,
    get_messages,
    add_generated_ui,
    list_generated_uis,
    get_cached_response,
    set_cached_response,
    get_preference,
    set_preference,
    get_all_preferences,
    create_user,
    get_user_by_username,
    get_user_by_id,
    update_user_password,
    update_conversation_title,
    get_last_message_preview,
)

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

from auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    require_current_user,
    security,
)
from database import delete_session

load_dotenv()

app = FastAPI(title="MyAgent API", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

mcp_asgi_app = create_streamable_http_app()

# Initialize database at startup
init_db()


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
    print("[API] Install with: pip install mcp")
    print("=" * 60)

    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp_missing_dependency():
        """Helpful fallback when the official MCP SDK is not installed."""
        print("=" * 60)
        print("[API] /mcp — Official MCP SDK missing")
        print("=" * 60)
        return {
            "error": "Official MCP SDK is not installed.",
            "install": "pip install mcp",
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

# Default conversation ID for the main chat page (auto-created on first use)
_default_conversation_id: Optional[int] = None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message to the AI assistant and get a response."""
    print("=" * 60)
    print(f"[API] POST /api/chat — Request received")
    print(f"[API]   Message: '{req.message}'")
    print(f"[API]   Language: '{req.language}'")
    print("=" * 60)

    # Use a default conversation for the main chat page
    global _default_conversation_id
    if _default_conversation_id is None:
        _default_conversation_id = create_conversation(title="Main Chat")
        print(f"[API]   Created default conversation #{_default_conversation_id}")

    # Save user message
    add_message(_default_conversation_id, "user", req.message, language=req.language)

    print(f"[API]   Delegating to agent tool router...")
    result = execute_chat_request(req.message, req.language)
    print(f"[API]   Integration completed: {result.integration}")
    print(f"[API]   Response length: {len(result.response)} chars")
    print(f"[API]   Response preview: {result.response[:120]}...")

    # Save assistant message
    add_message(
        _default_conversation_id, "assistant", result.response,
        language=req.language,
        tool_used=result.integration,
        metadata={"integration": result.integration, **result.metadata},
    )

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
    """Get current weather for a city (with DB cache)."""
    print("=" * 60)
    print(f"[API] GET /api/weather — Request received")
    print(f"[API]   Query param — city='{city}'")
    print("=" * 60)

    # Try cache first
    cache_key = f"weather:{city.lower()}"
    cached = get_cached_response("weather", cache_key)
    if cached:
        print(f"[API]   ✅ Using cached weather data for '{city}'")
        return {
            "city": city,
            "response": cached,
            "cached": True,
        }

    result = execute_weather_lookup(city)
    # Cache the result (5 min TTL)
    set_cached_response("weather", cache_key, result.response, ttl=300)

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
    """Get latest news for a topic (with DB cache)."""
    print("=" * 60)
    print(f"[API] GET /api/news — Request received")
    print(f"[API]   Query param — topic='{topic}'")
    print("=" * 60)

    # Try cache first
    cache_key = f"news:{topic.lower()}"
    cached = get_cached_response("news", cache_key)
    if cached:
        print(f"[API]   ✅ Using cached news data for '{topic}'")
        return {
            "topic": topic,
            "response": cached,
            "cached": True,
        }

    result = execute_news_lookup(topic)
    # Cache the result (5 min TTL)
    set_cached_response("news", cache_key, result.response, ttl=300)

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
    """Search the web using SearXNG (with DB cache)."""
    print("=" * 60)
    print(f"[API] POST /api/search — Request received")
    print(f"[API]   Query: '{req.query}'")
    print("=" * 60)

    # Try cache first
    cache_key = f"search:{req.query.lower().strip()}"
    cached = get_cached_response("search", cache_key)
    if cached:
        print(f"[API]   ✅ Using cached search result for '{req.query}'")
        return {
            "query": req.query,
            "response": cached,
            "cached": True,
        }

    result = execute_search_query(req.query)
    # Cache the result (5 min TTL)
    if result.response:
        set_cached_response("search", cache_key, result.response, ttl=300)

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
    speech_text = strip_thinking(req.message)
    print("=" * 60)
    print(f"[API] POST /speak — Request received")
    print(f"[API]   Text to speak: '{speech_text[:80]}...' ({len(speech_text)} chars)")
    print(f"[API]   Language: '{req.language}'")
    print("=" * 60)

    audio_path = generate_speech(
        speech_text,
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

# ── UI Generator ──────────────────────────────────────────────────────────

class GenerateUIRequest(BaseModel):
    prompt: str


GENERATED_DIR = os.path.join(FRONTEND_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)


@app.post("/api/generate-ui")
async def generate_ui(req: GenerateUIRequest):
    """Generate a complete HTML UI from a natural language prompt using Groq."""
    print("=" * 60)
    print(f"[API] POST /api/generate-ui — Request received")
    print(f"[API]   Prompt: '{req.prompt}'")
    print("=" * 60)

    html = codegen_ui(req.prompt)

    # Save to generated directory
    timestamp = int(time.time())
    filename = f"{timestamp}.html"
    filepath = os.path.join(GENERATED_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[API]   Saved to: {filepath}")

    # Extract a title from the HTML
    title = "Generated UI"
    for line in html.splitlines():
        line = line.strip()
        if line.startswith("<title>") and line.endswith("</title>"):
            title = line[7:-8]
            break

    # Record in database
    html_hash = str(hash(html))
    add_generated_ui(req.prompt, title, filename, html_hash)
    print(f"[API] POST /api/generate-ui — Response sent")

    return {
        "html": html,
        "title": title,
        "filename": filename,
    }


@app.get("/uigen")
async def ui_generator_page():
    """Serve the UI generator page."""
    print(f"[API] GET /uigen — Serving UI generator page")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "uigen.html")
    )


@app.get("/uigen.js")
async def ui_generator_js():
    print(f"[API] GET /uigen.js — Serving static file")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "uigen.js"),
        media_type="application/javascript"
    )


@app.get("/uigen.css")
async def ui_generator_css():
    print(f"[API] GET /uigen.css — Serving static file")
    return FileResponse(
        os.path.join(FRONTEND_DIR, "uigen.css"),
        media_type="text/css"
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


# ── Database-Enhanced Chat ─────────────────────────────────────────────────

class ChatRequestWithConversation(BaseModel):
    message: str
    language: str = "en"
    conversation_id: Optional[int] = None


@app.post("/api/v2/chat")
async def chat_v2(
    request: Request,
    user: Optional[dict] = Depends(get_current_user),
):
    """Send a message with conversation persistence.
    
    Supports file attachments (images, PDFs, DOCX, TXT).
    Supports authenticated users (creates user-scoped conversations)
    and anonymous users (creates global conversations).
    """
    content_type = request.headers.get("content-type", "").lower()
    file: Optional[UploadFile] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        message = str(form.get("message") or "")
        language = str(form.get("language") or "en")
        raw_conversation_id = form.get("conversation_id")
        form_file = form.get("file")
        if form_file is not None and getattr(form_file, "filename", None):
            file = form_file
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Expected JSON or multipart form data") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")

        message = str(payload.get("message") or "")
        language = str(payload.get("language") or "en")
        raw_conversation_id = payload.get("conversation_id")

    if not message.strip():
        raise HTTPException(status_code=422, detail="message is required")

    if raw_conversation_id in (None, "", "null", "undefined"):
        conversation_id = None
    else:
        try:
            conversation_id = int(raw_conversation_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="conversation_id must be an integer") from exc

    print("=" * 60)
    print(f"[API] POST /api/v2/chat — Request received")
    print(f"[API]   Message: '{message}'")
    print(f"[API]   Language: '{language}'")
    print(f"[API]   Conversation ID: {conversation_id}")
    print(f"[API]   File attached: {file is not None}")
    if file:
        print(f"[API]   File name: '{file.filename}', size: {file.size} bytes")
    print(f"[API]   Authenticated: {user is not None}")
    print("=" * 60)

    # Process file attachment if present
    file_info = None
    if file and file.filename:
        import tempfile
        from file_processor import process_uploaded_file
        
        # Save uploaded file temporarily
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        file_info = process_uploaded_file(temp_path, file.filename)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass
        
        print(f"[API]   File processed: type={file_info['type']}, content_len={len(str(file_info.get('content', '')))}")

    # Create or reuse conversation
    conv_id = conversation_id
    if conv_id is None:
        title = message[:50] + ("..." if len(message) > 50 else "")
        if user:
            conv_id = create_conversation_for_user(
                user_id=user["user_id"],
                title=title,
            )
        else:
            conv_id = create_conversation(title=title)
        print(f"[API]   Created new conversation #{conv_id}")
    else:
        existing = get_conversation(conv_id)
        if not existing:
            return {"error": f"Conversation #{conv_id} not found"}, 404
        print(f"[API]   Using existing conversation #{conv_id}")

    # Save user message (with file info in metadata if present)
    msg_metadata = {}
    if file_info:
        msg_metadata["file"] = {
            "type": file_info["type"],
            "filename": file_info["filename"],
            "description": file_info["description"],
        }
    
    add_message(conv_id, "user", message, language=language, metadata=msg_metadata if msg_metadata else None)

    # Execute the agent (pass file_info for multimodal processing)
    result = execute_chat_request(message, language, file_info=file_info)

    # Save assistant message
    add_message(
        conv_id, "assistant", result.response,
        language=language,
        tool_used=result.integration,
        metadata={"integration": result.integration, **result.metadata},
    )

    # Update title from first message if still default
    existing = get_conversation(conv_id)
    if existing and existing.get("title", "").startswith("New Conversation"):
        new_title = message[:50] + ("..." if len(message) > 50 else "")
        update_conversation_title(conv_id, new_title)

    ui = build_genui_response(
        result.integration,
        result.response,
        result.metadata,
    )

    # Get conversation info
    conv = get_conversation(conv_id)
    last_preview = get_last_message_preview(conv_id)

    print(f"[API] POST /api/v2/chat — Response sent (conv #{conv_id})")
    return {
        "conversation_id": conv_id,
        "conversation": conv,
        "last_preview": last_preview,
        "response": result.response,
        "ui": ui,
    }


@app.get("/api/conversations")
async def get_conversations(
    limit: int = 20,
    offset: int = 0,
    user: Optional[dict] = Depends(get_current_user),
):
    """List conversations. Filters by user if authenticated, otherwise returns all."""
    if user:
        conversations = list_conversations_for_user(user["user_id"], limit=limit, offset=offset)
    else:
        conversations = list_conversations(limit=limit, offset=offset)
    return {"conversations": conversations}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation_messages(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    user: Optional[dict] = Depends(get_current_user),
):
    """Get messages for a conversation."""
    conv = get_conversation(conversation_id)
    if not conv:
        return {"error": f"Conversation #{conversation_id} not found"}, 404
    messages = get_messages(conversation_id, limit=limit, offset=offset)
    return {"conversation": conv, "messages": messages}


@app.delete("/api/conversations/{conversation_id}")
async def remove_conversation(conversation_id: int):
    """Delete a conversation and its messages."""
    deleted = delete_conversation(conversation_id)
    if not deleted:
        return {"error": f"Conversation #{conversation_id} not found"}, 404
    return {"status": "deleted", "conversation_id": conversation_id}


class UpdateConversationTitleRequest(BaseModel):
    title: str


@app.patch("/api/conversations/{conversation_id}")
async def update_conversation_title(conversation_id: int, req: UpdateConversationTitleRequest):
    """Update a conversation's title."""
    conv = get_conversation(conversation_id)
    if not conv:
        return {"error": f"Conversation #{conversation_id} not found"}, 404
    from database import update_conversation_title as _update_title
    _update_title(conversation_id, req.title)
    return {"status": "ok", "conversation_id": conversation_id, "title": req.title}


# ── Generated UI History ──────────────────────────────────────────────────


@app.get("/api/generated-uis")
async def get_generated_uis(limit: int = 20, offset: int = 0):
    """List all generated UIs."""
    uis = list_generated_uis(limit=limit, offset=offset)
    return {"generated_uis": uis}


# ── User Preferences ──────────────────────────────────────────────────────


class PreferenceRequest(BaseModel):
    key: str
    value: Any = None


@app.get("/api/preferences")
async def get_preferences():
    """Get all user preferences."""
    return {"preferences": get_all_preferences()}


@app.get("/api/preferences/{key}")
async def get_preference_by_key(key: str):
    """Get a specific user preference."""
    value = get_preference(key)
    return {"key": key, "value": value}


@app.post("/api/preferences")
async def update_preference(req: PreferenceRequest):
    """Set a user preference."""
    set_preference(req.key, req.value)
    return {"status": "saved", "key": req.key, "value": req.value}


# ── API Cache Management ──────────────────────────────────────────────────


@app.delete("/api/cache/{service}")
async def clear_cache(service: str):
    """Clear cached responses for a service (weather, news, search)."""
    from database import clear_cache_for_service
    clear_cache_for_service(service)
    return {"status": "cleared", "service": service}


# ── Authentication ─────────────────────────────────────────────────────────


class AuthSignUpRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class AuthSignInRequest(BaseModel):
    username: str
    password: str


class AuthChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/signup")
async def signup(req: AuthSignUpRequest):
    """Register a new user with username and password."""
    print("=" * 60)
    print(f"[API] POST /api/auth/signup — Request received")
    print(f"[API]   Username: '{req.username}'")
    print("=" * 60)

    # Validate inputs
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be at least 3 characters")
    if len(req.password) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 4 characters")

    # Check if username exists
    existing = get_user_by_username(req.username.strip())
    if existing:
        print(f"[API]   Username '{req.username}' already exists")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Create user
    try:
        password_hash = hash_password(req.password)
        display_name = req.display_name.strip() or req.username.strip()
        user_id = create_user(
            username=req.username.strip(),
            password_hash=password_hash,
            display_name=display_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    # Generate JWT
    token = create_token(user_id, req.username.strip())

    print(f"[API]   User #{user_id} '{req.username}' created successfully")
    print(f"[API] POST /api/auth/signup — Response sent")
    return {
        "user": {
            "id": user_id,
            "username": req.username.strip(),
            "display_name": display_name,
        },
        "token": token,
    }


@app.post("/api/auth/signin")
async def signin(req: AuthSignInRequest):
    """Sign in with username and password."""
    print("=" * 60)
    print(f"[API] POST /api/auth/signin — Request received")
    print(f"[API]   Username: '{req.username}'")
    print("=" * 60)

    # Look up user
    user = get_user_by_username(req.username.strip())
    if not user:
        print(f"[API]   User '{req.username}' not found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Verify password
    if not verify_password(req.password, user["password_hash"]):
        print(f"[API]   Invalid password for '{req.username}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Generate JWT
    token = create_token(user["id"], user["username"])

    print(f"[API]   User #{user['id']} '{user['username']}' signed in")
    print(f"[API] POST /api/auth/signin — Response sent")
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
        },
        "token": token,
    }


@app.get("/api/auth/me")
async def get_me(user: Optional[dict] = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    if not user:
        return {"authenticated": False}
    full_user = get_user_by_id(user["user_id"])
    if not full_user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": full_user["id"],
            "username": full_user["username"],
            "display_name": full_user["display_name"],
            "created_at": full_user["created_at"],
        },
    }


@app.post("/api/auth/signout")
async def signout(
    user: dict = Depends(require_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Sign out the current user by deleting their session from the database."""
    print("=" * 60)
    print(f"[API] POST /api/auth/signout — Request received")
    print(f"[API]   User #{user['user_id']} signing out")
    print("=" * 60)
    
    # Extract the raw token and delete the session from the database
    if credentials is not None:
        deleted = delete_session(credentials.credentials)
        if deleted:
            print(f"[API]   Session deleted for user #{user['user_id']}")
        else:
            print(f"[API]   No session found to delete")
    
    print(f"[API]   User #{user['user_id']} signed out successfully")
    print(f"[API] POST /api/auth/signout — Response sent")
    return {"status": "signed_out"}


@app.post("/api/auth/change-password")
async def change_password(
    req: AuthChangePasswordRequest,
    user: dict = Depends(require_current_user),
):
    """Change the password for the currently authenticated user."""
    print("=" * 60)
    print(f"[API] POST /api/auth/change-password — Request received")
    print(f"[API]   User #{user['user_id']} changing password")
    print("=" * 60)

    # Validate new password length
    if len(req.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 4 characters",
        )

    # Fetch the full user record to verify current password
    full_user = get_user_by_id(user["user_id"])
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not verify_password(req.current_password, full_user["password_hash"]):
        print(f"[API]   Incorrect current password for user #{user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash the new password and update
    new_hash = hash_password(req.new_password)
    updated = update_user_password(user["user_id"], new_hash)

    if not updated:
        print(f"[API]   Failed to update password for user #{user['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    print(f"[API]   Password changed successfully for user #{user['user_id']}")
    print(f"[API] POST /api/auth/change-password — Response sent")
    return {"status": "password_changed"}


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
    print("║  ————————————————— Database Routes ——————————————————        ║")
    print("║  POST   /api/v2/chat         — Persistent chat (v2)         ║")
    print("║  GET    /api/conversations   — List conversations           ║")
    print("║  GET    /api/conversations/ — Get conversation messages    ║")
    print("║  DELETE /api/conversations/ — Delete a conversation        ║")
    print("║  GET    /api/generated-uis   — List generated UIs           ║")
    print("║  GET    /api/preferences     — Get all preferences          ║")
    print("║  POST   /api/preferences     — Set a preference             ║")
    print("║  DELETE /api/cache/{service} — Clear API cache              ║")
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
