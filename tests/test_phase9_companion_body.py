"""
Tests for Phase 9 — Natural Interaction, Desktop Companion Body.

Covers:
- CompanionModeController (ACTIVE/PASSIVE/SLEEPING/DISABLED)
- IdleBehaviorController (token budget, cooldown, no-spam)
- LookAtController (throttle, valid targets, mode gating)
- ReactionEngine (new events: ACTION_STARTED/VERIFIED/FAILED, USER_MESSAGE, SPEECH_STARTED/STOPPED)
- Companion tools registered in registry
- CompanionState.to_dict() includes companion_mode
"""

import sys
import os
import time
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# CompanionModeController tests
# ---------------------------------------------------------------------------

class TestCompanionModeController(unittest.TestCase):

    def setUp(self):
        from bridge.companion_mode import CompanionModeController, CompanionMode
        self.ctrl = CompanionModeController()
        self.Mode = CompanionMode

    def test_default_is_active(self):
        self.assertEqual(self.ctrl.get_mode(), self.Mode.ACTIVE)

    def test_set_valid_mode(self):
        result = self.ctrl.set_mode("PASSIVE")
        self.assertTrue(result["success"])
        self.assertEqual(self.ctrl.get_mode(), self.Mode.PASSIVE)

    def test_set_sleeping(self):
        self.ctrl.set_mode("SLEEPING")
        self.assertTrue(self.ctrl.is_sleeping())

    def test_set_disabled(self):
        self.ctrl.set_mode("DISABLED")
        self.assertTrue(self.ctrl.is_disabled())

    def test_invalid_mode_rejected(self):
        result = self.ctrl.set_mode("PARTY_MODE")
        self.assertFalse(result["success"])

    def test_case_insensitive_not_required(self):
        # Mode setting is case-sensitive (requires uppercase callers)
        result = self.ctrl.set_mode("ACTIVE")
        self.assertTrue(result["success"])

    def test_should_react_active_low_priority(self):
        self.ctrl.set_mode("ACTIVE")
        self.assertTrue(self.ctrl.should_react(0))

    def test_should_react_passive_low_priority(self):
        self.ctrl.set_mode("PASSIVE")
        self.assertFalse(self.ctrl.should_react(0))

    def test_should_react_passive_high_priority(self):
        self.ctrl.set_mode("PASSIVE")
        self.assertTrue(self.ctrl.should_react(3))

    def test_should_react_sleeping_never(self):
        self.ctrl.set_mode("SLEEPING")
        self.assertFalse(self.ctrl.should_react(5))

    def test_should_react_disabled_never(self):
        self.ctrl.set_mode("DISABLED")
        self.assertFalse(self.ctrl.should_react(5))

    def test_to_dict(self):
        d = self.ctrl.to_dict()
        self.assertIn("mode", d)

    def test_thread_safety(self):
        errors = []
        def switch():
            try:
                for mode in ["ACTIVE", "PASSIVE", "SLEEPING", "DISABLED", "ACTIVE"]:
                    self.ctrl.set_mode(mode)
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=switch) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# IdleBehaviorController tests
# ---------------------------------------------------------------------------

class TestIdleBehaviorController(unittest.TestCase):

    def setUp(self):
        from bridge.idle_behavior import IdleBehaviorController
        from bridge.companion_mode import CompanionModeController

        self.bridge = MagicMock()
        self.bridge.connected = True
        self.bridge.play_animation.return_value = {"status": "executed_unverified"}
        self.bridge.look_at.return_value = {"status": "executed_unverified"}

        self.mode = CompanionModeController()
        self.mode.set_mode("ACTIVE")

        self.state_mgr = MagicMock()
        self.state_mgr.get_state.return_value = {"activity": "IDLE"}

        self.ctrl = IdleBehaviorController(self.bridge, self.mode, self.state_mgr)

    def test_token_bucket_starts_full(self):
        from bridge.idle_behavior import IdleBehaviorController
        self.assertEqual(self.ctrl._tokens, IdleBehaviorController.MAX_ACTIONS_PER_HOUR)

    def test_can_trigger_initially(self):
        self.assertTrue(self.ctrl._can_trigger())

    def test_consume_token_decrements(self):
        before = self.ctrl._tokens
        self.ctrl._consume_token()
        self.assertEqual(self.ctrl._tokens, before - 1)

    def test_cooldown_prevents_fast_triggers(self):
        self.ctrl._last_idle_time = time.time()  # just triggered
        self.assertFalse(self.ctrl._can_trigger())

    def test_sleeping_mode_suppresses(self):
        self.mode.set_mode("SLEEPING")
        # _try_idle_action should return without calling bridge
        self.ctrl._try_idle_action()
        self.bridge.play_animation.assert_not_called()
        self.bridge.look_at.assert_not_called()

    def test_non_idle_activity_suppresses(self):
        self.state_mgr.get_state.return_value = {"activity": "THINKING"}
        self.ctrl._try_idle_action()
        self.bridge.play_animation.assert_not_called()

    def test_disconnected_suppresses(self):
        self.bridge.connected = False
        self.ctrl._try_idle_action()
        self.bridge.play_animation.assert_not_called()

    def test_start_stop(self):
        self.ctrl.start()
        self.assertTrue(self.ctrl._running)
        self.ctrl.stop()
        self.assertFalse(self.ctrl._running)


# ---------------------------------------------------------------------------
# LookAtController tests
# ---------------------------------------------------------------------------

class TestLookAtController(unittest.TestCase):

    def setUp(self):
        from bridge.look_at import LookAtController
        from bridge.companion_mode import CompanionModeController

        self.bridge = MagicMock()
        self.bridge.connected = True
        self.bridge.look_at.return_value = {"status": "executed_unverified"}

        self.mode = CompanionModeController()
        self.mode.set_mode("ACTIVE")

        self.ctrl = LookAtController(self.bridge, self.mode)

    def test_valid_targets(self):
        for target in ["mouse", "screen", "active_window", "none"]:
            result = self.ctrl.set_target(target)
            self.assertTrue(result["success"], f"Failed for target: {target}")

    def test_invalid_target_rejected(self):
        result = self.ctrl.set_target("webcam")
        self.assertFalse(result["success"])

    def test_mode_suppresses_sleeping(self):
        self.mode.set_mode("SLEEPING")
        result = self.ctrl.set_target("screen")
        self.assertFalse(result["success"])

    def test_not_connected_returns_failure(self):
        self.bridge.connected = False
        result = self.ctrl.set_target("mouse")
        self.assertFalse(result["success"])

    def test_throttle_same_target(self):
        self.ctrl.set_target("screen")
        self.bridge.look_at.reset_mock()
        # Second immediate call should be throttled
        result = self.ctrl.set_target("screen")
        self.assertEqual(result.get("status"), "throttled")

    def test_get_target(self):
        self.ctrl.set_target("mouse")
        self.assertEqual(self.ctrl.get_target(), "mouse")

    def test_reset(self):
        self.ctrl.set_target("screen")
        time.sleep(0.01)  # allow enough time for lock
        self.ctrl._last_update = 0.0  # force throttle reset
        result = self.ctrl.reset()
        self.assertTrue(result["success"])
        self.assertEqual(self.ctrl.get_target(), "none")


# ---------------------------------------------------------------------------
# ReactionEngine tests (new events)
# ---------------------------------------------------------------------------

class TestReactionEngineNewEvents(unittest.TestCase):

    def setUp(self):
        from bridge.reaction_engine import ReactionEngine
        from bridge.companion_mode import CompanionModeController
        from core.companion_state import CompanionEvent

        self.bridge = MagicMock()
        self.bridge.set_emotion.return_value = {"status": "executed_unverified"}
        self.bridge.play_animation.return_value = {"status": "executed_unverified"}

        self.mode = CompanionModeController()
        self.mode.set_mode("ACTIVE")

        self.engine = ReactionEngine(self.bridge, self.mode)
        self.CompanionEvent = CompanionEvent

    def _make_event(self, event_type, activity):
        return self.CompanionEvent(
            event_type=event_type,
            data={"activity": activity}
        )

    def _make_brain_event(self, event_name):
        return self.CompanionEvent(
            event_type="BRAIN_EVENT",
            data={"event": event_name}
        )

    def test_action_started_triggers(self):
        event = self._make_brain_event("ACTION_STARTED")
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_action_verified_triggers(self):
        event = self._make_brain_event("ACTION_VERIFIED")
        # Clear same-type cooldown
        self.engine._last_reaction_type_time = {}
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_action_failed_triggers_high_priority(self):
        event = self._make_brain_event("ACTION_FAILED")
        result = self.engine.handle_event(event)
        # ACTION_FAILED has priority 5, bypasses general cooldown
        self.assertTrue(result)

    def test_user_message_triggers(self):
        event = self._make_brain_event("USER_MESSAGE")
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_speech_started_triggers(self):
        event = self._make_brain_event("SPEECH_STARTED")
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_speech_stopped_triggers(self):
        event = self._make_brain_event("SPEECH_STOPPED")
        self.engine._last_reaction_type_time = {}
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_sleeping_mode_suppresses(self):
        self.mode.set_mode("SLEEPING")
        event = self._make_event("STATE_CHANGE", "WORKING")
        result = self.engine.handle_event(event)
        self.assertFalse(result)

    def test_disabled_mode_suppresses(self):
        self.mode.set_mode("DISABLED")
        event = self._make_brain_event("ACTION_FAILED")
        result = self.engine.handle_event(event)
        self.assertFalse(result)

    def test_passive_mode_blocks_low_priority(self):
        self.mode.set_mode("PASSIVE")
        event = self._make_brain_event("ACTION_STARTED")  # priority 2
        result = self.engine.handle_event(event)
        self.assertFalse(result)

    def test_passive_mode_allows_high_priority(self):
        self.mode.set_mode("PASSIVE")
        event = self._make_brain_event("ACTION_FAILED")  # priority 5
        result = self.engine.handle_event(event)
        self.assertTrue(result)

    def test_same_activity_skipped(self):
        event = self._make_event("STATE_CHANGE", "THINKING")
        self.engine.handle_event(event)
        result = self.engine.handle_event(event)
        self.assertFalse(result)

    def test_none_mode_controller_falls_through(self):
        from bridge.reaction_engine import ReactionEngine
        engine = ReactionEngine(self.bridge, None)
        event = self._make_event("STATE_CHANGE", "SUCCESS")
        result = engine.handle_event(event)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# Companion tools in registry
# ---------------------------------------------------------------------------

class TestCompanionToolsInRegistry(unittest.TestCase):

    def setUp(self):
        from tools.registry import default_registry
        self.registry = default_registry

    def test_companion_show_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_SHOW"))

    def test_companion_hide_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_HIDE"))

    def test_companion_status_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_STATUS"))

    def test_companion_mode_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_MODE"))

    def test_companion_reset_position_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_RESET_POSITION"))

    def test_companion_idle_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_IDLE"))

    def test_companion_happy_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_HAPPY"))

    def test_companion_sleepy_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_SLEEPY"))

    def test_companion_look_at_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_LOOK_AT"))

    def test_companion_stop_speech_registered(self):
        self.assertTrue(self.registry.has_tool("COMPANION_STOP_SPEECH"))

    def test_companion_mode_tool_executes(self):
        result = self.registry.execute("COMPANION_MODE", {"mode": "ACTIVE"})
        self.assertTrue(result.get("success"))

    def test_companion_mode_tool_invalid_mode(self):
        result = self.registry.execute("COMPANION_MODE", {"mode": "WARP_SPEED"})
        # Should return success=False due to invalid mode
        self.assertFalse(result.get("success"))

    def test_companion_status_tool_executes(self):
        result = self.registry.execute("COMPANION_STATUS", {})
        # registry.execute wraps in {success, data, ...}
        data = result.get("data") or result
        self.assertIn("companion_mode", data)

    def test_companion_idle_tool_executes(self):
        result = self.registry.execute("COMPANION_IDLE", {})
        self.assertTrue(result.get("success"))

    def test_companion_happy_tool_executes(self):
        result = self.registry.execute("COMPANION_HAPPY", {})
        self.assertTrue(result.get("success"))


# ---------------------------------------------------------------------------
# CompanionState to_dict includes companion_mode
# ---------------------------------------------------------------------------

class TestCompanionStateDict(unittest.TestCase):

    def test_to_dict_includes_companion_mode(self):
        from core.companion_state import CompanionState
        state = CompanionState()
        d = state.to_dict()
        self.assertIn("companion_mode", d)
        self.assertIn(d["companion_mode"], ["ACTIVE", "PASSIVE", "SLEEPING", "DISABLED"])

    def test_to_dict_includes_state_alias(self):
        from core.companion_state import CompanionState
        state = CompanionState(activity="THINKING")
        d = state.to_dict()
        self.assertEqual(d["state"], "THINKING")


if __name__ == "__main__":
    unittest.main()
