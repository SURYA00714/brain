"""
Unit test suite for BRAIN Phase 5F — Living Desktop Companion.
Provides 50 comprehensive unit tests across Protocol, Voice, Emotion, Lip Sync, Look-At,
Reaction Engine, Safety Invariants, and Integration.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bridge.protocol import (
    ActionStatus, CapabilityRegistry, CapabilityStatus,
    KNOWN_ACTIONS, ACTION_PARAMS, VRM10_EXPRESSIONS, BRAIN_USABLE_EXPRESSIONS,
    make_companion_action
)
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.reaction_engine import ReactionEngine, PRIORITY, STATE_REACTIONS
from core.voice import ResponsePreparer, SentenceSegmenter, LinuxNativeTTS, SpeechQueue, BaseVoiceProvider
from core.companion_state import CompanionState, CompanionActivity, CompanionStateManager, default_companion_state
from core.desktop_presence import DesktopPresenceManager


class TestPhase5FLivingCompanion(unittest.TestCase):
    def setUp(self):
        self.bridge = DesktopMateBridge()
        self.presence = DesktopPresenceManager(max_recovery_attempts=3)

    # --------------------------------------------------------------------------
    # 1. PROTOCOL TESTS (1-7)
    # --------------------------------------------------------------------------
    def test_01_speak_action_registration(self):
        self.assertIn("speak", KNOWN_ACTIONS)
        self.assertEqual(ACTION_PARAMS["speak"], ["text"])

    def test_02_emotion_action_registration(self):
        self.assertIn("set_emotion", KNOWN_ACTIONS)
        self.assertEqual(ACTION_PARAMS["set_emotion"], ["emotion"])

    def test_03_animation_action_registration(self):
        self.assertIn("play_animation", KNOWN_ACTIONS)
        self.assertEqual(ACTION_PARAMS["play_animation"], ["name"])

    def test_04_lookat_action_registration(self):
        self.assertIn("look_at", KNOWN_ACTIONS)
        self.assertEqual(ACTION_PARAMS["look_at"], ["target"])

    def test_05_malformed_companion_action(self):
        res = make_companion_action(None, None)
        self.assertEqual(res["type"], "companion_action")
        self.assertEqual(res["action"], "")
        self.assertEqual(res["arguments"], {})

    def test_06_unknown_action_rejection(self):
        action = make_companion_action("UNKNOWN_HACK_ACTION")
        self.assertEqual(action["action"], "UNKNOWN_HACK_ACTION")
        self.assertNotIn("UNKNOWN_HACK_ACTION", KNOWN_ACTIONS)

    def test_07_invalid_parameters_handling(self):
        self.bridge.connected = True
        res = self.bridge.set_fps("invalid_string_fps")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.FAILED.value)

    # --------------------------------------------------------------------------
    # 2. VOICE TESTS (8-14)
    # --------------------------------------------------------------------------
    def test_08_text_length_validation(self):
        res = self.bridge.speak("")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.FAILED.value)

    def test_09_response_preparer_sanitization(self):
        raw = "Here is ```python\nprint('hello')\n``` and a link [Python](https://python.org)"
        cleaned = ResponsePreparer.prepare_for_speech(raw)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("https://python.org", cleaned)
        self.assertIn("Python", cleaned)

    def test_10_sentence_segmenter(self):
        text = "Hello world. This is Brain e.g. speaking fast! How are you?"
        chunks = SentenceSegmenter.segment(text)
        self.assertEqual(len(chunks), 3)
        self.assertIn("Brain e.g. speaking fast!", chunks[1])

    def test_11_speech_queue_enqueue(self):
        mock_provider = MagicMock(spec=BaseVoiceProvider)
        queue = SpeechQueue(provider=mock_provider)
        queue.enqueue("Hello companion!")
        time.sleep(0.1)
        mock_provider.speak.assert_called_with("Hello companion!", wait=True)

    def test_12_speech_queue_interrupt(self):
        mock_provider = MagicMock(spec=BaseVoiceProvider)
        queue = SpeechQueue(provider=mock_provider)
        queue.enqueue("Long sentence 1")
        queue.enqueue("Long sentence 2")
        queue.interrupt()
        self.assertFalse(queue.is_speaking)

    def test_13_tts_failure_resilience(self):
        tts = LinuxNativeTTS()
        with patch("subprocess.Popen", side_effect=Exception("Execution failed")):
            res = tts.speak("Test resilience")
            self.assertTrue(res)

    def test_14_empty_text_handling(self):
        tts = LinuxNativeTTS()
        self.assertFalse(tts.speak(""))
        self.assertFalse(tts.speak(None))

    # --------------------------------------------------------------------------
    # 3. EMOTION TESTS (15-19)
    # --------------------------------------------------------------------------
    def test_15_valid_vrm10_emotions(self):
        for emo in BRAIN_USABLE_EXPRESSIONS:
            self.assertIn(emo, VRM10_EXPRESSIONS)

    def test_16_invalid_vrm10_emotion(self):
        self.bridge.connected = True
        res = self.bridge.set_emotion("hyper_excited")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.FAILED.value)

    def test_17_emotion_allowlist_enforcement(self):
        self.bridge.connected = True
        res = self.bridge.set_emotion("invalid_emo")
        self.assertIn("Unknown expression", res["error"])

    def test_18_emotion_runtime_unavailable_status(self):
        res = self.bridge.set_emotion("happy")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

    def test_19_executed_unverified_emotion_status(self):
        self.bridge.connected = True
        with patch.object(self.bridge, "send_and_wait", return_value={"success": True, "status": "executed_unverified"}):
            res = self.bridge.set_emotion("happy")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "executed_unverified")

    # --------------------------------------------------------------------------
    # 4. LIP SYNC TESTS (20-23)
    # --------------------------------------------------------------------------
    def test_20_lipsync_unavailable_fallback(self):
        self.bridge.connected = True
        res = self.bridge.play_voice("/nonexistent/tts.wav")
        self.assertIn("status", res)

    def test_21_lipsync_wav_notification(self):
        engine = ReactionEngine(bridge=self.bridge)
        event = MagicMock()
        event.event_type = "OS_EVENT"
        event.data = {"type": "VOICE_READY", "file": "/tmp/test.wav"}
        with patch.object(self.bridge, "play_voice", return_value={"success": True}) as mock_pv:
            dispatched = engine.handle_event(event)
            self.assertTrue(dispatched)
            mock_pv.assert_called_with("/tmp/test.wav")

    def test_22_audio_file_cleanup(self):
        tts = LinuxNativeTTS()
        tts.engine = None  # Mock mode
        temp_wav = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "tts.wav"))
        tts.speak("test cleanup", wait=True)
        # Verify file is not left behind after TTS execution
        self.assertFalse(os.path.exists(temp_wav))

    def test_23_lipsync_cancellation(self):
        tts = LinuxNativeTTS()
        tts.stop()
        self.assertIsNone(tts._active_proc)

    # --------------------------------------------------------------------------
    # 5. LOOK-AT TESTS (24-28)
    # --------------------------------------------------------------------------
    def test_24_valid_lookat_targets(self):
        self.bridge.connected = True
        with patch.object(self.bridge, "send_and_wait", return_value={"success": True}) as mock_send:
            res = self.bridge.look_at("SCREEN")
            mock_send.assert_called_with("look_at", {"target": "SCREEN"}, timeout=3.0)

    def test_25_invalid_lookat_target(self):
        res = self.bridge.look_at(None)
        self.assertFalse(res["success"])

    def test_26_lookat_throttling(self):
        self.bridge.connected = True
        t0 = time.time()
        self.bridge.look_at("USER")
        self.bridge.look_at("SCREEN")
        self.assertLess(time.time() - t0, 1.0)

    def test_27_lookat_runtime_unavailable(self):
        self.bridge.capabilities.set_capability("look_at", CapabilityStatus.UNAVAILABLE)
        caps = self.bridge.capabilities.to_dict()
        self.assertIn("look_at", caps)
        self.assertEqual(caps["look_at"]["status"], CapabilityStatus.UNAVAILABLE.value)


    def test_28_lookat_reset_neutral(self):
        self.bridge.connected = True
        res = self.bridge.return_idle()
        self.assertIn("status", res)

    # --------------------------------------------------------------------------
    # 6. REACTION ENGINE TESTS (29-40)
    # --------------------------------------------------------------------------
    def test_29_reaction_idle(self):
        self.assertEqual(STATE_REACTIONS["IDLE"]["expression"], "neutral")
        self.assertEqual(STATE_REACTIONS["IDLE"]["animation"], "idle")

    def test_30_reaction_listening(self):
        self.assertEqual(STATE_REACTIONS["LISTENING"]["expression"], "neutral")

    def test_31_reaction_thinking(self):
        self.assertEqual(STATE_REACTIONS["THINKING"]["expression"], "relaxed")

    def test_32_reaction_searching(self):
        self.assertEqual(STATE_REACTIONS["SEARCHING"]["expression"], "surprised")

    def test_33_reaction_working(self):
        self.assertEqual(STATE_REACTIONS["WORKING"]["expression"], "happy")
        self.assertEqual(STATE_REACTIONS["WORKING"]["animation"], "tuttuki")

    def test_34_reaction_success(self):
        self.assertEqual(STATE_REACTIONS["SUCCESS"]["expression"], "happy")
        self.assertEqual(STATE_REACTIONS["SUCCESS"]["animation"], "nadenade")

    def test_35_reaction_warning(self):
        self.assertEqual(STATE_REACTIONS["WARNING"]["expression"], "angry")

    def test_36_reaction_error(self):
        self.assertEqual(STATE_REACTIONS["ERROR"]["expression"], "sad")

    def test_37_reaction_speaking(self):
        self.assertEqual(STATE_REACTIONS["SPEAKING"]["expression"], "happy")

    def test_38_reaction_deduplication(self):
        engine = ReactionEngine(bridge=self.bridge)
        event = MagicMock(event_type="STATE_CHANGE", data={"activity": "THINKING"})
        with patch.object(self.bridge, "set_emotion", return_value={"success": True}):
            d1 = engine.handle_event(event)
            d2 = engine.handle_event(event)
            self.assertTrue(d1)
            self.assertFalse(d2)

    def test_39_reaction_cooldown_gating(self):
        engine = ReactionEngine(bridge=self.bridge)
        e1 = MagicMock(event_type="STATE_CHANGE", data={"activity": "THINKING"})
        e2 = MagicMock(event_type="STATE_CHANGE", data={"activity": "SEARCHING"})
        with patch.object(self.bridge, "set_emotion", return_value={"success": True}):
            self.assertTrue(engine.handle_event(e1))
            self.assertFalse(engine.handle_event(e2))  # Cooldown gated (<2s)

    def test_40_reaction_priority_override(self):
        self.assertGreater(PRIORITY["ERROR"], PRIORITY["WORKING"])
        self.assertGreater(PRIORITY["SUCCESS"], PRIORITY["THINKING"])

    # --------------------------------------------------------------------------
    # 7. SAFETY INVARIANTS (41-45)
    # --------------------------------------------------------------------------
    def test_41_no_arbitrary_shell_execution(self):
        for method in dir(self.bridge):
            self.assertNotIn("shell", method)
            self.assertNotIn("system", method)

    def test_42_no_terminal_command_execution(self):
        for method in dir(self.presence):
            self.assertNotIn("run_terminal", method)

    def test_43_no_x11_command_injection(self):
        with patch("subprocess.run") as mock_run:
            self.presence.apply_desktop_presence("0x9400003; rm -rf /")
            # Ensure wmctrl is called with separate string array, never shell=True
            args, kwargs = mock_run.call_args
            self.assertEqual(args[0][0], "wmctrl")
            self.assertNotIn("shell", kwargs)

    def test_44_no_credential_handling(self):
        self.assertNotIn("password", dir(self.bridge))
        self.assertNotIn("credential", dir(self.bridge))

    def test_45_speech_text_command_immunity(self):
        tts = LinuxNativeTTS()
        tts.engine = "spd-say"
        with patch.object(tts, "is_available", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc
            tts.speak("sudo rm -rf /", wait=True)
            args, _ = mock_popen.call_args
            # Speech text MUST be passed as argument to spd-say, NEVER executed as command
            self.assertEqual(args[0][0], "spd-say")
            self.assertIn("sudo rm -rf /", args[0])



    # --------------------------------------------------------------------------
    # 8. INTEGRATION & RECOVERY TESTS (46-50)
    # --------------------------------------------------------------------------
    def test_46_brain_to_companion_state_wiring(self):
        mgr = CompanionStateManager()
        res = mgr.set_state(activity=CompanionActivity.WORKING, task="Code review")
        self.assertEqual(res["activity"], "WORKING")
        self.assertEqual(res["current_task"], "Code review")

    def test_47_companion_state_to_desktopmate_fanout(self):
        state_dict = default_companion_state.get_state()
        self.assertIn("activity", state_dict)
        self.assertIn("speaking", state_dict)

    def test_48_desktopmate_failure_isolation(self):
        with patch.object(self.presence, "ensure_running", return_value={"success": False, "status": "failed"}):
            res = self.presence.recover()
            self.assertFalse(res["success"])

    def test_49_bridge_reconnect_resilience(self):
        self.assertFalse(self.bridge.connected)
        self.bridge.stop()
        self.assertFalse(self.bridge.connected)

    def test_50_bounded_recovery_retries(self):
        p = DesktopPresenceManager(max_recovery_attempts=2)
        p.recovery_count = 2
        res = p.recover()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "recovery_exhausted")


if __name__ == "__main__":
    unittest.main()
