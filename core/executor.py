"""
Brain Plan Executor.
Executes multi-step ExecutionPlan sequentially with controlled autonomy,
multi-signal evidence verification, bounded recovery, and task continuity.
"""

import time
from typing import Dict, Any, Optional

from brain_constants import UI_MODIFYING_TOOLS
from tools.vision import default_vision
from tools.screen import analyze_captured_screen
from tools.input import validate_gui_action_safety
from tools.plan import ExecutionPlan, ExecutionStep
from core.memory import default_memory
from core.world_state import default_world_state
from core.cognition import (
    default_cognition,
    verify_step_execution,
    validate_step_permissions,
    validate_step_parameters,
)
from core.formatter import format_tool_response


class TaskState:
    """
    Lightweight Task Execution State tracker.
    Tracks execution status, verification, progress, and bounded recovery limits.
    """
    def __init__(self, user_request: str):
        self.user_request = user_request
        self.current_goal = user_request
        self.completed_steps = []
        self.pending_steps = []
        self.current_observation = None
        self.last_action = None
        self.last_result = None
        self.verification_status = "UNVERIFIED"  # UNVERIFIED, VERIFIED, FAILED
        self.recovery_attempts = 0
        self.step_count = 0
        self.task_status = "PLANNING"  # PLANNING, OBSERVING, ACTING, VERIFYING, RECOVERING, COMPLETED, FAILED

    def update_action(self, action: Dict[str, Any]):
        self.last_action = action
        self.step_count += 1
        self.task_status = "ACTING"

    def update_result(self, result: Dict[str, Any], verification_status: str = "UNVERIFIED"):
        self.last_result = result
        self.verification_status = verification_status
        if result and result.get("success"):
            self.completed_steps.append({
                "action": self.last_action,
                "result": result,
                "verification": verification_status
            })
            self.task_status = "VERIFYING"
        else:
            self.task_status = "RECOVERING"
            self.recovery_attempts += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_request": self.user_request,
            "current_goal": self.current_goal,
            "completed_steps_count": len(self.completed_steps),
            "step_count": self.step_count,
            "recovery_attempts": self.recovery_attempts,
            "task_status": self.task_status,
            "verification_status": self.verification_status
        }


class TaskCheckpointManager:
    """
    Vision Domain 2.3: Checkpoints execution plans across long-running tasks,
    enabling bounded recovery and resumption after interruptions.
    """
    def __init__(self, checkpoint_dir: Optional[Any] = None):
        import os
        from pathlib import Path
        self.dir = Path(checkpoint_dir) if checkpoint_dir else Path("data/checkpoints")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, task_id: str):
        return self.dir / f"{task_id}.json"

    def save_checkpoint(self, task_id: str, plan: ExecutionPlan) -> None:
        import json
        data = {
            "task_id": task_id,
            "plan": plan.to_dict(),
            "timestamp": time.time()
        }
        self._file_path(task_id).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def has_checkpoint(self, task_id: str) -> bool:
        return self._file_path(task_id).exists()

    def load_checkpoint(self, task_id: str) -> Optional[ExecutionPlan]:
        import json
        f = self._file_path(task_id)
        if not f.exists():
            return None
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            plan_data = raw.get("plan", {})
            plan = ExecutionPlan(goal=plan_data.get("goal", ""))
            plan.status = plan_data.get("status", "PENDING")
            plan.current_step_idx = plan_data.get("current_step_idx", 0)
            plan.recovery_count = plan_data.get("recovery_count", 0)

            for s_data in plan_data.get("steps", []):
                step = ExecutionStep.from_dict(s_data)
                if step:
                    if "status" in s_data:
                        step.set_status(s_data["status"])
                    if "verification_status" in s_data:
                        step.verification_status = s_data["verification_status"]
                    if "duration_ms" in s_data:
                        step.duration_ms = s_data["duration_ms"]
                    if "retry_count" in s_data:
                        step.retry_count = s_data["retry_count"]
                    plan.steps.append(step)

            return plan
        except Exception:
            return None

    def clear_checkpoint(self, task_id: str) -> None:
        f = self._file_path(task_id)
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass


default_task_checkpoint_manager = TaskCheckpointManager()


def execute_plan(
    plan: ExecutionPlan,
    registry: Any,
    profiler: Any,
    user_request: str,
    mode: str = "AUTO",
    quiet: bool = False,
    debug: bool = False,
    user_confirmed: bool = False
) -> str:
    """
    Executes a multi-step ExecutionPlan sequentially with controlled autonomy,
    multi-signal evidence verification, bounded recovery, and task continuity.
    Does NOT invoke the LLM for every step.
    Returns final response string.
    """
    task_state = TaskState(user_request)
    last_tool_res = None
    step_idx = 0

    while not plan.is_complete() and step_idx < len(plan.steps):
        step = plan.steps[step_idx]
        step_idx += 1
        plan.current_step_idx = step_idx - 1

        # Task continuity: Skip steps already marked SUCCESS or SKIPPED
        if step.is_successful or step.status == "SKIPPED":
            continue

        action_type = step.action_type
        tool_name = step.tool_name
        args = step.arguments

        if action_type == "final":
            step.set_status("SUCCESS")
            plan.status = "SUCCESS"
            ans = step.answer or "Task completed successfully."
            current_obs = default_vision.get_current_observation()
            if current_obs and current_obs.get("elements") and "screen" in user_request.lower():
                elems = current_obs.get("elements", [])
                scr = current_obs.get("screen", {})
                elem_summary = f" Found {len(elems)} visible element(s) on screen ({scr.get('width', 1920)}x{scr.get('height', 1080)})."
                if not ans.endswith("."):
                    ans += "."
                ans += elem_summary
            return ans

        if action_type in ("tool", "capability"):
            # 1. Dependency Prerequisite Validation
            if step.depends_on:
                missing_deps = []
                for dep_id in step.depends_on:
                    dep_step = next((s for s in plan.steps if s.step_id == dep_id), None)
                    if not dep_step or not dep_step.is_successful:
                        missing_deps.append(dep_id)
                if missing_deps:
                    if step.allow_failure:
                        step.set_status("SKIPPED")
                        continue
                    else:
                        step.set_status("BLOCKED")
                        plan.status = "FAILED"
                        err_msg = f"Step {step.step_id} blocked: Prerequisite step(s) {missing_deps} have not succeeded."
                        step.error = err_msg
                        return f"Brain Error: {err_msg}"

            # 2. Tool Registry Existence Gate
            if not registry.has_tool(tool_name):
                err_msg = f"Tool '{tool_name}' is not registered."
                step.record_execution({"success": False, "error": err_msg}, success=False, verification_status="FAILED")
                plan.status = "FAILED"
                return f"Brain Error: {err_msg}"

            # 3. Parameter Validation Gate
            is_valid_param, param_err = validate_step_parameters(step, registry)
            if not is_valid_param:
                step.record_execution({"success": False, "error": param_err}, success=False, verification_status="FAILED")
                plan.status = "FAILED"
                return f"Brain Error: {param_err}"

            # 4. Terminal & Action-Chain Safety Gate
            is_safe, safety_err = validate_gui_action_safety(tool_name, args)
            if not is_safe:
                step.record_execution({"success": False, "error": safety_err}, success=False, verification_status="FAILED")
                plan.status = "FAILED"
                return f"Brain Error: {safety_err}"

            # 5. Permission & Confirmation Gate
            is_allowed, perm_reason = validate_step_permissions(step, user_confirmed=user_confirmed)
            if not is_allowed:
                step.set_status("BLOCKED")
                step.error = perm_reason
                plan.status = "BLOCKED"
                return f"Brain Notice: {perm_reason}"

            if user_confirmed:
                args["confirmed"] = True

            # Set step state to RUNNING
            step.set_status("RUNNING")

            if not quiet:
                print(f"Brain: [Step {step_idx}/{len(plan.steps)}] Executing {tool_name} with args {args}...")

            # 6. Tool Execution with Duration Tracking
            t0 = time.time()
            result = registry.execute(tool_name, args)
            t1 = time.time()
            dur_ms = (t1 - t0) * 1000.0
            profiler.record_tool(tool_name, t1 - t0, is_gui=(tool_name in UI_MODIFYING_TOOLS))

            # 7. Evidence-Based Verification
            is_verified, ver_status, ver_reason = verify_step_execution(tool_name, args, result)
            if not is_verified:
                result["success"] = False
                result["error"] = ver_reason

            default_world_state.record_action_outcome(tool_name, args, result, verified=is_verified)
            plan.record_result(step_idx - 1, result, success=is_verified, duration_ms=dur_ms, verification_status=ver_status)
            task_state.update_result(result, verification_status=ver_status)

            if is_verified:
                last_tool_res = result
                if tool_name in UI_MODIFYING_TOOLS:
                    analyze_captured_screen(force_refresh=True)
            else:
                # 8. Adaptive Cognitive Recovery & Retry Loop
                eval_decision = default_cognition.evaluate_step_result(step, result, plan.goal_state)
                decision = eval_decision.get("decision", "STOP")

                if decision == "RETRY":
                    step.retry_count += 1
                    if step.retry_count <= 2:
                        if not quiet:
                            print(f"Brain: Notice - Step '{tool_name}' failed verification ({result.get('error')}). Retrying attempt {step.retry_count}/2...")
                        step_idx -= 1
                        continue

                if decision == "REPLAN":
                    rec_tool = eval_decision.get("recommended_tool")
                    if rec_tool and registry.has_tool(rec_tool) and plan.recovery_count < plan.max_recovery_attempts:
                        plan.recovery_count += 1
                        if not quiet:
                            print(f"Brain: Re-planning step {step.step_id} with alternate tool '{rec_tool}'...")
                        step.tool_name = rec_tool
                        step_idx -= 1
                        continue

                # Unrecoverable failure: halt safely
                plan.status = "FAILED"
                default_world_state.set_active_task(None)
                default_memory.record_event("PLAN", f"Goal: {user_request}", status="FAILED")
                return f"Brain Error: Action '{tool_name}' failed verification ({result.get('error')}). Plan halted."

    plan.status = "SUCCESS"
    default_world_state.set_active_task(None)
    default_memory.record_event("PLAN", f"Goal: {user_request}", status="COMPLETED")

    # Derive response from last tool result if no explicit final step was provided
    if last_tool_res:
        tool_name = plan.steps[-1].tool_name if plan.steps else ""
        last_args = plan.steps[-1].arguments if plan.steps else {}
        return format_tool_response(tool_name, last_tool_res, last_args)

    return "Task completed successfully."
