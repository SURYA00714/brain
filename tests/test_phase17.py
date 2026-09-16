import time
import unittest
from unittest.mock import patch, MagicMock

from brain import run_planner_task
from core.cognition import default_cognition
from core.context import default_short_term_memory
from core.memory import default_memory
from core.telemetry import default_telemetry
from core.world_state import default_world_state
from models.gateway import default_gateway, ModelResponse, ProvenanceSource
from tools.apps import default_app_tracker
from tools.plan import ExecutionPlan, ExecutionStep, GoalState


class TestPhase17GenuineIntelligence(unittest.TestCase):
    """
    Phase 17 Verification Suite:
    Verifies that Brain behaves with genuine intelligence when deterministic logic
    is insufficient, maintaining Phase 16 zero-latency fast paths while providing
    evidence-grounded reasoning, transparent cloud-first model telemetry, accurate
    provenance, and robust autonomous GoalState management.
    """

    def setUp(self):
        default_app_tracker.clear()
        default_world_state.sync_from_system()
        default_short_term_memory.clear()

    def test_01_educational_query_fast_safe_zero_llm_calls(self):
        """'how does rm -rf work?' returns safe educational explanation in <100ms with 0 LLM calls."""
        t0 = time.perf_counter()
        res = run_planner_task("how does rm -rf work?", quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("recursive", res.lower())
        self.assertIn("force", res.lower())
        self.assertLess(dur_ms, 100.0)

        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)
        self.assertEqual(rec.provenance, "STATIC")

    def test_02_open_ended_reasoning_routes_to_model_gateway(self):
        """Genuinely open-ended questions route to ModelGateway with reasoning_required=True and llm_calls=1."""
        with patch.object(default_gateway, "generate") as mock_gen:
            mock_gen.return_value = ModelResponse(
                text="Python offers rapid prototyping with rich frameworks like Django and FastAPI, while JavaScript provides unified full-stack development with Node.js.",
                model="llama-3.3-70b-versatile",
                provider="groq",
                duration_ms=450.0,
                success=True,
                provenance="MODEL"
            )

            res = run_planner_task("Compare Python and JavaScript for backend development", quiet=True)

            self.assertIn("Python", res)
            self.assertIn("JavaScript", res)

            rec = default_telemetry.get_last()
            self.assertIsNotNone(rec)
            self.assertTrue(rec.reasoning_required)
            self.assertEqual(rec.llm_calls_this_request, 1)
            self.assertEqual(rec.provenance, "MODEL")

    def test_03_strict_provenance_tracking(self):
        """Every response is tagged with its true provenance source."""
        # 1. Memory provenance
        default_memory.add_memory("FACT", "user", "my_name", "Jai")
        run_planner_task("what is my name?", quiet=True)
        rec_mem = default_telemetry.get_last()
        self.assertEqual(rec_mem.provenance, "MEMORY")

        # 2. World State provenance
        run_planner_task("open terminal", quiet=True)
        run_planner_task("what app did we just open?", quiet=True)
        rec_ws = default_telemetry.get_last()
        self.assertEqual(rec_ws.provenance, "WORLD_STATE")

        # 3. Static educational provenance
        run_planner_task("what is tcp?", quiet=True)
        rec_static = default_telemetry.get_last()
        self.assertEqual(rec_static.provenance, "STATIC")

        # 4. Observed screen provenance
        run_planner_task("what is on my screen right now?", quiet=True)
        rec_obs = default_telemetry.get_last()
        self.assertEqual(rec_obs.provenance, "OBSERVED")

    def test_04_search_only_vs_search_and_synthesize(self):
        """Distinguishes SEARCH ONLY (0 LLM calls) from SEARCH + SYNTHESIZE."""
        # 1. Search only: 0 LLM calls
        run_planner_task("search Marvel", quiet=True)
        rec_search = default_telemetry.get_last()
        self.assertEqual(rec_search.llm_calls_this_request, 0)
        self.assertEqual(rec_search.provenance, "WEB")

        # 2. Search + synthesize
        with patch.object(default_gateway, "generate") as mock_gen:
            mock_gen.return_value = ModelResponse(
                text="Marvel produces iconic superhero franchises including the MCU.",
                model="llama-3.3-70b-versatile",
                provider="groq",
                duration_ms=300.0,
                success=True,
                provenance=ProvenanceSource.WEB_AND_MODEL.value
            )
            with patch("core.cognition.research_topic") as mock_research:
                mock_research.return_value = {
                    "success": True,
                    "findings": ["Marvel Studios produces films", "Stan Lee created Marvel heroes"],
                    "sources": ["https://marvel.com"]
                }
                res = run_planner_task("search Marvel and summarize what you find", quiet=True)
                self.assertIn("Marvel", res)

    def test_05_freshness_triggers_force_web_retrieval(self):
        """Freshness triggers ('latest', 'recent') route to web retrieval rather than static guesses."""
        with patch.object(default_cognition, "execute_web_research") as mock_res:
            mock_res.return_value = {
                "text": "Python 3.13.0 was released in October 2024 featuring an experimental free-threaded mode.",
                "provenance": "WEB",
                "model_used": "NONE"
            }
            res = run_planner_task("find the latest Python release information", quiet=True)
            self.assertIn("3.13", res)
            mock_res.assert_called()

    def test_06_contextual_reference_resolution(self):
        """Resolves conversational pronouns ('close it', 'focus it') using short-term memory."""
        # Turn 1: Open Brave
        run_planner_task("open brave", quiet=True)
        # Turn 2: Close it (should resolve to "close brave")
        res = run_planner_task("close it", quiet=True)
        self.assertIn("Brave", res)

    def test_07_goal_state_lifecycle_management(self):
        """Explicit GoalState tracks lifecycle from PENDING -> RUNNING -> COMPLETED."""
        plan = ExecutionPlan(goal="Test multi-step task")
        self.assertEqual(plan.goal_state.status, "PENDING")

        step1 = ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"})
        plan.add_step(step1)
        self.assertEqual(plan.goal_state.remaining_steps, ["OPEN_APP"])

        # Record step completion
        plan.record_result(0, {"success": True}, success=True)
        self.assertIn("OPEN_APP", plan.goal_state.completed_steps)
        self.assertEqual(plan.goal_state.remaining_steps, [])

    def test_08_consequential_safety_confirmation_and_hard_block(self):
        """Consequential and destructive actions ('rm -rf /') are blocked in <10ms with 0 execution."""
        t0 = time.perf_counter()
        res = run_planner_task("rm -rf /", quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("Safety Block", res)
        self.assertLess(dur_ms, 10.0)

        rec = default_telemetry.get_last()
        self.assertEqual(rec.llm_calls_this_request, 0)
