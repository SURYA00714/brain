import unittest
from unittest.mock import MagicMock
from core.accuracy import AccuracyEngine
from core.cognition import CognitiveEngine
from core.execution_manager import (
    AutonomousExecutionManager,
    ExecutionTaskStore,
    PermissionLevel,
    get_tool_permission_level,
    validate_safe_path,
)
from core.learning import ControlledLearningPipeline
from models.gateway import ModelResponse
from tools.plan import ExecutionPlan, ExecutionStep
from tools.registry import Tool, ToolRegistry


class TestPhase17Execution(unittest.TestCase):
    def test_stage1_truncated_json_detection_and_retry(self):
        self.assertTrue(CognitiveEngine.detect_truncated_json('{"goal":"x","steps":[', {"truncated": True})[0])
        self.assertTrue(CognitiveEngine.detect_truncated_json('{"goal":"x","steps":[{"step_id":1')[0])
        self.assertFalse(CognitiveEngine.detect_truncated_json('{"goal":"x","steps":[]}')[0])

        eng = CognitiveEngine()
        eng.gateway = MagicMock()
        eng.gateway.providers = {"groq": MagicMock(is_available=lambda: False), "gemini": MagicMock(is_available=lambda: False)}
        eng.gateway.generate.side_effect = [
            ModelResponse(text='{"goal":"test","steps":[{"step_id":1', success=True, metadata={"truncated": True}),
            ModelResponse(
                text='{"goal":"test","intent":"CHECK","steps":[{"step_id":1,"description":"Check mem","tool":"MEMORY_STATUS","parameters":{},"depends_on":[],"expected_result":"RAM ok"}],"completion_criteria":["RAM checked"],"status":"ready"}',
                success=True,
                metadata={"truncated": False},
            ),
        ]
        plan = eng.generate_structured_plan("Check memory", tier="LOCAL")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.steps[0].tool_name, "MEMORY_STATUS")
        self.assertEqual(eng.gateway.generate.call_count, 2)

    def test_stage2_ku01_portal_snippets_rejected(self):
        mars_portals = [
            "Mars: News & Features - NASA Science: Get the latest news releases, features, findings, and stories about the missions on Mars.",
            "Mars News -- ScienceDaily: Planet Mars News. Read astronomy articles on how Mars could have once supported life.",
            "Mars News: Latest & Breaking Mars Headlines: 7NEWS brings you the latest Mars news."
        ]
        res = AccuracyEngine.evaluate_evidence_relevance("What happened on Mars today?", mars_portals)
        self.assertEqual(res["relevant_findings"], [])
        self.assertEqual(res["evidence_coverage"], 0.0)
        self.assertTrue(res["portal_only"])

    def test_stage3_4_real_local_tool_execution_and_verification(self):
        store = ExecutionTaskStore(db_path=":memory:")
        mgr = AutonomousExecutionManager(task_store=store)
        plan = ExecutionPlan(goal="Check system health")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="MEMORY_STATUS", step_id=1))
        plan.add_step(ExecutionStep(action_type="tool", tool_name="CHECK_DISK_SPACE", step_id=2, depends_on=[1]))

        out = mgr.execute_task("Check memory and disk", plan)
        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(plan.steps[0].status, "SUCCESS")
        self.assertEqual(plan.steps[0].verification_status, "VERIFIED")
        self.assertEqual(plan.steps[1].status, "SUCCESS")
        self.assertEqual(plan.steps[1].verification_status, "VERIFIED")
        store.close()

    def test_stage5_bounded_recovery_and_learning_log(self):
        reg = ToolRegistry()
        calls = {"count": 0}

        def flaky_search(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] < 2:
                return {"success": False, "error": "transient timeout"}
            return {"success": True, "data": ["Linux kernel 6.12 released"]}

        reg.register(Tool("WEB_SEARCH", "search", {"query": "str"}, "LOW", flaky_search))
        store = ExecutionTaskStore(db_path=":memory:")
        learning = ControlledLearningPipeline(db_path=":memory:")
        mgr = AutonomousExecutionManager(registry=reg, task_store=store, learning_pipeline=learning)

        plan = ExecutionPlan(goal="Search")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="WEB_SEARCH", arguments={"query": "linux"}, step_id=1))
        out = mgr.execute_task("Search linux", plan)
        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(plan.steps[0].retry_count, 1)
        self.assertEqual(calls["count"], 2)
        store.close()
        learning.close()

    def test_stage6_permissions_and_safe_path(self):
        self.assertEqual(get_tool_permission_level("MEMORY_STATUS"), PermissionLevel.LEVEL_1_SAFE)
        self.assertEqual(get_tool_permission_level("CREATE_FILE"), PermissionLevel.LEVEL_2_CONTROLLED)
        self.assertEqual(get_tool_permission_level("DELETE_FILE"), PermissionLevel.LEVEL_3_CONFIRMATION_REQUIRED)

        self.assertFalse(validate_safe_path("/etc")[0])
        self.assertFalse(validate_safe_path("/")[0])
        self.assertTrue(validate_safe_path("/tmp/test.txt")[0])

        store = ExecutionTaskStore(db_path=":memory:")
        mgr = AutonomousExecutionManager(task_store=store)
        plan = ExecutionPlan(goal="Delete file")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="DELETE_FILE", arguments={"path": "/tmp/nonexistent_test.txt"}, step_id=1))
        out = mgr.execute_task("Delete file", plan, user_confirmed=False)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["decision"], "ASK_USER")
        self.assertEqual(out["permission_level"], "LEVEL_3_CONFIRMATION_REQUIRED")
        store.close()

    def test_stage7_persistence_resumption_duplicate_and_cancel(self):
        reg = ToolRegistry()
        exec_counts = {"s1": 0, "s2": 0}
        reg.register(Tool("MEMORY_STATUS", "mem", {}, "LOW", lambda **kw: (exec_counts.__setitem__("s1", exec_counts["s1"] + 1) or {"success": True, "data": {"used": 50}})))
        reg.register(Tool("CPU_STATUS", "cpu", {}, "LOW", lambda **kw: (exec_counts.__setitem__("s2", exec_counts["s2"] + 1) or {"success": True, "data": {"cpu": 10}})))

        store = ExecutionTaskStore(db_path=":memory:")
        mgr = AutonomousExecutionManager(registry=reg, task_store=store)

        # Simulate interrupted task where step 1 already succeeded and step 2 is pending
        plan = ExecutionPlan(goal="Health check")
        s1 = ExecutionStep(action_type="tool", tool_name="MEMORY_STATUS", step_id=1)
        s1.record_execution({"success": True, "data": {"used": 50}}, success=True, verification_status="VERIFIED")
        s2 = ExecutionStep(action_type="tool", tool_name="CPU_STATUS", step_id=2, depends_on=[1])
        plan.add_step(s1)
        plan.add_step(s2)
        plan.status = "RUNNING"
        store.save_task("task_interrupt_1", "Health check", plan)

        unfinished = store.list_unfinished_tasks()
        self.assertEqual(len(unfinished), 1)
        # Duplicate active check
        self.assertEqual(store.find_active_duplicate("Health check"), "task_interrupt_1")

        # Resume must NOT re-run step 1 (duplicate action prevention!)
        resumed = mgr.resume_task("task_interrupt_1")
        self.assertEqual(resumed["status"], "SUCCESS")
        self.assertEqual(exec_counts["s1"], 0)
        self.assertEqual(exec_counts["s2"], 1)

        # Cancellation test
        plan2 = ExecutionPlan(goal="Cancel me")
        plan2.add_step(ExecutionStep(action_type="tool", tool_name="CPU_STATUS", step_id=1))
        plan2.status = "PENDING"
        store.save_task("task_cancel_1", "Cancel me", plan2)
        self.assertTrue(store.cancel_task("task_cancel_1"))
        loaded = store.load_task("task_cancel_1")
        self.assertEqual(loaded["status"], "CANCELLED")
        self.assertEqual(loaded["plan"].steps[0].status, "CANCELLED")
        store.close()


if __name__ == "__main__":
    unittest.main()
