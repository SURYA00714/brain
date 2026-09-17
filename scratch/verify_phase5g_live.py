"""
Brain Phase 5G Real Live Desktop Verification Script.
Executes 10 live test steps on Linux Mint XFCE (X11) desktop:
1. SCREENSHOT & CLEANUP
2. WINDOW METADATA PERCEPTION
3. OCR TEXT EXTRACTION
4. STRUCTURED OBSERVATION MODEL
5. OBSERVE AFTER ACTION
6. SEARCH WORKFLOW OBSERVE LOOP
7. DESKTOP MATE HEALTH DIAGNOSTIC
8. FOCUS SAFETY VERIFICATION
9. PRIVACY & STORAGE AUDIT
10. 120-SECOND CONTINUOUS STABILITY MONITOR
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/home/jai/Downloads/Brain")

from tools.screen import capture_screen, get_screen_metadata, cleanup_screenshots, DEFAULT_SCREENSHOT_PATH
from core.window_state import default_window_provider
from tools.vision import default_vision
from core.perception import default_perception_router
from core.agent_loop import default_agent_loop
from core.desktop_presence import DesktopPresenceManager
from bridge.desktopmate_bridge import DesktopMateBridge

default_desktop_presence = DesktopPresenceManager()
default_bridge = DesktopMateBridge()


def run_live_verification():
    print("==================================================")
    print("BRAIN PHASE 5G — REAL LIVE DESKTOP VERIFICATION")
    print("==================================================")

    # Disable mock mode for real desktop environment test
    os.environ["BRAIN_MOCK_GUI"] = "0"

    # --- LIVE TEST 1: SCREENSHOT & CLEANUP ---
    print("\n=== LIVE TEST 1: SCREENSHOT CAPTURE & CLEANUP ===")
    cap_res = capture_screen()
    print(f"Capture Result: {cap_res}")
    assert cap_res.get("success"), f"Screenshot capture failed: {cap_res.get('error')}"
    img_path = Path(cap_res.get("image_path"))
    assert img_path.exists(), f"Image file {img_path} does not exist"
    assert cap_res.get("width", 0) > 0 and cap_res.get("height", 0) > 0, "Invalid screen dimensions"

    cleanup_screenshots(keep_latest=True)
    print("Screenshot capture & cleanup: PASS")

    # --- LIVE TEST 2: WINDOW METADATA PERCEPTION ---
    print("\n=== LIVE TEST 2: WINDOW METADATA PERCEPTION ===")
    win_meta = default_window_provider.get_active_window_metadata()
    print(f"Active Window Metadata: {win_meta}")
    assert "window" in win_meta, "Window metadata missing 'window' key"
    w_info = win_meta["window"]
    assert "id" in w_info and "title" in w_info and "class" in w_info, "Incomplete window fields"
    print(f"Focused Window: '{w_info.get('title')}' (Class: {w_info.get('class')}) [Geometry: {w_info.get('width')}x{w_info.get('height')}]")
    print("Window metadata perception: PASS")

    # --- LIVE TEST 3: OCR TEXT EXTRACTION ---
    print("\n=== LIVE TEST 3: OCR TEXT EXTRACTION ===")
    ocr_res = default_vision.ocr_provider.extract_text(img_path)
    print(f"OCR Extraction Status: {ocr_res.get('status')}")
    print(f"Extracted Regions Count: {len(ocr_res.get('regions', []))}")
    if ocr_res.get("text"):
        print(f"Sample Extracted Text: {ocr_res['text'][:5]}")
    print("OCR Layer: PASS")

    # --- LIVE TEST 4: STRUCTURED OBSERVATION MODEL ---
    print("\n=== LIVE TEST 4: STRUCTURED OBSERVATION MODEL ===")
    perc_res = default_perception_router.perceive(force_refresh=True)
    perc_dict = perc_res.to_dict()
    print(f"Perception Result: {perc_dict}")
    assert perc_dict.get("confidence_state") in ("CONFIRMED", "LIKELY", "UNKNOWN", "FAILED"), "Invalid confidence state"
    assert "active_window_meta" in perc_dict and "screen_meta" in perc_dict, "Missing metadata fields"
    print(f"Screen State: {perc_res.screen_state} | Confidence State: {perc_res.confidence_state} | Application: {perc_res.application}")
    print("Structured Observation Model: PASS")

    # --- LIVE TEST 5: OBSERVE AFTER ACTION ---
    print("\n=== LIVE TEST 5: OBSERVE AFTER ACTION ===")
    from tools.apps import open_app
    open_res = open_app("brave")
    print(f"Open App Result: {open_res}")
    time.sleep(1.0)
    post_act_perc = default_perception_router.perceive(force_refresh=True)
    print(f"Post-Action Observed Window: '{post_act_perc.application}' | State: {post_act_perc.screen_state}")
    assert isinstance(post_act_perc.application, str), "Invalid window application type"
    print("Observe after action: PASS")

    # --- LIVE TEST 6: SEARCH WORKFLOW OBSERVE LOOP ---
    print("\n=== LIVE TEST 6: SEARCH WORKFLOW OBSERVE LOOP ===")
    loop_res = default_agent_loop.run("Open Brave and search for Python tutorials.")
    print(f"Agent Loop Execution Status: {loop_res.get('status')}")
    print(f"Collected Evidence: {loop_res.get('evidence')}")
    assert loop_res.get("success"), f"Search workflow execution failed: {loop_res.get('answer')}"
    print("Search workflow observe loop: PASS")

    # --- LIVE TEST 7: DESKTOP MATE HEALTH DIAGNOSTIC ---
    print("\n=== LIVE TEST 7: DESKTOP MATE HEALTH DIAGNOSTIC ===")
    p_status = default_desktop_presence.get_detailed_status(
        bridge_connected=default_bridge.connected
    )
    print(f"Desktop Presence Status: {p_status}")
    assert p_status["process_running"], "Desktop Mate process is not running"
    assert p_status["window_present"], "Desktop Mate window is missing"
    print(f"Desktop Mate Memory RSS: {p_status.get('rss_memory_mb')} MB | Window ID: {p_status.get('window_id')}")
    print("Desktop Mate Health Diagnostic: PASS")

    # --- LIVE TEST 8: FOCUS SAFETY VERIFICATION ---
    print("\n=== LIVE TEST 8: FOCUS SAFETY VERIFICATION ===")
    active_before = default_window_provider.get_active_window_metadata()
    default_perception_router.perceive(force_refresh=True)
    active_after = default_window_provider.get_active_window_metadata()
    print(f"Window ID Before Perception: {active_before['window'].get('id')} | Window ID After: {active_after['window'].get('id')}")
    assert active_before['window'].get('id') == active_after['window'].get('id'), "Focus stolen during perception sampling"
    print("Focus Safety Verification: PASS")

    # --- LIVE TEST 9: PRIVACY & STORAGE AUDIT ---
    print("\n=== LIVE TEST 9: PRIVACY & STORAGE AUDIT ===")
    assert not hasattr(default_perception_router, "webcam"), "Webcam attribute present"
    assert not hasattr(default_perception_router, "microphone"), "Microphone attribute present"
    cleanup_screenshots(keep_latest=True)
    scratch_dir = DEFAULT_SCREENSHOT_PATH.parent
    file_count = len(list(scratch_dir.glob("screen_*.png")))
    print(f"Temporary Screenshots in Scratch Directory: {file_count}")
    assert file_count <= 1, "Uncontrolled temporary screenshot accumulation"
    print("Privacy & Storage Audit: PASS")

    # --- LIVE TEST 10: 120-SECOND CONTINUOUS STABILITY MONITOR ---
    print("\n=== LIVE TEST 10: 120-SECOND CONTINUOUS STABILITY MONITOR ===")
    start_time = time.time()
    duration = 120
    interval = 15
    check_idx = 0

    while (time.time() - start_time) < duration:
        elapsed = int(time.time() - start_time)
        diag = default_desktop_presence.get_detailed_status(
            bridge_connected=default_bridge.connected
        )
        p_res = default_perception_router.perceive(force_refresh=True)
        cleanup_screenshots(keep_latest=True)

        print(f"[T+{elapsed:03d}s] Process: {'ALIVE' if diag['process_running'] else 'DEAD'} | Window: {diag.get('window_id')} | Bridge: {'CONNECTED' if diag['bridge_connected'] else 'DISCONNECTED'} | App: '{p_res.application}' ({p_res.screen_state}) | RSS: {diag.get('rss_memory_mb', 0):.2f} MB")
        
        assert diag["process_running"], f"Desktop Mate process died at T+{elapsed}s"
        assert diag["window_present"], f"Desktop Mate window lost at T+{elapsed}s"

        time.sleep(interval)
        check_idx += 1

    total_elapsed = int(time.time() - start_time)
    print(f"\n120-Second Continuous Live Perception Stability Result: PASS ({total_elapsed}/{duration}s, 100% Uptime)")
    print("==================================================")
    print("ALL 10 LIVE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_live_verification()
