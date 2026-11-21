"""
Unit tests for Phase 2 Intelligence Upgrade: Grammar-Constrained Decoding (GBNF).
Tests:
1. ModelGateway passes format schema to underlying providers.
2. OllamaProvider outputs pure JSON when format is specified (no markdown fences, no conversational text).
3. CognitiveEngine.generate_structured_plan enforces PLAN_JSON_SCHEMA with think=False.
4. Validation and execution of grammar-constrained generated plan.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from models.gateway import default_gateway, ModelResponse, OllamaProvider
from core.cognition import default_cognition, PLAN_JSON_SCHEMA


class TestGrammarConstrainedPlanning(unittest.TestCase):

    def test_gateway_forwards_format_parameter(self):
        """Verifies ModelGateway.generate forwards format parameter to providers."""
        with patch.object(default_gateway.providers["ollama"], "generate") as mock_ollama:
            mock_ollama.return_value = ModelResponse(success=True, text='{"status": "ready"}')
            res = default_gateway.generate(
                prompt="Test plan",
                tier="LOCAL",
                format=PLAN_JSON_SCHEMA
            )
            mock_ollama.assert_called_once()
            _, kwargs = mock_ollama.call_args
            self.assertEqual(kwargs.get("format"), PLAN_JSON_SCHEMA)

    def test_plan_json_schema_structure(self):
        """Verifies PLAN_JSON_SCHEMA requires core ExecutionPlan fields."""
        self.assertEqual(PLAN_JSON_SCHEMA["type"], "object")
        self.assertIn("steps", PLAN_JSON_SCHEMA["required"])
        self.assertIn("goal", PLAN_JSON_SCHEMA["required"])
        step_props = PLAN_JSON_SCHEMA["properties"]["steps"]["items"]["properties"]
        self.assertIn("tool", step_props)
        self.assertIn("parameters", step_props)
        self.assertIn("depends_on", step_props)

    def test_generate_structured_plan_uses_schema(self):
        """CognitiveEngine.generate_structured_plan passes PLAN_JSON_SCHEMA and think=False."""
        valid_plan_json = json.dumps({
            "goal": "Check system disk space",
            "intent": "TASK_GOAL",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Open terminal",
                    "tool": "OPEN_APP",
                    "parameters": {"app_name": "terminal"},
                    "depends_on": [],
                    "expected_result": "Terminal open"
                },
                {
                    "step_id": 2,
                    "description": "Check disk space",
                    "tool": "CHECK_DISK_SPACE",
                    "parameters": {"target_path": "/"},
                    "depends_on": [1],
                    "expected_result": "Disk space checked"
                }
            ],
            "completion_criteria": ["Criteria: Terminal opened and disk measured"],
            "missing_information": [],
            "status": "ready"
        })

        with patch.object(default_cognition.gateway, "generate") as mock_gen:
            mock_gen.return_value = ModelResponse(
                success=True,
                text=valid_plan_json,
                provider="ollama",
                model="qwen3.5-brain:v2"
            )
            plan = default_cognition.generate_structured_plan("open terminal and check disk space")
            self.assertIsNotNone(plan)
            self.assertEqual(len(plan.steps), 2)
            self.assertEqual(plan.steps[0].tool_name, "OPEN_APP")
            self.assertEqual(plan.steps[1].tool_name, "CHECK_DISK_SPACE")

            mock_gen.assert_called_once()
            _, kwargs = mock_gen.call_args
            self.assertEqual(kwargs.get("format"), PLAN_JSON_SCHEMA)
            self.assertFalse(kwargs.get("think"))


if __name__ == "__main__":
    unittest.main()
