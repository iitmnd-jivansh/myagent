from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse

from rag import ask_question
from stt import transcribe_audio
from tts import generate_speech

from weather import get_weather
from news import get_news

from fastapi import WebSocket
from gemini_live import GeminiLiveSession

from fastapi.responses import FileResponse
import os

from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

load_dotenv()

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")


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


@app.get("/")
async def root():

    return {
        "message": "Local AI backend is running"
    }


@app.post("/chat")
async def chat(req: ChatRequest):

    query = req.message.strip()

    query_lower = query.lower()

    # Weather Intent
    if "weather" in query_lower:

        city = (
            query_lower
            .replace("weather", "")
            .replace("in", "")
            .strip()
        )

        if not city:
            city = "Delhi"

        response = get_weather(city)

        return {
            "response": response
        }

    # News Intent
    if "news" in query_lower:

        topic = (
            query_lower
            .replace("latest", "")
            .replace("news", "")
            .replace("about", "")
            .strip()
        )

        if not topic:
            topic = "india"

        response = get_news(topic)

        return {
            "response": response
        }

    # Normal RAG Flow

    if req.language == "hi":

        query = (
            "उत्तर केवल हिन्दी में दें.\n\n"
            + query
        )

    response = ask_question(
    query,
    req.language
    )    

    return {
        "response": response
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("en")
):

    temp_path = "temp_audio.wav"

    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())

    text = transcribe_audio(
        temp_path,
        language
    )

    return {
        "text": text
    }

@app.post("/speak")
async def speak(req: ChatRequest):

    audio_path = generate_speech(
        req.message,
        req.language,
        "response.mp3"
    )

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="response.mp3"
    )

@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):

    await ws.accept()

    session = GeminiLiveSession()

    try:
        await session.run(ws)
    except Exception as e:
        print(f"WebSocket closed: {e}")
    finally:
        await session.close()
        try:
            await ws.close()
        except:
            pass

@app.get("/live.css")
async def live_css():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "live.css"),
        media_type="text/css"
    )


@app.get("/live.js")
async def live_js():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "live.js"),
        media_type="application/javascript"
    )


@app.get("/live")
async def live_page():

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

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret or not livekit_url:
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

    return {
        "token": token.to_jwt(),
        "url": livekit_url,
    }


@app.get("/livekit_live.css")
async def livekit_live_css():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "livekit_live.css"),
        media_type="text/css"
    )


@app.get("/livekit_live.js")
async def livekit_live_js():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "livekit_live.js"),
        media_type="application/javascript"
    )


@app.get("/livekit-live")
async def livekit_live_page():
    return FileResponse(
        os.path.join(FRONTEND_DIR, "livekit_live.html")
    )
