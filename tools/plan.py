import json
import time
from tools.registry import default_registry


class ExecutionStep:
    """
    Represents a single executable step within an ExecutionPlan.
    """
    def __init__(self, action_type="tool", tool_name="", arguments=None, answer=None, description=""):
        self.action_type = str(action_type).lower()  # "tool", "final", "capability"
        self.tool_name = str(tool_name).upper() if tool_name else ""
        self.arguments = arguments if isinstance(arguments, dict) else {}
        self.answer = str(answer) if answer is not None else None
        self.description = str(description)
        self.status = "PENDING"  # PENDING, EXECUTING, COMPLETED, FAILED, SKIPPED
        self.result = None
        self.error = None
        self.timestamp = None

    def to_dict(self):
        d = {
            "action_type": self.action_type,
            "status": self.status
        }
        if self.tool_name:
            d["tool"] = self.tool_name
        if self.arguments:
            d["arguments"] = self.arguments
        if self.answer is not None:
            d["answer"] = self.answer
        if self.description:
            d["description"] = self.description
        if self.result is not None:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return None
        atype = data.get("type") or data.get("action_type") or "tool"
        tool = data.get("tool") or data.get("action") or ""
        args = data.get("arguments") or data.get("args") or {}
        ans = data.get("answer")
        desc = data.get("description", "")
        return cls(action_type=atype, tool_name=tool, arguments=args, answer=ans, description=desc)


class ExecutionPlan:
    """
    Persistent Multi-Step Execution Plan for Brain Phase 9.3.
    Stores and sequences multi-step tasks without requiring Qwen re-entry per step.
    """
    def __init__(self, goal=""):
        self.goal = str(goal)
        self.steps = []
        self.current_step_idx = 0
        self.recovery_count = 0
        self.max_recovery_attempts = 2
        self.status = "PLANNING"  # PLANNING, RUNNING, COMPLETED, FAILED
        self.created_at = time.time()

    def add_step(self, step):
        if isinstance(step, ExecutionStep):
            self.steps.append(step)
        elif isinstance(step, dict):
            st = ExecutionStep.from_dict(step)
            if st:
                self.steps.append(st)

    def get_current_step(self):
        if 0 <= self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return None

    def advance(self):
        if self.current_step_idx < len(self.steps):
            self.current_step_idx += 1
        if self.current_step_idx >= len(self.steps):
            self.status = "COMPLETED"

    def is_complete(self):
        return self.status == "COMPLETED" or (self.current_step_idx >= len(self.steps) and len(self.steps) > 0)

    def is_failed(self):
        return self.status == "FAILED"

    def record_result(self, step_idx, result, success=True):
        if 0 <= step_idx < len(self.steps):
            step = self.steps[step_idx]
            step.result = result
            step.timestamp = time.time()
            if success:
                step.status = "COMPLETED"
                step.error = None
            else:
                step.status = "FAILED"
                step.error = result.get("error") if isinstance(result, dict) else str(result)

    def validate(self, registry=None):
        """
        Validates all steps in the plan against tool registry and basic arguments.
        Returns (is_valid, error_msg).
        """
        if registry is None:
            registry = default_registry

        valid_tools = {t["name"] for t in registry.list_tools()}
        # Include composite capabilities
        valid_tools.add("BROWSER_SEARCH_FOREGROUND")

        for idx, step in enumerate(self.steps, 1):
            if step.action_type == "tool":
                if not step.tool_name:
                    return False, f"Plan Step {idx} missing tool name."
                if step.tool_name not in valid_tools:
                    return False, f"Plan Step {idx} references invalid/unregistered tool '{step.tool_name}'."
        return True, None

    def to_dict(self):
        return {
            "goal": self.goal,
            "status": self.status,
            "current_step_idx": self.current_step_idx,
            "total_steps": len(self.steps),
            "recovery_count": self.recovery_count,
            "steps": [s.to_dict() for s in self.steps]
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return None
        goal = data.get("goal", "")
        plan = cls(goal=goal)
        raw_steps = data.get("steps", [])
        for s in raw_steps:
            step_obj = ExecutionStep.from_dict(s)
            if step_obj:
                plan.add_step(step_obj)
        return plan
