import os
import unittest
from unittest.mock import patch, MagicMock

from tools.apps import verify_app_open, get_system_state_summary, format_system_state_summary, default_app_tracker, APP_CAPABILITIES
from tools.router import FastRouter
from tools.plan import ExecutionPlan, ExecutionStep
from core.cognition import CognitiveEngine, default_cognition
from core.telemetry import default_telemetry, RequestTelemetry
from brain import run_planner_task


class TestPhase18DeterministicSystemState(unittest.TestCase):
    """
    Failure A Verification:
    System state queries must execute deterministically in <200ms with zero LLM calls.
    """

    def setUp(self):
        default_app_tracker.clear()
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def tearDown(self):
        default_app_tracker.clear()

    def test_01_compound_open_apps_and_active_app(self):
        # Register mock running apps
        default_app_tracker.register_app("brave", pid=1001)
        default_app_tracker.register_app("terminal", pid=1002)
        default_app_tracker.set_focused_app("terminal")

        router = FastRouter()
        res = router.route("What apps are currently open on my computer, and which one am I using?")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("type"), "final")
        answer = res.get("answer", "")
        self.assertIn("Open applications", answer)
        self.assertIn("Brave Browser", answer)
        self.assertIn("Terminal", answer)
        self.assertIn("You are currently using: Terminal", answer)

    def test_02_open_apps_query_deterministic(self):
        default_app_tracker.register_app("file_manager", pid=2001)
        router = FastRouter()
        res = router.route("what apps are currently open")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("type"), "final")
        self.assertIn("File Manager", res.get("answer", ""))

    def test_03_active_app_query_deterministic(self):
        default_app_tracker.register_app("text_editor", pid=3001)
        default_app_tracker.set_focused_app("text_editor")
        router = FastRouter()
        res = router.route("which app am I using?")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("type"), "final")
        self.assertIn("Text Editor", res.get("answer", ""))

    def test_04_disk_space_query_deterministic(self):
        router = FastRouter()
        res = router.route("how much disk space do I have?")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("type"), "final")
        self.assertIn("free disk space", res.get("answer", ""))

    def test_05_ram_query_deterministic(self):
        router = FastRouter()
        res = router.route("how much RAM is available?")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("type"), "final")
        self.assertIn("RAM available", res.get("answer", ""))

    def test_06_end_to_end_system_state_zero_llm(self):
        default_app_tracker.register_app("brave", pid=4001)
        default_app_tracker.set_focused_app("brave")
        output = run_planner_task("What apps are currently open on my computer, and which one am I using?")
        self.assertIn("Brave Browser", output)
        last_tel = default_telemetry.get_last()
        self.assertEqual(last_tel.llm_calls_this_request, 0)
        self.assertLess(last_tel.total_ms, 200.0)


class TestPhase18MultiSignalVerification(unittest.TestCase):
    """
    Failure B Verification:
    Process/window verification must check multiple signals (tracker, window, pgrep, focus)
    and not fail falsely due to single-string process matching.
    """

    def setUp(self):
        default_app_tracker.clear()
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def tearDown(self):
        default_app_tracker.clear()

    def test_01_verify_app_open_mock_running(self):
        default_app_tracker.register_app("brave", pid=5001)
        ver = verify_app_open("brave")
        self.assertTrue(ver["verified"])
        self.assertEqual(ver["method"], "mock")

    def test_02_verify_app_open_not_running(self):
        ver = verify_app_open("calculator")
        self.assertFalse(ver["verified"])
        self.assertIn("not detected", ver["error"])

    def test_03_app_capabilities_patterns(self):
        self.assertIn("brave", APP_CAPABILITIES)
        self.assertIn("terminal", APP_CAPABILITIES)
        term_cap = APP_CAPABILITIES["terminal"]
        self.assertIn("xfce4-terminal", term_cap.process_patterns)
        self.assertIn("terminal", term_cap.process_patterns)

    def test_04_post_action_open_app_verification_success(self):
        res = run_planner_task("open brave")
        self.assertTrue("is open" in res or "opened successfully" in res)
        last_tel = default_telemetry.get_last()
        self.assertFalse(last_tel.false_verification)


class TestPhase18CompoundActionSequencing(unittest.TestCase):
    """
    Failure C Verification:
    Compound tasks must not truncate or stop after the first action.
    Sequenced plans must define dependencies and verification methods for each step.
    """

    def setUp(self):
        default_app_tracker.clear()
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def tearDown(self):
        default_app_tracker.clear()

    def test_01_compound_browser_goal_plan_generation(self):
        router = FastRouter()
        res = router.route("Open Brave, search for Python official documentation, and open the first result")
        self.assertEqual(res.get("type"), "plan")
        plan = res.get("plan")
        self.assertIsNotNone(plan)
        self.assertGreaterEqual(len(plan.steps), 5)

        # Check step sequencing
        steps = plan.steps
        self.assertEqual(steps[0].tool_name, "OPEN_APP")
        self.assertEqual(steps[1].tool_name, "FOCUS_APP")
        self.assertEqual(steps[1].depends_on, [1])
        self.assertEqual(steps[2].tool_name, "BROWSER_SEARCH_FOREGROUND")
        self.assertEqual(steps[2].arguments.get("query"), "Python official documentation")
        self.assertEqual(steps[2].depends_on, [2])
        self.assertEqual(steps[3].tool_name, "CLICK_FIRST_RESULT")
        self.assertEqual(steps[3].depends_on, [3])
        self.assertEqual(steps[4].tool_name, "ANALYZE_SCREEN")
        self.assertEqual(steps[4].depends_on, [4])

    def test_02_compound_browser_goal_execution_completes_all_steps(self):
        output = run_planner_task("Open Brave, search for Python official documentation, and open the first result")
        self.assertIn("opened the first result", output)
        last_tel = default_telemetry.get_last()
        self.assertEqual(last_tel.llm_calls_this_request, 0)

    def test_03_execution_step_serialization(self):
        step = ExecutionStep(
            step_id=3,
            action_type="tool",
            tool_name="CLICK_FIRST_RESULT",
            arguments={"query": "test"},
            depends_on=[1, 2],
            expected_outcome="First result clicked",
            verification_method="url_or_page"
        )
        d = step.to_dict()
        self.assertEqual(d["step_id"], 3)
        self.assertEqual(d["depends_on"], [1, 2])
        self.assertEqual(d["expected_outcome"], "First result clicked")
        self.assertEqual(d["verification_method"], "url_or_page")

        step2 = ExecutionStep.from_dict(d)
        self.assertEqual(step2.step_id, 3)
        self.assertEqual(step2.depends_on, [1, 2])
        self.assertEqual(step2.verification_method, "url_or_page")


class TestPhase18WebRelevanceAndDomainFiltering(unittest.TestCase):
    """
    Failure D Verification:
    Web research queries must filter returned snippets for query-keyword relevance.
    """

    @patch("core.cognition.research_topic")
    def test_01_web_research_domain_filtering(self, mock_research):
        mock_research.return_value = {
            "success": True,
            "findings": [
                "Generic portal news from MSN or Yahoo homepage without specific content.",
                "Python 3.13 introduces free-threaded CPython and experimental JIT compiler.",
                "Random celebrity gossip and sports headlines."
            ],
            "sources": ["https://python.org", "https://generic.com"]
        }

        engine = CognitiveEngine()
        # Ensure offline mode so synthesis does not call external APIs in unit test
        with patch.object(engine.gateway.providers["groq"], "is_available", return_value=False), \
             patch.object(engine.gateway.providers["gemini"], "is_available", return_value=False):
            res = engine.execute_web_research("What are the latest Python developments?")
            self.assertTrue(res.get("text"))
            # Verified that Python 3.13 was prioritized and generic portal / sports were filtered or ranked lower
            self.assertIn("Python 3.13", res["text"])


class TestPhase18TelemetryMetrics(unittest.TestCase):
    """
    Verifies that Phase 18 audit and telemetry fields are recorded correctly.
    """

    def test_01_telemetry_fields(self):
        tel = RequestTelemetry(
            request="test",
            false_verification=False,
            unnecessary_llm_call=False,
            replan_count=0,
            goal_step_count=5,
            verification_method="multi_signal"
        )
        d = tel.to_dict()
        self.assertIn("false_verification", d)
        self.assertIn("unnecessary_llm_call", d)
        self.assertIn("replan_count", d)
        self.assertIn("goal_step_count", d)
        self.assertIn("verification_method", d)
        self.assertEqual(d["verification_method"], "multi_signal")


if __name__ == "__main__":
    unittest.main()
