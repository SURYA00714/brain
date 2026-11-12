"""
Comprehensive Test Suite for Phase 1.5: Controlled Autonomous Execution.
Tests single-step & multi-step execution, parameter validation, safety/permission controls,
evidence-based verification, retry limits, task continuity, and duplicate action prevention.
"""

import os
import json
import unittest
from unittest.mock import patch, MagicMock

from tools.plan import ExecutionPlan, ExecutionStep
from tools.registry import ToolRegistry, Tool, default_registry
from tools.profiler import PerformanceProfiler
from brain import execute_plan
from core.cognition import (
    verify_step_execution,
    validate_step_permissions,
    validate_step_parameters,
    default_cognition
)


class TestControlledAutonomousExecution(unittest.TestCase):

    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"
        self.profiler = PerformanceProfiler()

        # Build clean test registry
        self.registry = ToolRegistry()
        self.registry.register(Tool(
            name="MEMORY_STATUS",
            description="Get memory metrics",
            parameters={},
            risk_level="LOW",
            func=lambda: {"success": True, "data": {"percent": 45.2, "used_mb": 3500}}
        ))
        self.registry.register(Tool(
            name="CPU_STATUS",
            description="Get CPU metrics",
            parameters={},
            risk_level="LOW",
            func=lambda: {"success": True, "data": {"usage_percent": 12.5}}
        ))
        self.registry.register(Tool(
            name="DELETE_FILE",
            description="Delete file from disk",
            parameters={"path": "string", "confirmed": "boolean"},
            risk_level="HIGH",
            func=lambda path, confirmed=False: {"success": True, "data": f"Deleted {path}"}
        ))
        self.registry.register(Tool(
            name="CREATE_FILE",
            description="Create file",
            parameters={"path": "string"},
            risk_level="MEDIUM",
            func=lambda path, content="": {"success": True, "data": f"Created {path}"}
        ))

    # 1. Single-step execution
    def test_01_single_step_execution(self):
        plan = ExecutionPlan(goal="Check memory")
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="MEMORY_STATUS",
            arguments={},
            expected_outcome="Memory metrics retrieved"
        )
        plan.add_step(step)

        ans = execute_plan(plan, self.registry, self.profiler, "Check memory", quiet=True)
        self.assertEqual(step.status, "SUCCESS")
        self.assertEqual(step.verification_status, "VERIFIED")
        self.assertGreaterEqual(step.duration_ms, 0.0)
        self.assertIsNotNone(step.evidence["result"])
        self.assertEqual(plan.status, "SUCCESS")

    # 2. Multi-step execution with dependencies
    def test_02_multistep_execution(self):
        plan = ExecutionPlan(goal="Inspect memory and CPU")
        s1 = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="MEMORY_STATUS",
            arguments={},
            expected_outcome="Memory checked"
        )
        s2 = ExecutionStep(
            step_id=2,
            action_type="tool",
            tool_name="CPU_STATUS",
            arguments={},
            depends_on=[1],
            expected_outcome="CPU checked"
        )
        plan.add_step(s1)
        plan.add_step(s2)

        ans = execute_plan(plan, self.registry, self.profiler, "Inspect memory and CPU", quiet=True)
        self.assertEqual(s1.status, "SUCCESS")
        self.assertEqual(s2.status, "SUCCESS")
        self.assertEqual(plan.status, "SUCCESS")
        self.assertEqual(len(plan.history), 2)

    # 3. Correct tool selection and dispatch
    def test_03_correct_tool_dispatch(self):
        plan = ExecutionPlan(goal="CPU check")
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="CPU_STATUS",
            arguments={}
        )
        plan.add_step(step)

        execute_plan(plan, self.registry, self.profiler, "CPU check", quiet=True)
        self.assertEqual(step.evidence["actual_tool"], "CPU_STATUS")
        self.assertIn("usage_percent", step.evidence["result"]["data"])

    # 4. Invalid/unregistered tool rejection
    def test_04_invalid_tool_rejection(self):
        plan = ExecutionPlan(goal="Run nonexistent action")
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="NONEXISTENT_MAGIC_TOOL",
            arguments={}
        )
        plan.add_step(step)

        ans = execute_plan(plan, self.registry, self.profiler, "Run nonexistent", quiet=True)
        self.assertIn("Brain Error", ans)
        self.assertEqual(step.status, "FAILED")
        self.assertEqual(step.verification_status, "FAILED")
        self.assertEqual(plan.status, "FAILED")

    # 5. Parameter validation gate
    def test_05_parameter_validation(self):
        # CREATE_FILE requires 'path'
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="CREATE_FILE",
            arguments={}  # Missing path
        )
        is_valid, err = validate_step_parameters(step, self.registry)
        self.assertFalse(is_valid)
        self.assertIn("requires 'path'", err)

        plan = ExecutionPlan(goal="Create nameless file")
        plan.add_step(step)
        ans = execute_plan(plan, self.registry, self.profiler, "Create nameless file", quiet=True)
        self.assertIn("Brain Error", ans)
        self.assertEqual(step.status, "FAILED")

    # 6. Failed tool recovery (transient failure followed by retry)
    def test_06_failed_tool_recovery(self):
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "error": "Transient connection blip", "data": None}
            return {"success": True, "data": {"percent": 40.0}}

        flaky_registry = ToolRegistry()
        flaky_registry.register(Tool("FLAKY_MEM", "Flaky tool", {}, "LOW", flaky_func))

        plan = ExecutionPlan(goal="Test flaky tool")
        step = ExecutionStep(step_id=1, action_type="tool", tool_name="FLAKY_MEM", arguments={})
        plan.add_step(step)

        ans = execute_plan(plan, flaky_registry, self.profiler, "Test flaky tool", quiet=True)
        self.assertEqual(call_count, 2)
        self.assertEqual(step.status, "SUCCESS")
        self.assertEqual(step.retry_count, 1)
        self.assertEqual(plan.status, "SUCCESS")

    # 7. Retry limits (max 2 retries enforced)
    def test_07_retry_limits(self):
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            return {"success": False, "error": "Permanent crash", "data": None}

        failing_registry = ToolRegistry()
        failing_registry.register(Tool("FAILING_TOOL", "Fails", {}, "LOW", always_fail))

        plan = ExecutionPlan(goal="Test failure limits")
        step = ExecutionStep(step_id=1, action_type="tool", tool_name="FAILING_TOOL", arguments={})
        plan.add_step(step)

        ans = execute_plan(plan, failing_registry, self.profiler, "Test failure limits", quiet=True)
        self.assertIn("Brain Error", ans)
        self.assertEqual(step.status, "FAILED")
        # Step should be attempted initial + 2 retries = 3 attempts total
        self.assertEqual(call_count, 3)
        self.assertEqual(step.retry_count, 2)
        self.assertEqual(plan.status, "FAILED")

    # 8. User confirmation for destructive actions
    def test_08_user_confirmation_destructive_action(self):
        plan = ExecutionPlan(goal="Delete system files")
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="DELETE_FILE",
            arguments={"path": "/tmp/test.txt"}
        )
        plan.add_step(step)

        # Unconfirmed execution should be BLOCKED
        ans = execute_plan(plan, self.registry, self.profiler, "Delete system files", quiet=True, user_confirmed=False)
        self.assertIn("Brain Notice", ans)
        self.assertEqual(step.status, "BLOCKED")
        self.assertEqual(plan.status, "BLOCKED")

        # When confirmed, execution proceeds
        with patch("os.path.exists", return_value=False):
            ans_confirmed = execute_plan(plan, self.registry, self.profiler, "Delete system files", quiet=True, user_confirmed=True)
            self.assertEqual(step.status, "SUCCESS")
            self.assertEqual(plan.status, "SUCCESS")

    # 9. Interrupted task continuation
    def test_09_interrupted_task_continuation(self):
        plan = ExecutionPlan(goal="Multi-step workflow")
        s1 = ExecutionStep(step_id=1, action_type="tool", tool_name="MEMORY_STATUS", arguments={})
        s2 = ExecutionStep(step_id=2, action_type="tool", tool_name="CPU_STATUS", arguments={}, depends_on=[1])
        plan.add_step(s1)
        plan.add_step(s2)

        # Simulate interruption after Step 1 completed
        s1.record_execution({"success": True, "data": {"percent": 50}}, success=True, duration_ms=5.0, verification_status="VERIFIED")
        self.assertEqual(s1.status, "SUCCESS")
        self.assertEqual(s2.status, "PENDING")

        # Call resume
        next_step = plan.resume()
        self.assertEqual(next_step.step_id, 2)
        self.assertEqual(plan.current_step_idx, 1)

        # Execute resumed plan
        ans = execute_plan(plan, self.registry, self.profiler, "Multi-step workflow", quiet=True)
        self.assertEqual(s1.status, "SUCCESS")
        self.assertEqual(s2.status, "SUCCESS")
        self.assertEqual(plan.status, "SUCCESS")

    # 10. Duplicate action prevention on continuation
    def test_10_duplicate_action_prevention(self):
        step1_calls = 0
        step2_calls = 0

        def run_step1():
            nonlocal step1_calls
            step1_calls += 1
            return {"success": True, "data": "Step 1 done"}

        def run_step2():
            nonlocal step2_calls
            step2_calls += 1
            return {"success": True, "data": "Step 2 done"}

        reg = ToolRegistry()
        reg.register(Tool("STEP_1", "", {}, "LOW", run_step1))
        reg.register(Tool("STEP_2", "", {}, "LOW", run_step2))

        plan = ExecutionPlan(goal="Prevent duplication")
        s1 = ExecutionStep(step_id=1, action_type="tool", tool_name="STEP_1", arguments={})
        s2 = ExecutionStep(step_id=2, action_type="tool", tool_name="STEP_2", arguments={})
        plan.add_step(s1)
        plan.add_step(s2)

        # Execute step 1 first
        s1.record_execution({"success": True, "data": "done"}, success=True, duration_ms=2.0, verification_status="VERIFIED")

        # Execute plan — step 1 must be skipped because it is already SUCCESS
        execute_plan(plan, reg, self.profiler, "Prevent duplication", quiet=True)
        self.assertEqual(step1_calls, 0)
        self.assertEqual(step2_calls, 1)

    # 11. Evidence-based success verification
    def test_11_evidence_based_success_verification(self):
        # Empty data payload cannot claim success
        verified, status, reason = verify_step_execution("MEMORY_STATUS", {}, {"success": True, "data": None})
        self.assertFalse(verified)
        self.assertEqual(status, "FAILED")
        self.assertIn("null observation", reason)

        # Valid metrics verify successfully
        verified_ok, status_ok, _ = verify_step_execution("MEMORY_STATUS", {}, {"success": True, "data": {"percent": 45.0}})
        self.assertTrue(verified_ok)
        self.assertEqual(status_ok, "VERIFIED")

        # Non-existent created file cannot claim success
        with patch("os.path.exists", return_value=False):
            ver_file, status_file, reason_file = verify_step_execution("CREATE_FILE", {"path": "/tmp/ghost.txt"}, {"success": True, "data": "Created"})
            self.assertFalse(ver_file)
            self.assertEqual(status_file, "FAILED")
            self.assertIn("does not exist", reason_file)

    # 12. Destructive actions never automatically retried
    def test_12_destructive_action_never_retried(self):
        step = ExecutionStep(
            step_id=1,
            action_type="tool",
            tool_name="DELETE_FILE",
            arguments={"path": "/tmp/critical.txt"}
        )
        failed_res = {"success": False, "error": "Permission denied"}
        decision_info = default_cognition.evaluate_step_result(step, failed_res)
        self.assertEqual(decision_info["decision"], "STOP")
        self.assertIn("prohibited from automatic retry", decision_info["message"])


if __name__ == "__main__":
    unittest.main()
