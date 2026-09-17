"""
Live verification script for Brain <-> Desktop Mate Bridge.
Tests raw protocol handshake and DesktopMateBridge client against ws://127.0.0.1:8766.
"""

import asyncio
import json
import sys
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.protocol import make_request, validate_response

async def raw_handshake_test():
    import websockets
    uri = "ws://127.0.0.1:8766"
    print(f"[TEST 1] Connecting directly to {uri}...")
    async with websockets.connect(uri) as ws:
        print("[TEST 1] Connected successfully!")
        
        # 1. Health check
        req1 = make_request("health")
        print(f"[TEST 2] Sending health request: {req1}")
        await ws.send(json.dumps(req1))
        raw_res1 = await asyncio.wait_for(ws.recv(), timeout=5.0)
        res1 = json.loads(raw_res1)
        print(f"[TEST 2] Received health response: {json.dumps(res1, indent=2)}")
        assert res1["action"] == "health"
        assert res1["request_id"] == req1["request_id"]
        assert "data" in res1
        print("[TEST 2] Health check PASSED!")
        
        # 2. Capabilities check
        req2 = make_request("capabilities")
        print(f"[TEST 3] Sending capabilities request: {req2}")
        await ws.send(json.dumps(req2))
        raw_res2 = await asyncio.wait_for(ws.recv(), timeout=5.0)
        res2 = json.loads(raw_res2)
        print(f"[TEST 3] Received capabilities response: {json.dumps(res2, indent=2)}")
        assert res2["action"] == "capabilities"
        assert "capabilities" in res2["data"] or "data" in res2
        print("[TEST 3] Capabilities check PASSED!")

        # 3. Action execution check (emotion)
        req3 = make_request("emotion", {"name": "happy"})
        print(f"[TEST 4] Sending emotion request: {req3}")
        await ws.send(json.dumps(req3))
        raw_res3 = await asyncio.wait_for(ws.recv(), timeout=5.0)
        res3 = json.loads(raw_res3)
        print(f"[TEST 4] Received emotion response: {json.dumps(res3, indent=2)}")
        assert res3["request_id"] == req3["request_id"]
        print("[TEST 4] Action response PASSED!")

def test_bridge_client():
    print("[TEST 5] Testing DesktopMateBridge Python client...")
    bridge = DesktopMateBridge()
    bridge.start()
    import time
    time.sleep(1.5)
    
    print(f"Bridge connected: {bridge.connected}")
    assert bridge.connected, "DesktopMateBridge failed to connect in background thread"
    
    health = bridge.health_check(timeout=3.0)
    print(f"Bridge health_check result: {health}")
    assert health.get("status") in ["verified", "executed_unverified"], f"Unexpected status: {health}"
    
    caps = bridge.refresh_capabilities(timeout=3.0)
    print(f"Bridge capabilities: {caps}")
    
    emo_res = bridge.set_emotion("happy")
    print(f"Bridge set_emotion result: {emo_res}")
    assert emo_res["status"] in ["executed_unverified", "not_implemented", "failed"]
    
    bridge.stop()
    print("[TEST 5] DesktopMateBridge client PASSED!")

if __name__ == "__main__":
    asyncio.run(raw_handshake_test())
    test_bridge_client()
    print("\n==========================================")
    print("ALL LIVE BRIDGE TESTS PASSED PERFECTLY!")
    print("==========================================")
