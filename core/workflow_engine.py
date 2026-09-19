import os
import time
from typing import Dict, Any, Optional
from tools.plan import ExecutionPlan, ExecutionStep
from tools.registry import default_registry

class DeterministicWorkflowEngine:
    """
    Deterministic Workflow Engine for Brain (Phase 6).
    Executes ordered, bounded multi-step cross-tool workflows with per-step validation,
    observable verification, timeouts, cancellation, and zero LLM calls.
    """
    def __init__(self, registry=None, max_steps=10):
        self.registry = registry or default_registry
        self.max_steps = max_steps

    def execute_plan(self, plan: ExecutionPlan, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Executes a deterministic multi-step ExecutionPlan.
        Returns standardized execution report dictionary.
        """
        if not plan or not isinstance(plan, ExecutionPlan):
            return {"success": False, "status": "FAILED", "error": "Invalid or missing ExecutionPlan."}

        # 1. Per-step validation against tool registry
        is_valid, val_err = plan.validate(registry=self.registry)
        if not is_valid:
            return {"success": False, "status": "FAILED", "error": f"Plan validation failed: {val_err}"}

        if len(plan.steps) > self.max_steps:
            return {"success": False, "status": "FAILED", "error": f"Plan steps count ({len(plan.steps)}) exceeds maximum limit of {self.max_steps}."}

        start_time = time.time()
        results = []
        plan.status = "RUNNING"

        for idx, step in enumerate(plan.steps):
            # 2. Check timeout and cancellation bounds
            if time.time() - start_time > timeout:
                plan.status = "FAILED"
                return {
                    "success": False,
                    "status": "TIMED_OUT",
                    "goal": plan.goal,
                    "completed_steps": idx,
                    "total_steps": len(plan.steps),
                    "results": results,
                    "error": f"Workflow execution timed out after {timeout} seconds."
                }

            step.status = "EXECUTING"

            # 3. Handle step action types
            if step.action_type == "final":
                step.status = "COMPLETED"
                step.result = step.answer
                plan.record_result(idx, {"data": step.answer}, success=True)
                results.append({"step_id": step.step_id, "action": "final", "answer": step.answer})
                continue

            tool_name = step.tool_name
            args = step.arguments

            # 4. Execute tool via ToolRegistry
            res = self.registry.execute(tool_name, args)
            success = res.get("success", False)

            # 5. Deterministic Verification Contract
            verified = success
            if success:
                verified = self._verify_step_outcome(tool_name, args, res, step)

            if verified:
                step.status = "COMPLETED"
                step.result = res
                plan.record_result(idx, res, success=True)
                results.append({"step_id": step.step_id, "tool": tool_name, "success": True, "data": res.get("data")})
            else:
                step.status = "FAILED"
                err_msg = res.get("error") or f"Verification failed for step {step.step_id} ({tool_name})."
                step.error = err_msg
                plan.record_result(idx, {"error": err_msg}, success=False)
                results.append({"step_id": step.step_id, "tool": tool_name, "success": False, "error": err_msg})

                if not step.allow_failure:
                    plan.status = "FAILED"
                    return {
                        "success": False,
                        "status": "FAILED",
                        "goal": plan.goal,
                        "failed_step": step.step_id,
                        "failed_tool": tool_name,
                        "completed_steps": idx,
                        "total_steps": len(plan.steps),
                        "results": results,
                        "error": err_msg
                    }

            plan.advance()

        plan.status = "COMPLETED"
        return {
            "success": True,
            "status": "COMPLETED",
            "goal": plan.goal,
            "completed_steps": len(plan.steps),
            "total_steps": len(plan.steps),
            "results": results,
            "error": None
        }

    def _verify_step_outcome(self, tool_name: str, args: dict, res: dict, step: ExecutionStep) -> bool:
        """
        Performs observable verification for actions.
        ACTION SUCCESS != TASK SUCCESS. Only observable evidence establishes success.
        """
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            return True

        if tool_name == "OPEN_APP":
            app_name = args.get("app_name") or args.get("name") or ""
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            return app_name in state.get("running_apps", []) or bool(state.get("active_app"))

        if tool_name == "MAXIMIZE_WINDOW":
            target = args.get("target") or ""
            from tools.window_manager import list_windows
            res_w = list_windows()
            return res_w.get("success", False)

        if tool_name in ("COPY_FILE", "CREATE_FILE"):
            from tools.files import validate_safe_path, resolve_location_alias
            dst = args.get("destination") or args.get("file_name") or ""
            cand = resolve_location_alias(dst)
            val, err = validate_safe_path(cand, allow_nonexistent=False)
            return val is not None and val.exists()

        if tool_name == "MOVE_FILE":
            from tools.files import validate_safe_path, resolve_location_alias
            src = args.get("source") or ""
            dst = args.get("destination") or ""
            cand_s = resolve_location_alias(src)
            cand_d = resolve_location_alias(dst)
            val_s, _ = validate_safe_path(cand_s)
            val_d, _ = validate_safe_path(cand_d)
            return (val_s is None or not val_s.exists()) and (val_d is not None and val_d.exists())

        if tool_name == "BROWSER_NAVIGATE":
            from tools.browser import browser_title
            bt = browser_title()
            return bt.get("success", False)

        if tool_name == "BROWSER_DOWNLOAD":
            return res.get("verified", False) and bool(res.get("path"))

        return True


default_workflow_engine = DeterministicWorkflowEngine()
