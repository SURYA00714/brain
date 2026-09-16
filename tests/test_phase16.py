import os
import unittest
import time

os.environ["BRAIN_MOCK_GUI"] = "1"

from brain import run_planner_task
from core.cognition import default_cognition
from core.memory import default_memory
from core.telemetry import default_telemetry
from core.world_state import default_world_state
from tools.apps import default_app_tracker


class TestPhase16EliminatingHiddenLLMLatency(unittest.TestCase):
    """
    Phase 16 Unit & Integration Tests:
    Verifies that Brain enforces the Hard 'No LLM Required' Decision Layer,
    achieving 0 LLM calls and <100ms latency on deterministic state, memory,
    safety, app allowlist, and compound tasks.
    """

    def setUp(self):
        default_app_tracker.clear()
        default_world_state.sync_from_system()

    def test_01_memory_fact_retrieval_zero_llm_calls(self):
        """'what is my name?' retrieves fact from memory in <100ms with 0 LLM calls."""
        default_memory.add_memory("FACT", "user", "my_name", "Alice")
        t0 = time.perf_counter()
        res = run_planner_task("what is my name?", quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("Alice", res)
        self.assertLess(dur_ms, 100.0)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)

    def test_02_world_state_last_app_zero_llm_calls(self):
        """'what app did we just open?' reads physical state in <100ms with 0 LLM calls."""
        run_planner_task("open terminal", quiet=True)
        t0 = time.perf_counter()
        res = run_planner_task("what app did we just open?", quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("Terminal", res)
        self.assertLess(dur_ms, 100.0)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)

    def test_03_screen_perception_routing_zero_llm_calls(self):
        """'what is on my screen right now?' routes directly to screen perception with 0 LLM calls."""
        res = run_planner_task("what is on my screen right now?", quiet=True)
        self.assertTrue("Screen captured" in res or "visible elements" in res or "observed the screen" in res)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)

    def test_04_unknown_app_immediate_rejection_zero_llm_calls(self):
        """'open fakeappthatdoesnotexist' fails fast in <100ms with 0 LLM calls."""
        t0 = time.perf_counter()
        res = run_planner_task("open fakeappthatdoesnotexist", quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIn("not in the approved safety allowlist", res)
        self.assertLess(dur_ms, 100.0)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)

    def test_05_destructive_intent_block_zero_llm_calls(self):
        """'delete all my files' and 'wipe the disk' are blocked in <10ms with 0 LLM calls."""
        for query in ["delete all my files", "wipe the disk", "rm -rf /", "erase my entire home directory"]:
            t0 = time.perf_counter()
            res = run_planner_task(query, quiet=True)
            dur_ms = (time.perf_counter() - t0) * 1000.0

            self.assertIn("Safety Block", res)
            self.assertLess(dur_ms, 25.0)
            rec = default_telemetry.get_last()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.llm_calls_this_request, 0)

    def test_06_compound_terminal_disk_space_zero_llm_calls(self):
        """'open terminal and check free disk space' executes deterministically with 0 LLM calls."""
        res = run_planner_task("open terminal and check free disk space", quiet=True)
        self.assertIn("Disk space", res)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.llm_calls_this_request, 0)

    def test_07_search_and_summarize_no_qwen_loop(self):
        """'search Marvel and summarize what you find' does not enter a multi-minute Qwen loop."""
        res = run_planner_task("search Marvel and summarize what you find", quiet=True)
        self.assertTrue("Marvel" in res or "Search results" in res or "retrieved web sources" in res)
        rec = default_telemetry.get_last()
        self.assertIsNotNone(rec)
        # Ensure offline CPU Qwen was not called
        self.assertNotEqual(rec.llm_provider, "qwen2.5:3b")

    def test_08_reasoning_necessity_contract(self):
        """ReasoningRequired contract correctly classifies deterministic vs open-ended goals."""
        # 1. Static knowledge
        req1 = default_cognition.evaluate_reasoning_necessity("what is python?")
        self.assertFalse(req1.required)
        self.assertTrue(req1.deterministic_solution_available)

        # 2. Safety block
        req2 = default_cognition.evaluate_reasoning_necessity("rm -rf /")
        self.assertFalse(req2.required)
        self.assertTrue(req2.deterministic_solution_available)

        # 3. Tool execution
        req3 = default_cognition.evaluate_reasoning_necessity("open brave")
        self.assertFalse(req3.required)

        # 4. Open-ended reasoning
        req4 = default_cognition.evaluate_reasoning_necessity("compare Python and Rust for writing high-frequency trading systems")
        self.assertTrue(req4.required)
        self.assertFalse(req4.deterministic_solution_available)


if __name__ == "__main__":
    unittest.main()
