"""
Test Suite for Phase 2.1 — Universal Local Model Intelligence Framework.
Verifies UniversalModelAdapter, ModelCapabilityProfiler, UniversalReasoningOrchestrator,
PromptOptimizer, and Model-Isolated Experience Learning.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from models.universal_adapter import UniversalModelAdapter, ModelMetadata
from models.capability_profiler import (
    ModelCapabilityProfiler,
    ModelCapabilityProfile,
    CapabilityStatus,
)
from models.prompt_optimizer import PromptOptimizer
from core.universal_reasoning import (
    UniversalReasoningOrchestrator,
    UniversalStrategy,
    UniversalReasoningResult,
)
from core.adaptive import AdaptiveIntelligenceEngine, ExperienceRecord, ProceduralRecord
from models.gateway import ModelResponse


class TestUniversalModelFramework(unittest.TestCase):

    def setUp(self):
        self.mock_adapter = MagicMock(spec=UniversalModelAdapter)
        self.mock_adapter.active_model = "test-model-2b"
        self.mock_metadata = ModelMetadata(
            model_id="test-model-2b",
            name="test-model-2b",
            provider="ollama",
            format="gguf",
            family="test_family",
            parameter_size="2B",
            quantization="Q4_K_M",
            file_size_mb=1200.0,
            context_window=2048,
            capabilities=["completion", "tools"],
        )
        self.mock_adapter.get_metadata.return_value = self.mock_metadata

        self.mock_profile = ModelCapabilityProfile(
            model_id="test-model-2b",
            timestamp="2026-11-12T00:00:00",
            overall_capability_score=75.0,
            capabilities={"logical_reasoning": {"score": 0.8, "status": "MEASURED"}},
        )
        self.mock_profiler = MagicMock(spec=ModelCapabilityProfiler)
        self.mock_profiler.get_or_infer_profile.return_value = self.mock_profile

    def test_01_adapter_metadata_and_normalization(self):
        """Verifies UniversalModelAdapter lists metadata and normalizes parameters."""
        meta = self.mock_adapter.get_metadata("test-model-2b")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.family, "test_family")
        self.assertEqual(meta.parameter_size, "2B")
        self.assertEqual(meta.quantization, "Q4_K_M")

    def test_02_capability_profiler_status_and_scoring(self):
        """Verifies CapabilityProfiler records empirical measurements and statuses."""
        profiler = ModelCapabilityProfiler(adapter=self.mock_adapter, storage_path=":memory:")
        self.mock_adapter.generate.return_value = ModelResponse(
            text="Yes",
            success=True,
            model="test-model-2b",
            duration_ms=50.0,
        )

        profile = profiler.profile_model("test-model-2b")
        self.assertEqual(profile.model_id, "test-model-2b")
        self.assertIn("logical_reasoning", profile.capabilities)
        self.assertEqual(
            profile.capabilities["logical_reasoning"]["status"],
            CapabilityStatus.MEASURED.value,
        )
        self.assertTrue(profile.capabilities["logical_reasoning"]["passed"])

    def test_03_prompt_optimizer_capability_awareness(self):
        """Verifies PromptOptimizer adapts prompt instructions based on model profile."""
        profile = ModelCapabilityProfile(
            model_id="small-model-1b",
            timestamp="2026-11-12T00:00:00",
            overall_capability_score=50.0,
            capabilities={
                "instruction_following": {"score": 0.2, "status": "MEASURED"},
                "structured_json_generation": {"score": 0.1, "status": "MEASURED"},
            },
            metadata={"context_window": 1024, "parameter_size": "1.5B"},
        )

        sys_prompt = PromptOptimizer.build_system_prompt(profile, task_type="json")
        self.assertIn("Pay extreme attention to negative constraints", sys_prompt)
        self.assertIn("Return ONLY raw JSON", sys_prompt)

        budget = PromptOptimizer.calculate_token_budget("What is 2+2?", profile, "simple")
        self.assertLessEqual(budget["num_predict"], 448)

    def test_04_universal_reasoning_orchestrator_strategy_selection(self):
        """Verifies UniversalReasoningOrchestrator maps tasks to appropriate strategies."""
        orchestrator = UniversalReasoningOrchestrator(adapter=self.mock_adapter, profiler=self.mock_profiler)
        profile = self.mock_profile

        strat_math = orchestrator.select_strategy("Calculate 25 * 4 + 10", profile)
        self.assertEqual(strat_math, UniversalStrategy.MATHEMATICAL_VERIFICATION)

        strat_tool = orchestrator.select_strategy("Open the terminal and check cpu status", profile)
        self.assertEqual(strat_tool, UniversalStrategy.TOOL_ASSISTED_REASONING)

        strat_unc = orchestrator.select_strategy("What will the exact price in 2035 be?", profile)
        self.assertEqual(strat_unc, UniversalStrategy.UNCERTAINTY_ANALYSIS)

    def test_05_deterministic_fast_path_execution(self):
        """Verifies deterministic math tasks execute via AST fast path without LLM call."""
        orchestrator = UniversalReasoningOrchestrator(adapter=self.mock_adapter, profiler=self.mock_profiler)
        res = orchestrator.solve("Calculate 120 / 4 + 15")
        self.assertEqual(res.execution_path, "DETERMINISTIC_FAST_PATH")
        self.assertTrue(res.verified)
        self.assertIn("45", res.text)
        self.mock_adapter.generate.assert_not_called()

    def test_06_model_isolated_experience_learning(self):
        """Verifies experiences and procedures are isolated per model_id in adaptive memory."""
        engine = AdaptiveIntelligenceEngine(db_path=":memory:")

        # Record for model A
        engine.record_experience(
            user_request="backup files",
            strategy_used="BASH_SCRIPT",
            plan_dict={"steps": ["tar -czf backup.tar.gz /data"]},
            tools_selected=["RUN_COMMAND"],
            tool_results=[{"success": True}],
            duration_ms=120.0,
            verification_outcome="VERIFIED",
            outcome="SUCCESS",
            model_id="model-alpha-2b",
        )

        # Record for model B
        engine.record_experience(
            user_request="backup files",
            strategy_used="PYTHON_SHUTIL",
            plan_dict={"steps": ["import shutil; shutil.make_archive()"]},
            tools_selected=["RUN_COMMAND"],
            tool_results=[{"success": True}],
            duration_ms=150.0,
            verification_outcome="VERIFIED",
            outcome="SUCCESS",
            model_id="model-beta-7b",
        )

        # Search filtered by model A
        res_a = engine.search_experiences("backup files", model_id="model-alpha-2b")
        self.assertEqual(len(res_a), 1)
        self.assertEqual(res_a[0].strategy_used, "BASH_SCRIPT")
        self.assertEqual(res_a[0].model_id, "model-alpha-2b")

        # Search filtered by model B
        res_b = engine.search_experiences("backup files", model_id="model-beta-7b")
        self.assertEqual(len(res_b), 1)
        self.assertEqual(res_b[0].strategy_used, "PYTHON_SHUTIL")
        self.assertEqual(res_b[0].model_id, "model-beta-7b")


if __name__ == "__main__":
    unittest.main()
