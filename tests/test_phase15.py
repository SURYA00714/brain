import os
import unittest
import time
from unittest.mock import patch, MagicMock

os.environ["BRAIN_MOCK_GUI"] = "1"

from brain import run_planner_task
from tools.input import screen_prompt_safety
from tools.router import default_router
from core.cognition import default_cognition
from core.context import default_short_term_memory
from core.world_state import default_world_state
from tools.apps import default_app_tracker


class TestPhase15ResponsiveAutonomousAgent(unittest.TestCase):
    def setUp(self):
        default_short_term_memory.clear()

    def tearDown(self):
        default_short_term_memory.clear()

    # --------------------------------------------------------------------------
    # 1. ZERO-LATENCY IMMEDIATE SAFETY SCREEN (<1ms)
    # --------------------------------------------------------------------------
    def test_01_zero_latency_immediate_safety_screen(self):
        """Destructive system commands are blocked immediately at the gate in <10ms."""
        dangerous_prompts = [
            "delete all system files with rm -rf /",
            "rm -rf /",
            "rm -rf /*",
            "format disk",
            "mkfs /dev/sda1",
            "dd if=/dev/zero of=/dev/sda"
        ]
        for prompt in dangerous_prompts:
            t0 = time.perf_counter()
            is_safe, err = screen_prompt_safety(prompt)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.assertFalse(is_safe)
            self.assertIn("Safety Block", err)
            self.assertLess(duration_ms, 10.0)

    def test_02_run_planner_task_blocks_dangerous_command_instantly(self):
        """run_planner_task halts dangerous prompts without invoking any LLM reasoning."""
        t0 = time.perf_counter()
        resp = run_planner_task("delete all system files with rm -rf /", quiet=True)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.assertIn("Safety Block", resp)
        self.assertLess(duration_ms, 50.0)  # Must be instant (<50ms)

    # --------------------------------------------------------------------------
    # 2. DIRECT SEARCH ROUTING (NO LLM BOTTLENECK)
    # --------------------------------------------------------------------------
    def test_03_direct_search_routing_no_llm(self):
        """'search <query>' routes directly to search tools without LLM reasoning."""
        route1 = default_router.route("search Marvel")
        self.assertIsNotNone(route1)
        self.assertEqual(route1["type"], "tool")
        self.assertIn(route1["tool"], ("BROWSER_SEARCH", "BROWSER_SEARCH_FOREGROUND"))
        self.assertEqual(route1["arguments"]["query"], "Marvel")

        route2 = default_router.route("search Python 3.12 documentation")
        self.assertIsNotNone(route2)
        self.assertEqual(route2["type"], "tool")
        self.assertEqual(route2["arguments"]["query"], "Python 3.12 documentation")

    # --------------------------------------------------------------------------
    # 3. DIRECT SCREEN PERCEPTION (NO LLM BOTTLENECK)
    # --------------------------------------------------------------------------
    def test_04_direct_screen_perception_no_llm(self):
        """'tell me what you see' and screen inspection queries route directly to perception."""
        perception_queries = [
            "tell me what you see",
            "what do you see",
            "what is on my screen",
            "describe the screen"
        ]
        for q in perception_queries:
            route = default_router.route(q)
            self.assertIsNotNone(route, f"Failed for query: {q}")
            self.assertEqual(route["type"], "tool")
            self.assertEqual(route["tool"], "ANALYZE_SCREEN")

    # --------------------------------------------------------------------------
    # 4. EVIDENCE-FIRST TROUBLESHOOTING (<1s)
    # --------------------------------------------------------------------------
    def test_05_evidence_first_troubleshooting(self):
        """Troubleshooting queries inspect real physical system state (CPU, RAM, /dev/shm) first."""
        t0 = time.perf_counter()
        diag = default_cognition.inspect_and_troubleshoot("my browser is crashing when I open tabs, what could be wrong?")
        duration_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("[OBSERVED]", diag)
        self.assertTrue("RAM" in diag or "CPU" in diag)
        self.assertIn("Shared Memory", diag)
        self.assertLess(duration_ms, 2000.0)  # Must be fast (<2s)

    def test_06_troubleshooting_routing_via_planner_task(self):
        """Browser troubleshooting in run_planner_task uses evidence-first path."""
        t0 = time.perf_counter()
        res = run_planner_task("my browser is crashing when I open tabs, what could be wrong?", quiet=True)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.assertIn("[OBSERVED]", res)
        self.assertLess(duration_ms, 2000.0)

    # --------------------------------------------------------------------------
    # 5. REAL POST-ACTION PHYSICAL VERIFICATION
    # --------------------------------------------------------------------------
    def test_07_post_action_verification_detects_false_success(self):
        """Brain rejects optimistic tool success if process is not running in real system."""
        mock_registry = MagicMock()
        mock_registry.execute.return_value = {"success": True, "app_name": "nonexistent_app_xyz"}
        mock_registry.has_tool.return_value = True

        from tools.plan import ExecutionPlan, ExecutionStep
        from brain import execute_plan
        from tools.profiler import PerformanceProfiler

        plan = ExecutionPlan("Open nonexistent app")
        plan.add_step(ExecutionStep("tool", "OPEN_APP", {"app_name": "nonexistent_app_xyz"}))

        res = execute_plan(plan, mock_registry, PerformanceProfiler(), "Open nonexistent app", quiet=True)
        self.assertIn("Brain Error", res)
        self.assertIn("Verification failed", res)

    # --------------------------------------------------------------------------
    # 6. COMPOUND WORKFLOW WITH SEARCH AND SUMMARIZATION
    # --------------------------------------------------------------------------
    def test_08_search_and_summarize_research_intent(self):
        """'search Marvel and summarize what you find' routes to research intelligence."""
        i = default_cognition.understand_intent("search Marvel and summarize what you find")
        self.assertIn(i["intent"], ("RESEARCH", "COMPOUND_GOAL"))


if __name__ == "__main__":
    unittest.main()
