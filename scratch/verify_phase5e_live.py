"""
Phase 5E Real Live Verification & 120-Second Stability Test Script.
"""

import sys
import os
import time
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.desktop_presence import DesktopPresenceManager
from bridge.desktopmate_bridge import DesktopMateBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Phase5EVerifier")

def main():
    print("==================================================================")
    print("  BRAIN PHASE 5E — REAL LIVE DESKTOP COMPANION VERIFICATION      ")
    print("==================================================================")

    presence = DesktopPresenceManager()
    bridge = DesktopMateBridge()

    # Step 1: Ensure Desktop Mate is running
    print("\n--- STEP 1: ENSURE DESKTOP MATE PROCESS & WINDOW ---")
    run_res = presence.ensure_running()
    print(f"ensure_running result: {run_res}")
    if not run_res.get("success"):
        print("FAIL: Desktop Mate process launch failed!")
        return 1

    proc_running = presence.is_process_running()
    win_id = presence.get_window_id()
    print(f"Process Running: {proc_running}")
    print(f"Window ID: {win_id}")

    # Step 2: Connect Bridge
    print("\n--- STEP 2: CONNECT DESKTOP MATE BRIDGE ---")
    bridge.start()

    # Wait up to 10s for WebSocket connection & capability discovery
    connected = False
    for i in range(10):
        time.sleep(1.0)
        if bridge.connected:
            connected = True
            print(f"Bridge connected after {i+1} seconds!")
            break

    if not connected:
        print("FAIL: Could not connect to BepInEx WebSocket bridge at ws://127.0.0.1:8766")
        bridge.stop()
        return 1

    # Step 3: Health & Capabilities
    print("\n--- STEP 3: RUNTIME HEALTH & CAPABILITIES ---")
    health = bridge.health_check(timeout=3.0)
    print(f"Health Check: {json.dumps(health, indent=2)}")

    capabilities = bridge.get_capabilities()
    print(f"Capabilities: {json.dumps(capabilities, indent=2)}")

    # Step 4: Multi-State Presence Diagnostic
    print("\n--- STEP 4: STRUCTURED 5-DIMENSION PRESENCE STATUS ---")
    detailed = presence.get_detailed_status(
        bridge_connected=bridge.connected,
        runtime_ready=health.get("runtime_ready", False),
        character_ready=health.get("character_ready", False)
    )
    print(f"Structured Presence Status:\n{json.dumps(detailed, indent=2)}")

    # Step 5: Test FPS Control
    print("\n--- STEP 5: VERIFY REAL FPS CONTROL ---")
    fps_15 = bridge.set_fps(15, timeout=3.0)
    print(f"set_fps(15) result: {fps_15}")

    time.sleep(1.0)
    fps_30 = bridge.set_fps(30, timeout=3.0)
    print(f"set_fps(30) result: {fps_30}")

    # Step 6: Test Memory Trim & RSS Measurement
    print("\n--- STEP 6: VERIFY MEMORY TRIM & RSS FOOTPRINT ---")
    rss_before = presence.get_memory_usage_mb()
    print(f"Desktop Mate RSS Memory BEFORE Trim: {rss_before} MB")

    trim_res = bridge.trim_memory(timeout=3.0)
    print(f"trim_memory() result: {trim_res}")

    time.sleep(2.0)
    rss_after = presence.get_memory_usage_mb()
    print(f"Desktop Mate RSS Memory AFTER Trim: {rss_after} MB")

    # Step 7: Test Animation Action
    print("\n--- STEP 7: VERIFY REAL ANIMATION EXECUTION ---")
    anim_res = bridge.play_animation("tuttuki", timeout=3.0)
    print(f"play_animation('tuttuki') result: {json.dumps(anim_res, indent=2)}")

    time.sleep(2.0)
    idle_res = bridge.play_animation("idle", timeout=3.0)
    print(f"play_animation('idle') result: {json.dumps(idle_res, indent=2)}")

    # Step 8: 120-Second Continuous Stability Test
    print("\n--- STEP 8: 120-SECOND CONTINUOUS STABILITY TEST ---")
    print("Monitoring process, window, bridge, and memory every 15s for 120 seconds...")

    intervals = [0, 15, 30, 60, 90, 120]
    start_time = time.time()
    stability_pass = True

    for checkpoint in intervals:
        elapsed = time.time() - start_time
        if elapsed < checkpoint:
            time.sleep(checkpoint - elapsed)

        current_proc = presence.is_process_running()
        current_win = presence.get_window_id()
        current_bridge = bridge.connected
        current_rss = presence.get_memory_usage_mb()

        print(f"[T+{int(time.time() - start_time):03d}s] Process: {'ALIVE' if current_proc else 'DEAD'} | Window: {current_win or 'NONE'} | Bridge: {'CONNECTED' if current_bridge else 'DISCONNECTED'} | RSS: {current_rss} MB", flush=True)

        if not current_proc or not current_win or not current_bridge:
            print(f"STABILITY FAILURE AT T+{int(time.time() - start_time)}s!", flush=True)
            stability_pass = False
            break

    print(f"\nStability Test Overall Result: {'PASS (120/120s)' if stability_pass else 'FAIL'}", flush=True)


    bridge.stop()

    print("\n==================================================================")
    print("  PHASE 5E LIVE VERIFICATION SUMMARY                              ")
    print(f"  Desktop Mate Process: {'ALIVE' if proc_running else 'DEAD'}")
    print(f"  Window ID: {win_id}")
    print(f"  Bridge Connected: {connected}")
    print(f"  Runtime Ready: {health.get('runtime_ready')}")
    print(f"  Character Ready: {health.get('character_ready')}")
    print(f"  FPS Control: {fps_15.get('status')}")
    print(f"  Memory Trim: {trim_res.get('status')}")
    print(f"  RSS Memory: {rss_before} MB -> {rss_after} MB")
    print(f"  Animation Action: {anim_res.get('status')}")
    print(f"  120-Second Stability: {'PASS' if stability_pass else 'FAIL'}")
    print("==================================================================")

    return 0 if (connected and stability_pass) else 1

if __name__ == "__main__":
    sys.exit(main())
