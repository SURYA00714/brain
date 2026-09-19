import os
import unittest
from tools.plan import ExecutionPlan, ExecutionStep
from core.workflow_engine import DeterministicWorkflowEngine, default_workflow_engine
from tools.router import FastRouter
from tools.registry import default_registry

class TestCrossToolWorkflows(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"
        self.engine = DeterministicWorkflowEngine(registry=default_registry)

    def test_workflow_engine_successful_execution(self):
        plan = ExecutionPlan(goal="Open calculator and maximize it")
        plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "calculator"}))
        plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="MAXIMIZE_WINDOW", arguments={"target": "calculator"}))
        plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="final", answer="Calculator opened and maximized."))

        res = self.engine.execute_plan(plan, timeout=10.0)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["completed_steps"], 3)

    def test_workflow_engine_timeout_handling(self):
        plan = ExecutionPlan(goal="Slow workflow")
        plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="BROWSER_WAIT", arguments={"seconds": 0.1}))
        
        # Immediate timeout check
        res = self.engine.execute_plan(plan, timeout=-1.0)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "TIMED_OUT")

    def test_workflow_engine_safe_failure(self):
        plan = ExecutionPlan(goal="Failing workflow")
        plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "non_existent_fake_app_xyz"}))
        
        res = self.engine.execute_plan(plan, timeout=10.0)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "FAILED")

    def test_fast_router_multi_step_workflow_plans(self):
        router = FastRouter()
        queries = [
            "open calculator and maximize it",
            "open Brave and go to example.com",
            "open Brave and search for Python 3.12"
        ]
        for q in queries:
            route_res = router.route(q)
            self.assertIsNotNone(route_res, f"Failed to route multi-step request: {q}")
            self.assertEqual(route_res.get("type"), "plan")
            plan = route_res.get("plan")
            self.assertIsInstance(plan, ExecutionPlan)
            self.assertGreater(len(plan.steps), 1)

            # Test deterministic execution of routed plan
            exec_res = self.engine.execute_plan(plan, timeout=10.0)
            self.assertTrue(exec_res["success"], f"Failed to execute plan for '{q}': {exec_res.get('error')}")

if __name__ == "__main__":
    unittest.main()
