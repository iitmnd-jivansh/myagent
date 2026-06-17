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

app = FastAPI()


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