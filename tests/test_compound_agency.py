"""
Unit tests for Phase 19 Companion Evolution:
1. NEW_TAB tool execution & compound browser agency
2. Compound router commands (browser new tab + search, terminal run, file manager navigation)
3. ModelRuntimeStatus truthful identity and latency (<2ms)
4. CompanionState & SSE streaming event emission
5. ResponsePreparer, SentenceSegmenter, and VoiceManager speech queue
"""

import os
import unittest
from unittest.mock import patch, MagicMock

# Enable mock environment for deterministic tests
os.environ["BRAIN_MOCK_GUI"] = "1"

from tools.registry import default_registry, ToolRegistry
from tools.router import default_router
from tools.browser import GUIFallbackBrowserProvider, browser_new_tab, browser_search_foreground
from models.gateway import ModelRuntimeStatus
from core.companion_state import CompanionState, CompanionActivity, CompanionStateManager, CompanionEvent
from core.voice import ResponsePreparer, SentenceSegmenter, VoiceManager, BaseVoiceProvider
from core.config import companion_config


class TestCompoundAgency(unittest.TestCase):

    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_new_tab_registered(self):
        """NEW_TAB should be registered in default_registry."""
        self.assertTrue(default_registry.has_tool("NEW_TAB"))

    def test_new_tab_execution(self):
        """Executing NEW_TAB returns success."""
        res = default_registry.execute("NEW_TAB", {})
        self.assertTrue(res.get("success"))
        data_str = str(res.get("data", "")).lower()
        self.assertIn("tab", data_str)

    def test_browser_new_tab_function(self):
        """Direct call to browser_new_tab returns success."""
        res = browser_new_tab()
        self.assertTrue(res.get("success"))

    def test_compound_router_browser_new_tab_search(self):
        """Router decomposes 'open brave and open new tab and search jarvis' into an ExecutionPlan."""
        query = "open brave and open new tab and search jarvis"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        self.assertIsNotNone(plan)
        tool_names = [step.tool_name for step in plan.steps]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("NEW_TAB", tool_names)
        self.assertIn("BROWSER_SEARCH_FOREGROUND", tool_names)

    def test_compound_router_browser_search(self):
        """Router routes 'open brave and search tamil' into an ExecutionPlan."""
        query = "open brave and search tamil"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        self.assertIsNotNone(plan)
        tool_names = [step.tool_name for step in plan.steps]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("BROWSER_SEARCH_FOREGROUND", tool_names)

    def test_compound_router_terminal_run(self):
        """Router routes 'open terminal and run python' into an ExecutionPlan."""
        query = "open terminal and run python"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        self.assertIsNotNone(plan)
        tool_names = [step.tool_name for step in plan.steps]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("TYPE_TEXT", tool_names)

    def test_compound_router_file_manager(self):
        """Router routes 'open file manager and go to downloads' into an ExecutionPlan."""
        query = "open file manager and go to downloads"
        route_res = default_router.route(query)
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        self.assertIsNotNone(plan)
        tool_names = [step.tool_name for step in plan.steps]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("LIST_FILES", tool_names)


class TestTruthfulModelRuntimeStatus(unittest.TestCase):

    def test_runtime_identity_summary(self):
        """Runtime identity summary reports active cloud provider and fallback."""
        summary = ModelRuntimeStatus.get_runtime_identity_summary()
        self.assertIn("cognitive reasoning", summary.lower())
        self.assertIn("qwen2.5:3b", summary.lower())

    def test_qwen_purpose_summary(self):
        """Qwen purpose summary accurately explains local fallback purpose."""
        purpose = ModelRuntimeStatus.get_qwen_purpose_summary()
        self.assertIn("offline reasoning fallback", purpose.lower())
        self.assertIn("qwen2.5:3b", purpose.lower())

    def test_router_identity_fast_path(self):
        """Router intercepts 'what model do you use' directly as final answer."""
        route_res = default_router.route("what model do you use")
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "final")
        resp = route_res.get("answer", "")
        self.assertIn("cognitive reasoning", resp.lower())

    def test_router_qwen_purpose_fast_path(self):
        """Router intercepts 'for what do you use qwen' directly as final answer."""
        route_res = default_router.route("for what do you use qwen")
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "final")
        resp = route_res.get("answer", "")
        self.assertIn("offline reasoning fallback", resp.lower())


class TestCompanionStateAndEvents(unittest.TestCase):

    def test_state_defaults(self):
        mgr = CompanionStateManager()
        snap = mgr.get_state()
        self.assertEqual(snap["activity"], "IDLE")
        self.assertFalse(snap["speaking"])

    def test_state_updates_and_broadcast(self):
        mgr = CompanionStateManager()

        sub_q = mgr.subscribe()
        mgr.set_state(
            activity=CompanionActivity.WORKING,
            status_text="Executing automated workflow",
            speaking=False,
            progress=0.5
        )

        snap = mgr.get_state()
        self.assertEqual(snap["activity"], "WORKING")
        self.assertEqual(snap["status_text"], "Executing automated workflow")
        self.assertEqual(snap["progress"], 0.5)

        # Event queue receives broadcast
        event = sub_q.get(timeout=1.0)
        self.assertEqual(event.event_type.upper(), "STATE_CHANGE")
        self.assertEqual(event.data["activity"], "WORKING")
        mgr.unsubscribe(sub_q)

    def test_companion_config_loads(self):
        companion_config.reload()
        self.assertIsNotNone(companion_config.avatar)
        self.assertEqual(companion_config.avatar.port, 8765)
        self.assertTrue(companion_config.avatar.mouse_tracking)


class TestVoicePipeline(unittest.TestCase):

    def test_response_preparer_cleans_markdown_and_telemetry(self):
        raw = "```python\nprint('hello')\n```\nHere is [link](http://example.com) to search.\nConfidence: 0.99\n[TELEMETRY] latency=5ms"
        cleaned = ResponsePreparer.prepare_for_speech(raw)
        self.assertNotIn("print('hello')", cleaned)
        self.assertNotIn("Confidence: 0.99", cleaned)
        self.assertNotIn("[TELEMETRY]", cleaned)
        self.assertIn("link", cleaned)

    def test_sentence_segmenter(self):
        text = "Hello there. This is Brain speaking! How can I help you today? E.g. search something."
        segments = SentenceSegmenter.segment(text)
        self.assertGreaterEqual(len(segments), 3)
        self.assertTrue(any("Brain speaking" in s for s in segments))

    def test_voice_manager_speak(self):
        class MockVoice(BaseVoiceProvider):
            def __init__(self):
                self.spoken = []
            def speak(self, text: str, wait: bool = False) -> bool:
                self.spoken.append(text)
                return True
            def is_available(self) -> bool:
                return True

        mock_provider = MockVoice()
        vm = VoiceManager(provider=mock_provider)
        res = vm.speak("Opening browser now. Performing fast web search.", wait=True)
        self.assertTrue(res)
        self.assertGreaterEqual(len(mock_provider.spoken), 1)


if __name__ == "__main__":
    unittest.main()
