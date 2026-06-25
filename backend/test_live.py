import asyncio
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash-native-audio-latest"
client = genai.Client(api_key="AQ.Ab8RN6JX3zr8nisUcobmistRepfPfi4uoXFtZJkGvI9TX8nENQ")

async def main():
    async with client.aio.live.connect(model=MODEL) as session:
        print("Connected")
        await session.send(input="Hello, say something.")
        print("Sent hello")
        async for msg in session.receive():
            print("Received msg", type(msg))
        print("Finished receiving!")
        
asyncio.run(main())
