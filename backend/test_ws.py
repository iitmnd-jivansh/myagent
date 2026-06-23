import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8000/ws/live") as websocket:
        await websocket.send(json.dumps({
            "type": "audio",
            "data": [0] * 16000
        }))
        msg = await websocket.recv()
        print(msg)

asyncio.run(test())
