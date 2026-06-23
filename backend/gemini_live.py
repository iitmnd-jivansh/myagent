import os
import json
import asyncio
from google import genai
from google.genai import types
from fastapi import WebSocketDisconnect

from weather import get_weather
from search import search_web
from news import get_news
from rag import query_knowledge_base
MODEL = "gemini-2.5-flash-native-audio-latest"

# Will pick up GEMINI_API_KEY from environment variables by default.
client = genai.Client(api_key="AQ.Ab8RN6J6q2zVLeKzpCbAIel6WnSeKW6eTtxdcsZ5DGWCw5OXKg")

class GeminiLiveSession:

    def __init__(self):
        self.session = None

    async def run(self, websocket):

        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": {
                "parts": [{"text": "You are MyAgent. Be concise and conversational. ALWAYS use `query_knowledge_base` first when asked for any information, facts, or context. It searches the internal knowledge base and automatically falls back to web search if needed. You also have tools for weather and news."}]
            },
            "tools": [get_weather, get_news, query_knowledge_base]
        }

        async with client.aio.live.connect(
            model=MODEL,
            config=config,
        ) as session:

            self.session = session
            
            task1 = asyncio.create_task(self.browser_to_gemini(websocket))
            task2 = asyncio.create_task(self.gemini_to_browser(websocket))
            
            done, pending = await asyncio.wait(
                [task1, task2],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
            for task in done:
                try:
                    task.result()
                except Exception as e:
                    print(f"Task exited with error: {e}")

    async def browser_to_gemini(self, websocket):
        audio_count = 0
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)

            if payload["type"] == "audio":
                audio_count += 1
                if audio_count % 50 == 0:
                    print(f"Received {audio_count} audio chunks from browser.")
                await self.session.send_realtime_input(
                    media=types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=bytes(payload["data"])
                    )
                )

    async def gemini_to_browser(self, websocket):
        async for msg in self.session.receive():
            # print("Received message from Gemini")
            server_content = msg.server_content
            if server_content is not None and server_content.model_turn is not None:
                for part in server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        await websocket.send_bytes(part.inline_data.data)

            if msg.tool_call is not None:
                function_responses = []
                for call in msg.tool_call.function_calls:
                    name = call.name
                    args = call.args if call.args else {}
                    print(f"Tool called: {name} with args: {args}")
                    result = None
                    try:
                        if name == "get_weather":
                            result = get_weather(**args)
                        elif name == "search_web":
                            result = search_web(**args)
                        elif name == "get_news":
                            result = get_news(**args)
                        elif name == "query_knowledge_base":
                            result = query_knowledge_base(**args)
                        else:
                            result = f"Unknown tool {name}"
                    except Exception as e:
                        print(f"Error executing tool {name}: {e}")
                        result = f"Error: {e}"
                        
                    if result is None:
                        result = "No result returned."
                    
                    function_responses.append(
                        types.FunctionResponse(
                            name=name,
                            id=call.id,
                            response={"result": result}
                        )
                    )
                
                if function_responses:
                    await self.session.send(
                        input=types.LiveClientToolResponse(
                            function_responses=function_responses
                        )
                    )

    async def close(self):
        pass
