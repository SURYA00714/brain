import unittest
from unittest.mock import MagicMock
from core.context import ContextBuilder, ShortTermMemory
from core.math_logic import (
    convert_units,
    detect_logical_contradictions,
    safe_eval_arithmetic,
    solve_sequence_pattern,
    try_deterministic_math_or_logic,
)
from core.memory import MemoryStore
from core.reasoning import (
    AdvancedPlanner,
    DeepReasoningEngine,
    ReasoningStrategy,
    select_reasoning_strategy,
    verify_response_multipass,
)
from models.gateway import ModelResponse


class TestPhase19Reasoning(unittest.TestCase):
    def test_stage4_deterministic_math_and_logic(self):
        self.assertEqual(safe_eval_arithmetic("(12 + 8) * 3"), 60.0)
        self.assertIsNone(safe_eval_arithmetic("__import__('os').system('ls')"))
        self.assertIsNone(safe_eval_arithmetic("10 / 0"))

        self.assertEqual(convert_units(4, "gb", "mb"), 4096.0)
        self.assertEqual(convert_units(100, "c", "f"), 212.0)

        self.assertEqual(solve_sequence_pattern([2, 6, 12, 20, 30])["next"], 42.0)
        self.assertEqual(solve_sequence_pattern([1, 1, 2, 3, 5])["next"], 8.0)
        self.assertEqual(solve_sequence_pattern([3, 6, 12, 24])["next"], 48.0)

        contras = detect_logical_contradictions(["Ollama is active.", "Ollama is not active."])
        self.assertEqual(len(contras), 1)

        self.assertEqual(try_deterministic_math_or_logic("What is 15% of 240?")["answer"], "36")
        self.assertEqual(try_deterministic_math_or_logic("convert 2 gb to mb")["answer"], "2048 mb")
        self.assertIn("42", try_deterministic_math_or_logic("next number in sequence 2, 6, 12, 20, 30")["answer"])

    def test_stage2_strategy_router_and_adaptive_budgets(self):
        r_amb = select_reasoning_strategy("fix this")
        self.assertEqual(r_amb["strategy"], ReasoningStrategy.UNCERTAINTY_ANALYSIS)
        self.assertFalse(r_amb["needs_llm"])

        r_web = select_reasoning_strategy("What happened today?")
        self.assertEqual(r_web["strategy"], ReasoningStrategy.EVIDENCE_BASED_REASONING)

        r_cmp = select_reasoning_strategy("Compare Python vs Rust for CLI tools")
        self.assertEqual(r_cmp["strategy"], ReasoningStrategy.ALTERNATIVE_COMPARISON)

        r_simple = select_reasoning_strategy("Hi")
        self.assertEqual(r_simple["strategy"], ReasoningStrategy.DIRECT_RESPONSE)
        self.assertEqual(r_simple["num_predict"], 128)

    def test_stage1_and_3_deep_reasoning_and_multipass_verify(self):
        # Deterministic math fast path uses 0 LLM calls
        mock_gw = MagicMock()
        eng = DeepReasoningEngine(gateway=mock_gw)
        res = eng.solve("What is 25% of 80?")
        self.assertEqual(res["answer"], "20")
        self.assertEqual(res["model_calls"], 0)
        mock_gw.generate.assert_not_called()

        # Multi-pass verification catches contradiction and triggers bounded repair
        mock_gw.generate.side_effect = [
            ModelResponse(text="Python is typed. Python is not typed.", success=True),
            ModelResponse(text="Python is dynamically typed.", success=True),
        ]
        res2 = eng.solve("Describe Python typing")
        self.assertTrue(res2["verified"])
        self.assertEqual(res2["model_calls"], 2)

        # Direct verifier check
        v_bad = verify_response_multipass("What is 10 + 5?", "The answer is 14.")
        self.assertFalse(v_bad["verified"])

    def test_stage5_advanced_planner_compare_strategies(self):
        cmp_fast = AdvancedPlanner.compare_strategies("Check memory status", ["MEMORY_STATUS"])
        self.assertEqual(cmp_fast["selected"]["name"], "FAST_DETERMINISTIC")

        cmp_multi = AdvancedPlanner.compare_strategies("Open terminal and check cpu", ["OPEN_APP", "CPU_STATUS"])
        self.assertEqual(cmp_multi["selected"]["name"], "MULTI_STEP_VERIFIED_PLAN")

    def test_stage6_context_dedup_and_conflict_detection(self):
        mem = MemoryStore(db_path=":memory:")
        mem.add_memory("FACT", "user", "browser", "Brave")
        mem.add_memory("PREFERENCE", "user", "browser", "Firefox")
        cb = ContextBuilder(memory_store=mem, short_term_mem=ShortTermMemory())
        ctx = cb.build_system_context("What is my browser?")
        self.assertIn("[CONFLICT]", ctx)
        self.assertIn("Brave", ctx)
        self.assertIn("Firefox", ctx)
        mem.close()


if __name__ == "__main__":
    unittest.main()
