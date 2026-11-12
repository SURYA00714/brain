"""
Test Suite for Phase 2.2 — Universal Intelligence Improvement & Generalization.
Verifies Conditional Intelligence Layer (DIRECT, ASSISTED, VERIFIED),
contradiction detection precision, and non-intervention on premise-based reasoning.
"""

import unittest
from unittest.mock import MagicMock, patch

from core.universal_reasoning import (
    UniversalReasoningOrchestrator,
    UniversalStrategy,
    ExecutionMode,
    UniversalReasoningResult,
)
from core.math_logic import (
    detect_logical_contradictions,
    try_deterministic_math_or_logic,
)
from models.universal_adapter import UniversalModelAdapter, ModelMetadata
from models.capability_profiler import ModelCapabilityProfiler, ModelCapabilityProfile
from models.gateway import ModelResponse


class TestPhase22ConditionalIntelligence(unittest.TestCase):

    def setUp(self):
        self.mock_adapter = MagicMock(spec=UniversalModelAdapter)
        self.mock_adapter.active_model = "test-model-2b"
        self.mock_profile = ModelCapabilityProfile(
            model_id="test-model-2b",
            timestamp="2026-11-12T00:00:00",
            overall_capability_score=80.0,
            capabilities={
                "logical_reasoning": {"score": 0.8, "status": "MEASURED", "passed": True},
                "causal_reasoning": {"score": 0.8, "status": "MEASURED", "passed": True},
                "mathematical_reasoning": {"score": 0.6, "status": "MEASURED", "passed": False},
                "instruction_following": {"score": 0.5, "status": "MEASURED", "passed": False},
            },
        )
        self.mock_profiler = MagicMock(spec=ModelCapabilityProfiler)
        self.mock_profiler.get_or_infer_profile.return_value = self.mock_profile
        self.orchestrator = UniversalReasoningOrchestrator(
            adapter=self.mock_adapter, profiler=self.mock_profiler
        )

    def test_01_execution_mode_classification(self):
        """Verifies DIRECT, ASSISTED, and VERIFIED modes are correctly routed."""
        # 1. VERIFIED: Deterministic math
        mode_math = self.orchestrator.classify_execution_mode("Calculate 15 * 8", self.mock_profile)
        self.assertEqual(mode_math, ExecutionMode.VERIFIED)

        # 2. VERIFIED: Strict constraints
        mode_constraint = self.orchestrator.classify_execution_mode(
            "Write a poem. NEVER use the word 'cat'.", self.mock_profile
        )
        self.assertEqual(mode_constraint, ExecutionMode.VERIFIED)

        # 3. DIRECT: Causal reasoning
        mode_causal = self.orchestrator.classify_execution_mode(
            "The laptop throttled because the fan failed and CPU temperature reached 95C. What caused the throttling?",
            self.mock_profile
        )
        self.assertEqual(mode_causal, ExecutionMode.DIRECT)

        # 4. DIRECT: Inductive reasoning
        mode_inductive = self.orchestrator.classify_execution_mode(
            "The sun rose in the east on Monday, Tuesday, Wednesday, and Thursday. Where will it rise on Friday?",
            self.mock_profile
        )
        self.assertEqual(mode_inductive, ExecutionMode.DIRECT)

        # 5. ASSISTED: Complex multi-part planning
        mode_planning = self.orchestrator.classify_execution_mode(
            "Create a step-by-step procedure to migrate a production PostgreSQL database to a new server with minimal downtime, including pre-checks, backup, data replication, DNS cutover, and post-migration verification.",
            self.mock_profile
        )
        self.assertEqual(mode_planning, ExecutionMode.ASSISTED)

    def test_02_contradiction_detection_precision(self):
        """Verifies contradiction detector does not fire on valid multi-attribute or transition metrics."""
        # Multi-attribute specs: 8 GB system + 4 GB app (CAR_10)
        s1 = ["The system has 8 GB of RAM.", "The application was allocated 4 GB."]
        contra1 = detect_logical_contradictions(s1)
        self.assertEqual(len(contra1), 0, f"Expected 0 contradictions, got: {contra1}")

        # Transition / speedup: 800ms -> 5ms (CAR_07)
        s2 = ["The query previously took 800 ms to execute.", "Adding an index caused a speedup to 5 ms."]
        contra2 = detect_logical_contradictions(s2)
        self.assertEqual(len(contra2), 0, f"Expected 0 contradictions, got: {contra2}")

        # Genuine contradiction: X is enabled vs X is disabled
        s3 = ["Firewall is enabled.", "Firewall is disabled."]
        contra3 = detect_logical_contradictions(s3)
        self.assertTrue(len(contra3) > 0, "Expected genuine contradiction detected.")

    def test_03_alphanumeric_sequence_isolation(self):
        """Verifies deterministic sequence solver does NOT corrupt alphanumeric sequences like A1, B2."""
        res = try_deterministic_math_or_logic("What comes next in the sequence A1, B2, C3, D4, ?")
        self.assertIsNone(res, "Alphanumeric sequence should not be intercepted by pure numeric solver")

        # Pure numeric sequences should still be solved
        res_num = try_deterministic_math_or_logic("Next number in sequence 2, 4, 6, 8, ?")
        self.assertIsNotNone(res_num)
        self.assertTrue(res_num.get("solved"))
        self.assertIn("10", str(res_num.get("answer")))

    def test_04_direct_mode_execution_unencumbered(self):
        """Verifies DIRECT mode does not inject uncertainty prompt disclaimers."""
        self.mock_adapter.generate.return_value = ModelResponse(
            text="The throttling was caused by high CPU temperature due to fan failure.",
            success=True,
            model="test-model-2b",
            duration_ms=45.0,
        )

        prompt = "The CPU throttled because temperature reached 95C after the cooling fan stopped. What was the cause?"
        res = self.orchestrator.solve(prompt)

        self.assertEqual(res.mode, "DIRECT")
        self.assertEqual(res.execution_path, "LLM_DIRECT")
        self.assertTrue(res.verified)
        self.assertIn("fan failure", res.text)

        # Verify system prompt passed to adapter did NOT contain "cannot be verified"
        call_kwargs = self.mock_adapter.generate.call_args[1]
        sys_prompt = call_kwargs.get("system_prompt", "")
        self.assertNotIn("cannot be verified", sys_prompt)


if __name__ == "__main__":
    unittest.main()
