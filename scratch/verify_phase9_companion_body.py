"""
Phase 9 Live Verification Script.
Tests: CompanionMode, LookAt, IdleBehavior, ReactionEngine, Companion Tools, Bridge mode.
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PASS = "PASS"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"

results = []

def check(label, success, detail=""):
    status = PASS if success else FAIL
    results.append((label, status, detail))
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))

print("\n=== PHASE 9 LIVE VERIFICATION ===\n")

# 1. CompanionMode
print("1. CompanionMode Controller")
try:
    from bridge.companion_mode import CompanionModeController, CompanionMode
    ctrl = CompanionModeController()
    check("default ACTIVE", ctrl.get_mode() == CompanionMode.ACTIVE)
    ctrl.set_mode("PASSIVE")
    check("set PASSIVE", ctrl.get_mode() == "PASSIVE")
    ctrl.set_mode("SLEEPING")
    check("should_react SLEEPING = False", not ctrl.should_react(5))
    ctrl.set_mode("ACTIVE")
    check("should_react ACTIVE low = True", ctrl.should_react(0))
    r = ctrl.set_mode("INVALID")
    check("invalid mode rejected", not r["success"])
except Exception as e:
    check("CompanionMode", False, str(e))

# 2. LookAt
print("\n2. LookAt Controller")
try:
    from bridge.look_at import LookAtController, VALID_TARGETS
    from bridge.companion_mode import CompanionModeController
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.connected = True
    bridge.look_at.return_value = {"status": "executed_unverified"}
    mode = CompanionModeController()
    ctrl_la = LookAtController(bridge, mode)

    check("valid targets set", {"mouse","screen","active_window","none"} == VALID_TARGETS)
    r = ctrl_la.set_target("screen")
    check("set screen succeeds", r["success"])
    r = ctrl_la.set_target("webcam")
    check("invalid target rejected", not r["success"])
    mode.set_mode("SLEEPING")
    r = ctrl_la.set_target("mouse")
    check("sleeping suppresses", not r["success"])
except Exception as e:
    check("LookAt", False, str(e))

# 3. IdleBehavior
print("\n3. Idle Behavior Controller")
try:
    from bridge.idle_behavior import IdleBehaviorController
    from bridge.companion_mode import CompanionModeController
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.connected = True
    bridge.play_animation.return_value = {"status": "executed_unverified"}
    bridge.look_at.return_value = {"status": "executed_unverified"}
    mode = CompanionModeController()
    state_mgr = MagicMock()
    state_mgr.get_state.return_value = {"activity": "IDLE"}
    idle = IdleBehaviorController(bridge, mode, state_mgr)

    check("starts with full tokens", idle._tokens == IdleBehaviorController.MAX_ACTIONS_PER_HOUR)
    check("can trigger initially", idle._can_trigger())
    idle._last_idle_time = time.time()
    check("cooldown blocks", not idle._can_trigger())
    idle.start()
    time.sleep(0.1)
    check("starts running", idle._running)
    idle.stop()
    check("stops", not idle._running)
except Exception as e:
    check("IdleBehavior", False, str(e))

# 4. ReactionEngine new events
print("\n4. ReactionEngine New Events")
try:
    from bridge.reaction_engine import ReactionEngine
    from bridge.companion_mode import CompanionModeController
    from core.companion_state import CompanionEvent
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.set_emotion.return_value = {"status": "executed_unverified"}
    bridge.play_animation.return_value = {"status": "executed_unverified"}
    mode = CompanionModeController()
    engine = ReactionEngine(bridge, mode)

    e = CompanionEvent(event_type="BRAIN_EVENT", data={"event": "ACTION_FAILED"})
    check("ACTION_FAILED triggers", engine.handle_event(e))

    mode.set_mode("DISABLED")
    e2 = CompanionEvent(event_type="BRAIN_EVENT", data={"event": "ACTION_FAILED"})
    check("DISABLED suppresses", not engine.handle_event(e2))
    mode.set_mode("ACTIVE")
except Exception as e:
    check("ReactionEngine", False, str(e))

# 5. Companion tools in registry
print("\n5. Companion Tools in Registry")
try:
    from tools.registry import default_registry
    tools_expected = [
        "COMPANION_SHOW", "COMPANION_HIDE", "COMPANION_STATUS",
        "COMPANION_MODE", "COMPANION_RESET_POSITION", "COMPANION_IDLE",
        "COMPANION_HAPPY", "COMPANION_SLEEPY", "COMPANION_LOOK_AT",
        "COMPANION_STOP_SPEECH"
    ]
    for t in tools_expected:
        check(f"  {t} registered", default_registry.has_tool(t))

    # Execute a safe one
    r = default_registry.execute("COMPANION_IDLE", {})
    check("COMPANION_IDLE executes", r.get("success"))
    r = default_registry.execute("COMPANION_MODE", {"mode": "ACTIVE"})
    check("COMPANION_MODE executes", r.get("success"))
except Exception as e:
    check("Companion Tools", False, str(e))

# 6. CompanionState includes companion_mode
print("\n6. CompanionState.to_dict includes companion_mode")
try:
    from core.companion_state import CompanionState
    d = CompanionState().to_dict()
    check("companion_mode in dict", "companion_mode" in d)
    check("companion_mode is valid string", d.get("companion_mode") in ["ACTIVE","PASSIVE","SLEEPING","DISABLED"])
except Exception as e:
    check("CompanionState dict", False, str(e))

# 7. Desktop presence (no DM required)
print("\n7. Desktop Presence Manager")
try:
    from core.desktop_presence import DesktopPresenceManager
    mgr = DesktopPresenceManager()
    proc = mgr.is_process_running()
    check("is_process_running callable", True)
    rss = mgr.get_memory_usage_mb()
    check("get_memory_usage_mb callable", True, f"{rss} MB")
    check("max_recovery_attempts configurable", mgr.max_recovery_attempts == 3)
except Exception as e:
    check("DesktopPresence", False, str(e))

# Summary
print("\n=== RESULTS ===")
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
print(f"Total: {passed + failed}")
print(f"PASS:  {passed}")
print(f"FAIL:  {failed}")

if failed:
    print("\nFailures:")
    for label, status, detail in results:
        if status == FAIL:
            print(f"  [{FAIL}] {label}: {detail}")

sys.exit(0 if failed == 0 else 1)
