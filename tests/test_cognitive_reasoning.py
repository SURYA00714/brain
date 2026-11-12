"""
Comprehensive Test Suite for Phase 1.3: Cognitive Reasoning Upgrade.
Tests AI-driven structured planning, schema validation, failure recovery,
and regression safety across familiar and unfamiliar requests.
"""

import os
import json
import unittest
from unittest.mock import patch, MagicMock

from core.cognition import CognitiveEngine
from models.gateway import ModelResponse
from tools.plan import ExecutionPlan, ExecutionStep, GoalState
from tools.registry import default_registry


class TestPhase1_3CognitiveReasoning(unittest.TestCase):

    def setUp(self):
        self.engine = CognitiveEngine()

    # 1. Familiar requests preserve deterministic fast paths
    def test_01_familiar_request_uses_fast_path(self):
        goal = "open brave and search for python documentation"
        plan = self.engine.plan_autonomous_goal(goal)
        self.assertIsNotNone(plan)
        tools = [s.tool_name for s in plan.steps]
        self.assertIn("OPEN_APP", tools)
        self.assertIn("BROWSER_SEARCH_FOREGROUND", tools)
        # Should not call model gateway
        self.assertIsNone(self.engine.last_planning_response)

    # 2. Unfamiliar requests trigger AI-driven structured planning
    def test_02_unfamiliar_request_generates_ai_plan(self):
        mock_plan_json = json.dumps({
            "goal": "Backup project reports to archive",
            "intent": "FILE_ARCHIVE",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Find all report files",
                    "tool": "FIND_FILES",
                    "parameters": {"name_pattern": "*.txt", "path": "/home/jai/Downloads/Brain"},
                    "expected_result": "List of report files found",
                    "requires_confirmation": False
                },
                {
                    "step_id": 2,
                    "description": "Create archive folder",
                    "tool": "CREATE_FOLDER",
                    "parameters": {"folder_path": "/home/jai/Downloads/Brain/archive"},
                    "expected_result": "Archive folder created",
                    "requires_confirmation": False
                }
            ],
            "completion_criteria": ["Archive folder created and files located"],
            "missing_information": [],
            "status": "ready"
        })

        with patch.object(self.engine.gateway, "generate", return_value=ModelResponse(
            text=mock_plan_json,
            model="qwen3.5:2b-q4_K_M",
            provider="ollama",
            duration_ms=450.0,
            success=True
        )) as mock_gen:
            plan = self.engine.plan_autonomous_goal("organize and archive all project text files")
            self.assertIsNotNone(plan)
            self.assertEqual(len(plan.steps), 2)
            self.assertEqual(plan.steps[0].tool_name, "FIND_FILES")
            self.assertEqual(plan.steps[1].tool_name, "CREATE_FOLDER")
            mock_gen.assert_called_once()

    # 3. Multi-step planning with dependencies
    def test_03_multi_step_dependencies_and_schema(self):
        mock_plan_dict = {
            "goal": "Inspect system performance and capture screen",
            "intent": "SYSTEM_DIAGNOSTIC",
            "steps": [
                {"step_id": 1, "description": "Check memory", "tool": "MEMORY_STATUS", "parameters": {}},
                {"step_id": 2, "description": "Check CPU", "tool": "CPU_STATUS", "parameters": {}},
                {"step_id": 3, "description": "Capture diagnostic screenshot", "tool": "SCREENSHOT", "parameters": {}}
            ],
            "completion_criteria": ["Memory, CPU, and screen collected"],
            "status": "ready"
        }
        is_valid, err, plan = self.engine.validate_structured_plan(mock_plan_dict)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[1].depends_on, [1])
        self.assertEqual(plan.steps[2].depends_on, [2])

    # 4. Invalid model output handling (malformed JSON)
    def test_04_malformed_json_rejected(self):
        is_valid, err, plan = self.engine.validate_structured_plan("I think we should do step 1 then step 2.")
        self.assertFalse(is_valid)
        self.assertIn("Malformed JSON", err)
        self.assertIsNone(plan)

    # 5. Hallucinated / unknown tool name rejected
    def test_05_unknown_tool_rejected(self):
        bad_plan = {
            "goal": "Hack into mainframe",
            "intent": "EXPLOIT",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Exploit system",
                    "tool": "NON_EXISTENT_MAGIC_TOOL",
                    "parameters": {}
                }
            ]
        }
        is_valid, err, plan = self.engine.validate_structured_plan(bad_plan)
        self.assertFalse(is_valid)
        self.assertIn("Hallucinated tool name", err)
        self.assertIsNone(plan)

    # 6. Missing parameters / structure validation
    def test_06_missing_parameters_must_be_dict(self):
        bad_plan = {
            "goal": "List files",
            "steps": [
                {"step_id": 1, "tool": "LIST_FILES", "parameters": "not a dict"}
            ]
        }
        is_valid, err, plan = self.engine.validate_structured_plan(bad_plan)
        self.assertFalse(is_valid)
        self.assertIn("parameters must be a dictionary", err)

    # 7. Model timeout / gateway failure returns None gracefully
    def test_07_gateway_failure_returns_none(self):
        with patch.object(self.engine.gateway, "generate", return_value=ModelResponse(
            text="",
            success=False,
            error="Connection timed out after 25s",
            provider="ollama"
        )):
            plan = self.engine.plan_autonomous_goal("unfamiliar complex novel workflow")
            self.assertIsNone(plan)

    # 8. Failed tool execution and adaptive evaluation (CONTINUE, RETRY, REPLAN, STOP)
    def test_08_evaluate_step_result_success_and_failure(self):
        step = ExecutionStep(step_id=1, tool_name="MEMORY_STATUS")

        # Success case
        res_ok = {"success": True, "data": {"used_mb": 2048}}
        eval_ok = self.engine.evaluate_step_result(step, res_ok)
        self.assertEqual(eval_ok["decision"], "CONTINUE")

        # Transient failure case
        res_fail = {"success": False, "error": "Temporary X11 query failure"}
        eval_fail = self.engine.evaluate_step_result(step, res_fail)
        self.assertIn(eval_fail["decision"], ["RETRY", "REPLAN"])

    # 9. Alternative method suggestion on DOM/click failure
    def test_09_recovery_alternative_method_switching(self):
        step = ExecutionStep(step_id=1, tool_name="CLICK_FIRST_RESULT")
        res_fail = {"success": False, "error": "Playwright element locator not found"}
        goal_state = GoalState(objective="Search web and click")

        # First failure suggests alternative method
        eval_res = self.engine.evaluate_step_result(step, res_fail, goal_state)
        self.assertIn(eval_res["decision"], ["RETRY", "REPLAN"])

    # 10. Missing information sets plan status to BLOCKED / need_info
    def test_10_missing_information_blocks_execution(self):
        plan_need_info = {
            "goal": "Send email to client",
            "intent": "COMMUNICATION",
            "steps": [
                {"step_id": 1, "tool": None, "description": "Ask user for recipient address"}
            ],
            "missing_information": ["Client email address", "Email subject"],
            "status": "need_info"
        }
        is_valid, err, plan = self.engine.validate_structured_plan(plan_need_info)
        self.assertTrue(is_valid)
        self.assertEqual(plan.status, "BLOCKED")
        self.assertTrue(any("MissingInfo" in ev for ev in plan.goal_state.evidence))

    # 11. Regression check: Existing process_reasoning_query handles epistemic guard
    def test_11_epistemic_safety_guard_preserved(self):
        ans = self.engine.process_reasoning_query("What happened on Mars today?")
        self.assertIn("could not verify", ans.lower())


if __name__ == "__main__":
    unittest.main()
