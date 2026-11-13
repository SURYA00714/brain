import unittest
import tempfile
import shutil
from pathlib import Path
from tools.plan import ExecutionPlan, ExecutionStep
from core.executor import TaskCheckpointManager

class TestTaskCheckpoint(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = TaskCheckpointManager(checkpoint_dir=Path(self.test_dir))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_resume_checkpoint(self):
        plan = ExecutionPlan(goal="Test multi-step task")
        s1 = ExecutionStep(action_type="tool", tool_name="TIME", arguments={}, step_id=1)
        s2 = ExecutionStep(action_type="tool", tool_name="CPU_STATUS", arguments={}, step_id=2)
        plan.add_step(s1)
        plan.add_step(s2)

        # Mark step 1 as complete
        plan.record_result(0, {"success": True, "data": "12:00 PM"}, success=True)
        task_id = "task_test_123"

        self.mgr.save_checkpoint(task_id, plan)
        self.assertTrue(self.mgr.has_checkpoint(task_id))

        resumed_plan = self.mgr.load_checkpoint(task_id)
        self.assertIsNotNone(resumed_plan)
        self.assertEqual(resumed_plan.steps[0].status, "SUCCESS")
        self.assertEqual(resumed_plan.steps[1].status, "PENDING")

        self.mgr.clear_checkpoint(task_id)
        self.assertFalse(self.mgr.has_checkpoint(task_id))

if __name__ == "__main__":
    unittest.main()
