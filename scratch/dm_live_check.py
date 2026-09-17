"""
Brain Desktop Mate Live Diagnostic.
Usage: python scratch/dm_live_check.py [--start]
  --start  : attempt to launch Desktop Mate if not running
Output: compact PASS/FAIL per capability.
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

START_DM = "--start" in sys.argv

def header(title):
    print(f"\n=== {title} ===")

def result(label, status, detail=""):
    print(f"  {label}: {status}" + (f" ({detail})" if detail else ""))

header("DESKTOP MATE LIVE DIAGNOSTIC")

# --- Step 1: Check process ---
from core.desktop_presence import DesktopPresenceManager
dm = DesktopPresenceManager()

running = dm.is_process_running()
if not running and START_DM:
    print("  Launching Desktop Mate...")
    r = dm.ensure_running()
    running = r.get("running", False)
    if not running:
        result("DESKTOP_MATE", "NOT_RUNNING", r.get("error", r.get("status", "")))
        sys.exit(1)

if not running:
    result("DESKTOP_MATE", "NOT_RUNNING", "use --start to launch")
    sys.exit(1)

win_id = dm.get_window_id()
result("DESKTOP_MATE", "RUNNING", f"window={win_id}")
rss = dm.get_memory_usage_mb()
result("DM_MEMORY", f"{rss:.0f} MB")

# --- Step 2: Bridge health ---
from bridge.desktopmate_bridge import DesktopMateBridge
bridge = DesktopMateBridge()
bridge.start()

time.sleep(0.5)

if not bridge.connected:
    result("BRIDGE", "NOT_CONNECTED", "check BepInEx plugin on ws://127.0.0.1:8766")
    sys.exit(1)

r = bridge.health_check() or {}
runtime_ready = r.get("runtime_ready", False)
char_ready = r.get("character_ready", False)
result("BRIDGE", "CONNECTED" if bridge.connected else "NOT_CONNECTED")
result("HEALTH", "PASS" if runtime_ready else "FAIL", f"runtime={runtime_ready} char={char_ready}")
print("DEBUG HEALTH: ", r)

if not runtime_ready:
    result("ANIMATION", "SKIP", "runtime not ready")
    result("EMOTION", "SKIP", "runtime not ready")
    result("LOOK_AT", "SKIP", "runtime not ready")
    bridge.stop()
    sys.exit(1)

# --- Step 3: Capabilities ---
anim_status = bridge.capabilities.get_capability("animation")["status"]
emo_status = bridge.capabilities.get_capability("emotion")["status"]
look_status = bridge.capabilities.get_capability("look_at")["status"]
result("CAPS_ANIMATION", anim_status)
result("CAPS_EMOTION", emo_status)
result("CAPS_LOOK_AT", look_status)

# --- Step 4: Animation ---
if anim_status in ("verified", "available"):
    r = bridge.play_animation("idle")
    s = r.get("status", r.get("data", {}).get("status", "unknown"))
    result("ANIMATION", "PASS" if r.get("success") else "FAIL", s)
else:
    result("ANIMATION", "UNAVAILABLE")

# --- Step 5: Emotion ---
time.sleep(0.3)
if emo_status in ("verified", "available"):
    r = bridge.set_emotion("happy")
    s = r.get("status", "unknown")
    result("EMOTION_HAPPY", "PASS" if r.get("success") else "FAIL", s)
    time.sleep(0.5)
    r2 = bridge.set_emotion("neutral")
    s2 = r2.get("status", "unknown")
    result("EMOTION_NEUTRAL", "PASS" if r2.get("success") else "FAIL", s2)
else:
    result("EMOTION", "UNAVAILABLE")

# --- Step 6: Look-at ---
time.sleep(0.2)
r = bridge.look_at("screen")
s = r.get("status", "unknown")
look_ok = r.get("success") or s == "not_implemented"
result("LOOK_AT", "PASS" if r.get("success") else "NOT_IMPLEMENTED" if s == "not_implemented" else "FAIL", s)

# --- Step 7: Reaction event ---
from core.companion_state import default_companion_state
from bridge.companion_mode import default_companion_mode
default_companion_mode.set_mode("ACTIVE")

# Simulate reaction: set to THINKING → SUCCESS
from bridge.reaction_engine import ReactionEngine
engine = ReactionEngine(bridge, default_companion_mode)
from core.companion_state import CompanionEvent
e1 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
r1 = engine.handle_event(e1)
time.sleep(0.5)
e2 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "SUCCESS"})
r2 = engine.handle_event(e2)
result("BRAIN_REACTION", "PASS" if (r1 or r2) else "FAIL", f"THINKING={r1} SUCCESS={r2}")

# --- Step 8: Memory trim ---
r = bridge.trim_memory()
result("MEMORY_TRIM", "PASS" if r.get("success") else "FAIL", r.get("status", ""))

# --- Step 9: FPS set ---
r = bridge.set_fps(30)
result("FPS_30", "PASS" if r.get("success") else "FAIL", r.get("status", ""))

bridge.stop()
print("\n=== DONE ===")
