import asyncio
import websockets

async def test():
    uri = "ws://127.0.0.1:8766"
    print("Connecting to", uri)
    async with websockets.connect(uri) as ws:
        print("Connected!")
        req = '{"protocol":"brain-desktopmate","version":1,"request_id":"test1","action":"ping","arguments":{}}'
        print(f"Sending: {req}")
        await ws.send(req)
        print("Sent, waiting for response...")
        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
        print(f"SUCCESS! Received: {resp}")

asyncio.run(test())
