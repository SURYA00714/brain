"""
Brain Phase 6 Comprehensive Regression & Safety Unit Test Suite.
Verifies World State, Perception Fusion, Smart Observation Policy, Action Verification Contract,
Task Continuity, Interruption, Recovery Engine, Companion Reactions, Voice Abstraction,
Memory Grounding, and Safety Gate Hardening.
"""

import unittest
import time
import os
from unittest.mock import MagicMock, patch

# Enforce headless mock GUI environment during tests
os.environ["BRAIN_MOCK_GUI"] = "1"

from core.world_state import WorldState, WorldStateManager, default_world_state
from core.perception import (
    PerceptionRouter, PerceptionResult, ScreenObservation, FusedObservation,
    SmartObservationPolicy, PerceptionClassifier, default_perception_router
)
from tools.registry import ToolRegistry, Tool, default_registry
from tools.vision import VisionProvider, RapidOCRVisionProvider, UnavailableVisionProvider, default_vision
from core.companion_state import CompanionStateManager, CompanionActivity, InterruptionController, default_companion_state
from core.voice import VoiceManager, LinuxNativeTTS, SpeechInputProvider, default_speech_input
from core.goals import PersistentGoalManager, PersistentGoal, SubTask, default_goals
from core.memory import MemoryStore, MemoryPolicy, MemoryRecord, default_memory
from core.context import ContextBuilder, ShortTermMemory, default_short_term_memory
from core.recovery import AdaptiveRecoveryManager, default_recovery_manager
from core.agent_loop import AgentLoop, default_agent_loop
from bridge.reaction_engine import ReactionEngine, PRIORITY, STATE_REACTIONS


class TestPhase6UnifiedWorldState(unittest.TestCase):
    """Tests Stage 6B — Unified World State."""

    def setUp(self):
        self.mgr = WorldStateManager(staleness_threshold_seconds=1.0)

    def test_world_state_initial_snapshot(self):
        snap = self.mgr.get_snapshot()
        self.assertIsInstance(snap, WorldState)
        self.assertEqual(snap.observation_status, "UNKNOWN")
        self.assertEqual(snap.last_verification, "UNKNOWN")
        self.assertEqual(snap.model_provider, "groq")

    def test_world_state_to_dict_keys(self):
        d = self.mgr.get_snapshot().to_dict()
        required_keys = [
            "os_name", "user_name", "running_apps", "focused_app",
            "active_application", "active_window", "screen_dimensions",
            "brain_activity", "companion_activity", "last_verification",
            "model_provider", "desktop_mate_status", "voice_status"
        ]
        for k in required_keys:
            self.assertIn(k, d, f"Missing required key '{k}' in WorldState dict")

    def test_staleness_detection(self):
        self.mgr.sync_from_system()
        self.assertEqual(self.mgr.check_staleness(), "KNOWN")
        time.sleep(1.1)
        self.assertEqual(self.mgr.check_staleness(), "STALE")

    def test_record_action_outcome_verification(self):
        self.mgr.record_action_outcome("OPEN_APP", {"app_name": "brave"}, {"success": True}, verified=True)
        snap = self.mgr.get_snapshot()
        self.assertEqual(snap.last_action, "OPEN_APP")
        self.assertEqual(snap.last_verification, "CONFIRMED")


class TestPhase6PerceptionFusionAndPolicy(unittest.TestCase):
    """Tests Stage 6C & 6D — Perception Fusion & Smart Observation Policy."""

    def setUp(self):
        self.router = PerceptionRouter()
        self.policy = SmartObservationPolicy(max_freshness_seconds=1.0)

    def test_smart_observation_policy_freshness(self):
        with patch("tools.apps.default_app_tracker.get_focused_app", return_value="brave"):
            self.policy.record_observation("obs_1", "brave")
            # Fresh observation, no action executed -> should NOT observe
            self.assertFalse(self.policy.should_observe(last_action=None, action_executed=False))
            # Force refresh -> should observe
            self.assertTrue(self.policy.should_observe(force_refresh=True))
            # Action executed -> should observe for verification
            self.assertTrue(self.policy.should_observe(last_action="CLICK", action_executed=True))


    def test_smart_observation_policy_app_switch(self):
        self.policy.record_observation("obs_1", "terminal")
        with patch("tools.apps.default_app_tracker.get_focused_app", return_value="brave"):
            self.assertTrue(self.policy.should_observe())

    def test_perception_result_stale_invalidation(self):
        res = PerceptionResult(timestamp=time.time() - 20.0)
        self.assertTrue(res.is_stale(max_age_seconds=15.0))
        res2 = PerceptionResult(timestamp=time.time())
        res2.invalidate()
        self.assertTrue(res2.is_stale())

    def test_fused_observation_construction(self):
        res = self.router.perceive(force_refresh=True, target_evidence="brave")
        self.assertIsInstance(res, PerceptionResult)
        fused = self.router.get_last_fused()
        self.assertIsNotNone(fused)
        self.assertIsInstance(fused, FusedObservation)
        self.assertTrue(len(fused.observation_id) > 0)


class TestPhase6ActionVerificationContract(unittest.TestCase):
    """Tests Stage 6E — Action Verification Contract."""

    def setUp(self):
        self.registry = ToolRegistry()

    def test_unregistered_tool_returns_failed_status(self):
        res = self.registry.execute("NON_EXISTENT_TOOL", {})
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "failed")

    def test_blocked_action_returns_blocked_status(self):
        # Register a tool that attempts dangerous shell command
        def dummy_cmd(cmd):
            return "ok"
        self.registry.register(Tool("DUMMY_SHELL", "shell", {"cmd": "str"}, "HIGH", dummy_cmd))
        
        # Safe input validator should block bash commands
        with patch("tools.input.validate_gui_action_safety", return_value=(False, "Blocked terminal execution")):
            res = self.registry.execute("DUMMY_SHELL", {"cmd": "sudo rm -rf /"})
            self.assertFalse(res["success"])
            self.assertEqual(res["status"], "blocked")

    def test_executed_unverified_status(self):
        def dummy_action():
            return {"success": True, "data": "clicked"}
        self.registry.register(Tool("DUMMY_CLICK", "click", {}, "MEDIUM", dummy_action))
        res = self.registry.execute("DUMMY_CLICK", {})
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "executed_unverified")


class TestPhase6NaturalConversationStateAndInterruption(unittest.TestCase):
    """Tests Stage 6F & 6G — Natural Conversation State & User Interruption."""

    def setUp(self):
        self.state_mgr = CompanionStateManager()
        self.interruption = InterruptionController(state_manager=self.state_mgr)

    def test_companion_state_transitions(self):
        self.state_mgr.set_state(activity=CompanionActivity.THINKING)
        self.assertEqual(self.state_mgr.get_state()["activity"], "THINKING")
        self.state_mgr.set_state(activity=CompanionActivity.WORKING)
        self.assertEqual(self.state_mgr.get_state()["activity"], "WORKING")

    def test_interruption_stops_speech_and_resets_activity(self):
        mock_voice = MagicMock()
        self.interruption.voice_mgr = mock_voice

        res = self.interruption.request_interruption("user_click")
        self.assertTrue(res["interrupted"])
        self.assertTrue(self.interruption.is_cancelled())
        mock_voice.interrupt.assert_called_once()
        self.assertEqual(self.state_mgr.get_state()["activity"], "IDLE")

        self.interruption.reset()
        self.assertFalse(self.interruption.is_cancelled())


class TestPhase6TaskContinuityAndMemory(unittest.TestCase):
    """Tests Stage 6H & 6I — Task Continuity & Memory Grounding."""

    def setUp(self):
        self.stm = ShortTermMemory()

    def test_resolve_references_task_commands(self):
        self.stm.add_turn("Search python tutorials", "Searching web for python tutorials", referenced_query="python tutorials")

        resolved_continue = self.stm.resolve_references("continue")
        self.assertIn("python tutorials", resolved_continue)

        resolved_retry = self.stm.resolve_references("try again")
        self.assertEqual(resolved_retry, "Search python tutorials")

        resolved_stop = self.stm.resolve_references("stop")
        self.assertEqual(resolved_stop, "stop current action")

    def test_memory_policy_redacts_sensitive_credentials(self):
        decision, reason, record = MemoryPolicy.evaluate("FACT", "user", "my_password", "secret12345")
        self.assertEqual(decision, "IGNORE")
        self.assertIn("Privacy Policy Violation", reason)

        decision2, reason2, record2 = MemoryPolicy.evaluate("FACT", "user", "api_key", "sk-12345678901234567890")
        self.assertEqual(decision2, "IGNORE")


class TestPhase6VoiceAndVisionAbstractions(unittest.TestCase):
    """Tests Stage 6L & 6M — Voice & Vision Abstractions."""

    def test_speech_input_provider_unavailable_by_default(self):
        prov = SpeechInputProvider()
        self.assertFalse(prov.is_available())
        res = prov.listen()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "UNAVAILABLE")

    def test_vision_provider_redacts_sensitive_text(self):
        prov = RapidOCRVisionProvider()
        # Mock OCR output with a password field
        with patch.object(prov.ocr, "extract_text", return_value={
            "success": True,
            "status": "OCR_ANALYZED",
            "regions": [{"text": "enter password", "x": 10, "y": 20, "width": 100, "height": 30, "confidence": 0.99}]
        }):
            with patch("pathlib.Path.exists", return_value=True):
                res = prov.analyze_screen("/fake/path.png")
                self.assertTrue(res["success"])
                elem = res["elements"][0]
                self.assertEqual(elem["text"], "[REDACTED]")
                self.assertTrue(elem["is_sensitive"])


class TestPhase6RecoveryAndSafety(unittest.TestCase):
    """Tests Stage 6N & 6P — Recovery Engine & Safety Gate Hardening."""

    def setUp(self):
        self.recovery = AdaptiveRecoveryManager(max_recovery_attempts=2)

    def test_diagnose_invalid_tool(self):
        reason, explanation = self.recovery.diagnose_failure("UNKNOWN_TOOL", {}, {"error": "Tool 'UNKNOWN_TOOL' is not registered."})
        self.assertEqual(reason, "INVALID_TOOL")

    def test_diagnose_safety_block(self):
        reason, explanation = self.recovery.diagnose_failure("SHELL", {}, {"error": "Safety Block: Terminal command execution forbidden."})
        self.assertEqual(reason, "ACTION_BLOCKED_BY_SAFETY")

    def test_recovery_halt_on_safety_block(self):
        strat = self.recovery.determine_recovery_strategy("SHELL", {}, "ACTION_BLOCKED_BY_SAFETY", attempt=0)
        self.assertEqual(strat["action"], "HALT")
        self.assertIn("Safety controller blocks cannot be autonomously bypassed", strat["message"])

    def test_recovery_max_attempts_exceeded(self):
        strat = self.recovery.determine_recovery_strategy("CLICK", {}, "ACTION_FAILED", attempt=2)
        self.assertEqual(strat["action"], "HALT")


class TestPhase6ReactionEngine(unittest.TestCase):
    """Tests Stage 6J — Companion Reaction Intelligence."""

    def test_reaction_engine_cooldown_and_priority(self):
        mock_bridge = MagicMock()
        mock_bridge.set_emotion.return_value = {"status": "ok"}
        mock_bridge.play_animation.return_value = {"status": "ok"}

        engine = ReactionEngine(mock_bridge)
        event1 = MagicMock(event_type="STATE_CHANGE", data={"activity": "WORKING"})

        dispatched = engine.handle_event(event1)
        self.assertTrue(dispatched)

        # Immediate repeated reaction -> should be blocked by cooldown
        event2 = MagicMock(event_type="STATE_CHANGE", data={"activity": "WORKING"})
        dispatched2 = engine.handle_event(event2)
        self.assertFalse(dispatched2)


if __name__ == "__main__":
    unittest.main()
