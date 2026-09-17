"""
Unit tests for BRAIN Phase 5E — Real Live Desktop Companion Hardening & Verification.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.desktop_presence import DesktopPresenceManager
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.reaction_engine import ReactionEngine
from core.companion_state import CompanionState

from bridge.protocol import ActionStatus, CapabilityRegistry


class TestPhase5EHardening(unittest.TestCase):
    def setUp(self):
        self.presence = DesktopPresenceManager(max_recovery_attempts=3)
        self.bridge = DesktopMateBridge()

    def test_structured_presence_status(self):
        """Verify get_detailed_status returns all 5 required presence dimensions."""
        with patch.object(self.presence, "is_process_running", return_value=True), \
             patch.object(self.presence, "get_window_id", return_value="0x8e00006"), \
             patch.object(self.presence, "get_memory_usage_mb", return_value=185.5):

            status = self.presence.get_detailed_status(
                bridge_connected=True,
                runtime_ready=True,
                character_ready=True
            )

            self.assertTrue(status["process_running"])
            self.assertTrue(status["window_present"])
            self.assertTrue(status["bridge_connected"])
            self.assertTrue(status["runtime_ready"])
            self.assertTrue(status["character_ready"])
            self.assertEqual(status["window_id"], "0x8e00006")
            self.assertEqual(status["rss_memory_mb"], 185.5)

    def test_duplicate_launch_prevention(self):
        """ensure_running must not spawn duplicate Desktop Mate processes if already running."""
        with patch.object(self.presence, "is_process_running", return_value=True), \
             patch.object(self.presence, "get_window_id", return_value="0x8e00006"), \
             patch("subprocess.Popen") as mock_popen:

            res = self.presence.ensure_running()

            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "already_running")
            mock_popen.assert_not_called()

    def test_stale_zombie_process_filtering(self):
        """is_process_running must filter out zombie processes and python/grep wrappers."""
        fake_ps_output = (
            "100 Z python (python)\n"
            "101 Z DesktopMate.exe (DesktopMate.exe)\n"
            "102 S grep (grep DesktopMate.exe)\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_ps_output)
            self.assertFalse(self.presence.is_process_running())

    def test_fps_validation_range(self):
        """FPS target values outside 15-60 must be cleanly rejected or clamped."""
        self.bridge.connected = True
        # Test lower bound rejection (<15)
        res_low = self.bridge.set_fps(10)
        self.assertFalse(res_low["success"])
        self.assertIn("out of allowed range", res_low["error"].lower())

        # Test upper bound rejection (>60)
        res_high = self.bridge.set_fps(120)
        self.assertFalse(res_high["success"])
        self.assertIn("out of allowed range", res_high["error"].lower())

        # Test invalid type rejection
        res_invalid = self.bridge.set_fps("invalid")
        self.assertFalse(res_invalid["success"])

    def test_memory_trim_disconnected_behavior(self):
        """trim_memory must return truthful status when bridge is not connected."""
        res = self.bridge.trim_memory()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

    def test_animation_allowlist_validation(self):
        """play_animation must reject animations outside the allowlist."""
        self.bridge.connected = True
        res = self.bridge.play_animation("unauthorized_spin")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.UNAVAILABLE.value)


    def test_companion_reaction_deduplication(self):
        """ReactionEngine must deduplicate identical state transitions."""
        engine = ReactionEngine(bridge=self.bridge)
        event = MagicMock()
        event.event_type = "STATE_CHANGE"
        event.data = {"activity": "THINKING"}

        with patch.object(self.bridge, "set_emotion", return_value={"success": True, "status": "executed_unverified"}) as mock_emo:

            dispatched1 = engine.handle_event(event)
            self.assertTrue(dispatched1)
            self.assertEqual(mock_emo.call_count, 1)

            # Repeat same state — should be deduplicated
            dispatched2 = engine.handle_event(event)
            self.assertFalse(dispatched2)
            self.assertEqual(mock_emo.call_count, 1)


    def test_safety_invariants(self):
        """Ensure bridge and presence modules never expose arbitrary shell or terminal execution."""
        for method in dir(self.presence):
            self.assertNotIn("exec_shell", method)
            self.assertNotIn("sudo", method)
            self.assertNotIn("run_terminal", method)
        for method in dir(self.bridge):
            self.assertNotIn("exec_shell", method)
            self.assertNotIn("sudo", method)


if __name__ == "__main__":
    unittest.main()
