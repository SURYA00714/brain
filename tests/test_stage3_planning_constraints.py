import json
import unittest
from unittest.mock import MagicMock
from core.constraints import (
    validate_constraints,
    extract_constraints_from_prompt,
    generate_with_constraints,
)
from core.cognition import CognitiveEngine
from models.gateway import ModelResponse


class TestConstraintsEngine(unittest.TestCase):
    def test_validate_multiple_constraints(self):
        ok, errs = validate_constraints(
            "Python Java Go",
            {"forbidden_chars": [",", "1", "2", "3", "•", "-"], "word_count": 3}
        )
        self.assertTrue(ok)
        self.assertEqual(errs, [])

        ok2, errs2 = validate_constraints(
            "Python is high-level, Java, Go",
            {"forbidden_chars": [",", "-"], "max_words": 4}
        )
        self.assertFalse(ok2)
        self.assertTrue(len(errs2) >= 2)

    def test_validate_numbered_json_and_language(self):
        ok, _ = validate_constraints("1. First\n2. Second", {"numbered_output": True})
        self.assertTrue(ok)
        ok_bad, _ = validate_constraints("First and Second", {"numbered_output": True})
        self.assertFalse(ok_bad)

        ok_json, _ = validate_constraints('{"a": 1}', {"exact_format": "json"})
        self.assertTrue(ok_json)
        ok_json_bad, _ = validate_constraints("not json", {"exact_format": "json"})
        self.assertFalse(ok_json_bad)

        ok_ascii, _ = validate_constraints("Hello world", {"language": "ascii"})
        self.assertTrue(ok_ascii)

    def test_extract_constraints_from_prompts(self):
        c1 = extract_constraints_from_prompt("State the current status in exactly three words.")
        self.assertEqual(c1.get("word_count"), 3)

        c2 = extract_constraints_from_prompt("List three common programming languages. Do NOT use numbers, bullet points, or commas.")
        self.assertIn(",", c2.get("forbidden_chars", []))
        self.assertIn("-", c2.get("forbidden_chars", []))
        self.assertIn("1", c2.get("forbidden_chars", []))

        c3 = extract_constraints_from_prompt("Explain RAM in one sentence without using the word 'memory'.")
        self.assertEqual(c3.get("max_sentences"), 1)
        self.assertIn("memory", c3.get("forbidden_words", []))

    def test_generate_with_constraints_bounded_retry(self):
        mock_gw = MagicMock()
        mock_gw.generate.side_effect = [
            ModelResponse(text="Python is high-level and Java is great.", success=True, model="qwen", provider="ollama"),
            ModelResponse(text="Python Java Go", success=True, model="qwen", provider="ollama"),
        ]
        resp, passed, violations = generate_with_constraints(
            mock_gw,
            "List three common programming languages. Do NOT use numbers, bullet points, or commas.",
            max_retries=2
        )
        self.assertTrue(passed)
        self.assertEqual(violations, [])
        self.assertEqual(resp.text, "Python Java Go")
        self.assertEqual(mock_gw.generate.call_count, 2)


class TestPlanQualityValidator(unittest.TestCase):
    def test_incomplete_pl02_rejected_and_corrected(self):
        eng = CognitiveEngine()
        incomplete_json = json.dumps({
            "goal": "Open terminal and check CPU",
            "intent": "SYSTEM_CHECK",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Open terminal",
                    "tool": "OPEN_APP",
                    "parameters": {"name": "terminal"},
                    "expected_result": "Terminal open"
                }
            ],
            "completion_criteria": ["Terminal opened"],
            "status": "ready"
        })
        complete_json = json.dumps({
            "goal": "Open terminal and check CPU",
            "intent": "SYSTEM_CHECK",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Open terminal",
                    "tool": "OPEN_APP",
                    "parameters": {"name": "terminal"},
                    "depends_on": [],
                    "expected_result": "Terminal open"
                },
                {
                    "step_id": 2,
                    "description": "Check CPU usage",
                    "tool": "CPU_STATUS",
                    "parameters": {},
                    "depends_on": [1],
                    "expected_result": "CPU stats returned"
                }
            ],
            "completion_criteria": ["Terminal opened", "CPU usage measured"],
            "status": "ready"
        })

        # Direct quality check rejects incomplete plan
        ok, err, bad_plan = eng.validate_structured_plan(incomplete_json)
        self.assertTrue(ok)
        q_ok, q_issues = eng.validate_plan_quality(bad_plan, "Open the terminal and check system CPU usage")
        self.assertFalse(q_ok)
        self.assertTrue(any("Incomplete plan" in i for i in q_issues))

        # generate_structured_plan retries once and returns complete plan
        eng.gateway = MagicMock()
        eng.gateway.providers = {"groq": MagicMock(is_available=lambda: False), "gemini": MagicMock(is_available=lambda: False)}
        eng.gateway.generate.side_effect = [
            ModelResponse(text=incomplete_json, success=True, model="qwen", provider="ollama"),
            ModelResponse(text=complete_json, success=True, model="qwen", provider="ollama"),
        ]
        plan = eng.generate_structured_plan("Open the terminal and check system CPU usage", tier="LOCAL")
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual([s.tool_name for s in plan.steps], ["OPEN_APP", "CPU_STATUS"])

    def test_dependency_consistency_and_missing_params_rejected(self):
        eng = CognitiveEngine()
        bad_deps_json = json.dumps({
            "goal": "Open app",
            "intent": "OPEN",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Open app",
                    "tool": "OPEN_APP",
                    "parameters": {},  # Missing name/app_name
                    "depends_on": [2],  # Forward dependency
                    "expected_result": "Opened"
                }
            ],
            "status": "ready"  # Missing completion_criteria
        })
        ok, _, plan = eng.validate_structured_plan(bad_deps_json)
        self.assertTrue(ok)
        q_ok, q_issues = eng.validate_plan_quality(plan, "Open app")
        self.assertFalse(q_ok)
        self.assertTrue(any("precede" in i for i in q_issues))
        self.assertTrue(any("parameter error" in i for i in q_issues))
        self.assertTrue(any("completion_criteria" in i for i in q_issues))


if __name__ == "__main__":
    unittest.main()
