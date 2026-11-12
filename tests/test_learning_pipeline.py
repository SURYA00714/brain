import tempfile
import unittest
from pathlib import Path
from core.learning import ControlledLearningPipeline
from core.constraints import validate_constraints


class TestControlledLearningPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = ControlledLearningPipeline(db_path=":memory:", min_examples_for_finetune=2)

    def tearDown(self):
        self.pipeline.close()

    def test_record_classify_and_reject_bad_correction(self):
        obs_id = self.pipeline.record_failure(
            "INCORRECT_ANSWER",
            "List three languages without commas or hyphens",
            "Python is high-level, Java, Go",
            error_reason="Contains forbidden character '-'"
        )
        # Correction still violates constraint -> must NOT be approved
        ok_bad, _ = self.pipeline.propose_and_evaluate_correction(
            obs_id,
            "Python, Java, Go",
            evaluator_fn=lambda inp, out: (
                validate_constraints(out, {"forbidden_chars": [",", "-"]})[0],
                "checked"
            )
        )
        self.assertFalse(ok_bad)
        self.assertEqual(len(self.pipeline.get_approved_examples()), 0)

        # Valid correction -> approved
        ok_good, _ = self.pipeline.propose_and_evaluate_correction(
            obs_id,
            "Python Java Go",
            evaluator_fn=lambda inp, out: (
                validate_constraints(out, {"forbidden_chars": [",", "-"]})[0],
                "checked"
            )
        )
        self.assertTrue(ok_good)
        approved = self.pipeline.get_approved_examples()
        self.assertEqual(len(approved), 1)
        self.assertIn(approved[0]["root_cause"], ("MODEL_ERROR", "CONSTRAINT_VIOLATION"))

    def test_export_and_finetune_readiness_never_auto_modifies(self):
        id1 = self.pipeline.record_failure("FAILED_PLAN", "Open terminal and check CPU", "[]", "Incomplete plan")
        id2 = self.pipeline.record_failure("USER_CORRECTION", "What browser?", "Chrome", "conflict")
        self.pipeline.propose_and_evaluate_correction(id1, '{"steps": [1, 2]}')
        self.pipeline.propose_and_evaluate_correction(id2, "Brave")

        gate = self.pipeline.check_finetune_readiness(independent_eval_passed=True)
        self.assertTrue(gate["ready_for_offline_finetune"])
        self.assertFalse(gate["auto_modify_weights"])
        self.assertFalse(gate["online_self_training"])

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "train.jsonl"
            count = self.pipeline.export_training_dataset(out_path)
            self.assertEqual(count, 2)
            self.assertTrue(out_path.exists())


if __name__ == "__main__":
    unittest.main()
