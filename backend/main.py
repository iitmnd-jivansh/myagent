from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
from fastapi.responses import FileResponse

from rag import ask_question
from stt import transcribe_audio
from tts import generate_speech


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


@app.get("/")
async def root():

    return {
        "message": "Local AI backend is running"
    }


@app.post("/chat")
async def chat(req: ChatRequest):

    response = ask_question(req.message)

    return {
        "response": response
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    temp_path = "temp_audio.wav"

    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())

    text = transcribe_audio(temp_path)

    return {
        "text": text
    }


@app.post("/speak")
async def speak(req: ChatRequest):

    audio_path = generate_speech(req.message)

    return FileResponse(
        audio_path,
        media_type="audio/wav"
    )
