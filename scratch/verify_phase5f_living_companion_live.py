"""
Phase 5F Living Desktop Companion Real Live Verification & 120-Second Stability Test Script.
"""

import sys
import os
import time
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.desktop_presence import DesktopPresenceManager
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.reaction_engine import ReactionEngine
from core.companion_state import default_companion_state, CompanionActivity

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Phase5FVerifier")

def main():
    print("==================================================================", flush=True)
    print("  BRAIN PHASE 5F — LIVING DESKTOP COMPANION REAL LIVE VERIFICATION  ", flush=True)
    print("==================================================================", flush=True)

    presence = DesktopPresenceManager()
    bridge = DesktopMateBridge()

    # Step 1: Ensure Desktop Mate is running
    print("\n--- STEP 1: DESKTOP PRESENCE DIAGNOSTIC ---", flush=True)
    run_res = presence.ensure_running()
    print(f"ensure_running result: {run_res}", flush=True)

    proc_running = presence.is_process_running()
    win_id = presence.get_window_id()
    print(f"Process Running: {proc_running}", flush=True)
    print(f"Window ID: {win_id}", flush=True)

    # Step 2: Connect Bridge
    print("\n--- STEP 2: CONNECT BRIDGE ---", flush=True)
    bridge.start()

    connected = False
    for i in range(10):
        time.sleep(1.0)
        if bridge.connected:
            connected = True
            print(f"Bridge connected after {i+1} seconds!", flush=True)
            break

    if not connected:
        print("FAIL: Could not connect to bridge at ws://127.0.0.1:8766", flush=True)
        bridge.stop()
        return 1

    # Step 3: Structured Presence Status
    print("\n--- STEP 3: 5-DIMENSION PRESENCE STATUS ---", flush=True)
    health = bridge.health_check(timeout=3.0)
    detailed = presence.get_detailed_status(
        bridge_connected=bridge.connected,
        runtime_ready=health.get("runtime_ready", False),
        character_ready=health.get("character_ready", False)
    )
    print(f"Detailed Status:\n{json.dumps(detailed, indent=2)}", flush=True)

    # Step 4: Speech Synthesis (TTS) & Interruption Test
    print("\n--- STEP 4: SPEECH SYNTHESIS & INTERRUPTION ---", flush=True)
    speak_res = bridge.speak("Hello. I am Brain, your live desktop companion.")
    print(f"speak() result: {speak_res}", flush=True)
    time.sleep(1.5)

    stop_res = bridge.stop_speaking()
    print(f"stop_speaking() result: {stop_res}", flush=True)

    # Step 5: Emotion & Animation Execution
    print("\n--- STEP 5: REAL EMOTION & ANIMATION CONTROL ---", flush=True)
    emo_res = bridge.set_emotion("happy")
    print(f"set_emotion('happy') result: {emo_res}", flush=True)
    time.sleep(1.0)

    anim_res = bridge.play_animation("tuttuki")
    print(f"play_animation('tuttuki') result: {json.dumps(anim_res, indent=2)}", flush=True)
    time.sleep(1.5)

    idle_res = bridge.return_idle()
    print(f"return_idle() result: {idle_res}", flush=True)

    # Step 6: CompanionState Reaction Pipeline Test
    print("\n--- STEP 6: REACTION ENGINE PIPELINE ---", flush=True)

    print("Triggering CompanionActivity.WORKING...", flush=True)
    default_companion_state.set_state(activity=CompanionActivity.WORKING, task="Executing task")
    time.sleep(1.5)

    print("Triggering CompanionActivity.SUCCESS...", flush=True)
    default_companion_state.set_state(activity=CompanionActivity.SUCCESS, task="Completed task")
    time.sleep(1.5)

    print("Triggering CompanionActivity.IDLE...", flush=True)
    default_companion_state.set_state(activity=CompanionActivity.IDLE, task=None)


    # Step 7: 120-Second Continuous Stability Test
    print("\n--- STEP 7: 120-SECOND CONTINUOUS STABILITY TEST ---", flush=True)
    print("Monitoring process, window, bridge, and memory every 15s for 120 seconds...", flush=True)

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

    print("\n==================================================================", flush=True)
    print("  PHASE 5F LIVE VERIFICATION SUMMARY                              ", flush=True)
    print(f"  Desktop Mate Process: {'ALIVE' if proc_running else 'DEAD'}", flush=True)
    print(f"  Window ID: {win_id}", flush=True)
    print(f"  Bridge Connected: {connected}", flush=True)
    print(f"  Runtime Ready: {health.get('runtime_ready')}", flush=True)
    print(f"  Character Ready: {health.get('character_ready')}", flush=True)
    print(f"  Speech Synthesis: {speak_res.get('status')}", flush=True)
    print(f"  Emotion Control: {emo_res.get('status')}", flush=True)
    print(f"  Animation Action: {anim_res.get('status')}", flush=True)
    print(f"  120-Second Stability: {'PASS' if stability_pass else 'FAIL'}", flush=True)
    print("==================================================================", flush=True)

    return 0 if (connected and stability_pass) else 1

if __name__ == "__main__":
    sys.exit(main())
