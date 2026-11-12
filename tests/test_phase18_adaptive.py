import tempfile
import unittest
from pathlib import Path
from core.adaptive import AdaptiveIntelligenceEngine, ProceduralRecord
from core.learning import ControlledLearningPipeline
from core.memory import MemoryStore


class TestPhase18AdaptiveIntelligence(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryStore(db_path=":memory:")
        self.learning = ControlledLearningPipeline(db_path=":memory:")
        self.engine = AdaptiveIntelligenceEngine(
            db_path=":memory:",
            memory_store=self.mem,
            learning_pipeline=self.learning,
        )

    def tearDown(self):
        self.engine.close()
        self.learning.close()
        self.mem.close()

    def test_stage1_experience_learning_and_unverified_downgrade(self):
        # Unverified result must NEVER be stored as SUCCESS
        self.engine.record_experience(
            user_request="Check system memory and disk",
            strategy_used="STANDARD_PLANNING",
            plan_dict={"steps": [{"tool": "MEMORY_STATUS"}]},
            tools_selected=["MEMORY_STATUS"],
            tool_results=[{"success": True}],
            duration_ms=12.0,
            verification_outcome="UNVERIFIED",
            outcome="SUCCESS",
        )
        exps = self.engine.search_experiences("Check system memory")
        self.assertEqual(len(exps), 1)
        self.assertEqual(exps[0].outcome, "UNVERIFIED")

        # Irrelevant query must return empty
        irrelevant = self.engine.search_experiences("quantum astrophysics black hole")
        self.assertEqual(irrelevant, [])

    def test_stage2_and_4_strategy_selection_procedural_reuse_and_invalidation(self):
        proc = ProceduralRecord(
            name="check_system_health",
            task_category="SYSTEM_HEALTH",
            preconditions=["local_os_linux"],
            required_permissions="LEVEL_1_SAFE",
            steps=[{"tool": "MEMORY_STATUS"}, {"tool": "CHECK_DISK_SPACE"}],
            expected_outputs="RAM and disk metrics",
            verification_conditions="Non-empty dict payloads",
            success_count=3,
            failure_count=0,
        )
        self.engine.store_procedure(proc)

        decision = self.engine.select_strategy("Check system health memory and disk")
        self.assertEqual(decision["strategy"], "REUSE_PROCEDURE")
        self.assertEqual(decision["procedure"]["name"], "check_system_health")

        # Invalidate procedure -> no longer reused
        self.assertTrue(self.engine.invalidate_procedure("check_system_health"))
        decision2 = self.engine.select_strategy("Check system health memory and disk")
        self.assertEqual(decision2["strategy"], "STANDARD_PLANNING")

    def test_stage2_repeated_failure_triggers_alternative_strategy(self):
        self.engine.record_experience(
            user_request="Search web for linux kernel",
            strategy_used="BACKGROUND_SEARCH",
            plan_dict={"steps": [{"tool": "BROWSER_SEARCH"}]},
            tools_selected=["BROWSER_SEARCH"],
            tool_results=[{"success": False}],
            duration_ms=5000.0,
            verification_outcome="FAILED",
            outcome="FAILURE",
            errors=["timeout"],
        )
        decision = self.engine.select_strategy("Search web for linux kernel")
        self.assertEqual(decision["strategy"], "ALTERNATIVE_STRATEGY")
        self.assertIn("BROWSER_SEARCH", decision["avoid_tools"])

    def test_stage3_ten_standardized_failure_categories(self):
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("TOOL_FAILURE", "Level 3 confirmation required"), "PERMISSION_BLOCK")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("TOOL_FAILURE", "missing parameter path"), "INVALID_PARAMETERS")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("FAILED_PLAN", "Hallucinated tool name"), "TOOL_SELECTION_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("FAILED_PLAN", "Circular dependency detected"), "PLANNING_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("TOOL_FAILURE", "Verification failed"), "VERIFICATION_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("INCORRECT_ANSWER", "Could not verify evidence"), "SEARCH_EVIDENCE_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("REPEATED_MISUNDERSTANDING", "Please clarify"), "USER_INPUT_AMBIGUITY")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("USER_CORRECTION", "Conflicting context"), "CONTEXT_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("TOOL_FAILURE", "Connection timeout"), "TOOL_EXECUTION_ERROR")
        self.assertEqual(ControlledLearningPipeline.classify_root_cause("INCORRECT_ANSWER", "Contains forbidden char"), "MODEL_ERROR")

    def test_stage5_user_feedback_intelligence(self):
        temp = self.engine.process_user_feedback("Use Firefox just for now", subject="user", key="browser", corrected_value="Firefox")
        self.assertEqual(temp["classification"], "TEMPORARY_INSTRUCTION")
        self.assertFalse(temp["persisted"])

        conv = self.engine.process_user_feedback("Sounds good, thanks!")
        self.assertEqual(conv["classification"], "CONVERSATIONAL")
        self.assertFalse(conv["persisted"])

        corr = self.engine.process_user_feedback("That is incorrect, my city is Mysore", subject="user", key="city", corrected_value="Mysore")
        self.assertEqual(corr["classification"], "VERIFIED_FACTUAL_CORRECTION")
        self.assertTrue(corr["persisted"])
        self.assertEqual(self.mem.get_memory("FACT", "user", "city").value, "Mysore")

    def test_stage6_self_evaluation_deterministic(self):
        ev = self.engine.evaluate_task_execution(
            user_request="Check memory",
            strategy_decision={"strategy": "STANDARD_PLANNING"},
            plan_valid=True,
            execution_result={
                "status": "SUCCESS",
                "plan": {"steps": [{"tool": "MEMORY_STATUS", "status": "SUCCESS", "verification_status": "VERIFIED", "retry_count": 0}]},
            },
            model_calls=1,
        )
        self.assertTrue(ev["independently_verified"])
        self.assertTrue(ev["completion_criteria_met"])

    def test_stage7_controlled_dataset_split_and_scrubbing(self):
        id1 = self.learning.record_failure("INCORRECT_ANSWER", "q1", "bad1", "forbidden")
        id2 = self.learning.record_failure("INCORRECT_ANSWER", "q2", "bad2", "forbidden")
        id3 = self.learning.record_failure("INCORRECT_ANSWER", "q1", "bad1", "forbidden")  # Duplicate
        id4 = self.learning.record_failure("INCORRECT_ANSWER", "password=secret123", "bad4", "forbidden")  # Sensitive
        self.learning.propose_and_evaluate_correction(id1, "good1")
        self.learning.propose_and_evaluate_correction(id2, "good2")
        self.learning.propose_and_evaluate_correction(id3, "good1")
        self.learning.propose_and_evaluate_correction(id4, "good4")

        with tempfile.TemporaryDirectory() as tmp:
            tr, ev = self.learning.export_split_datasets(Path(tmp) / "train.jsonl", Path(tmp) / "eval.jsonl", eval_ratio=0.5)
            self.assertEqual(tr + ev, 2)  # Duplicate + sensitive excluded!
            self.assertEqual(tr, 1)
            self.assertEqual(ev, 1)

    def test_stage8_strategy_stats_sample_size_guard(self):
        for i in range(2):
            self.engine.record_experience(
                user_request=f"Check cpu {i}",
                strategy_used="STANDARD_PLANNING",
                plan_dict={},
                tools_selected=["CPU_STATUS"],
                tool_results=[{"success": True}],
                duration_ms=10.0,
                verification_outcome="VERIFIED",
                outcome="SUCCESS",
            )
        stats2 = self.engine.get_strategy_stats("SYSTEM_HEALTH", "STANDARD_PLANNING", min_samples=3)
        self.assertTrue(stats2["insufficient_samples"])

        self.engine.record_experience(
            user_request="Check cpu 3",
            strategy_used="STANDARD_PLANNING",
            plan_dict={},
            tools_selected=["CPU_STATUS"],
            tool_results=[{"success": True}],
            duration_ms=10.0,
            verification_outcome="VERIFIED",
            outcome="SUCCESS",
        )
        stats3 = self.engine.get_strategy_stats("SYSTEM_HEALTH", "STANDARD_PLANNING", min_samples=3)
        self.assertFalse(stats3["insufficient_samples"])
        self.assertEqual(stats3["task_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
