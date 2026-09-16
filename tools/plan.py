import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from tools.registry import default_registry


@dataclass
class GoalState:
    """
    Explicit Autonomous Goal State for Brain Agent (Phase 17).
    Tracks live lifecycle status, execution progress, collected evidence, and confidence.
    Statuses: PENDING, RUNNING, WAITING, VERIFYING, RECOVERING, COMPLETED, FAILED, BLOCKED.
    """
    objective: str
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    remaining_steps: List[str] = field(default_factory=list)
    status: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "remaining_steps": self.remaining_steps,
            "status": self.status
        }


class ExecutionStep:
    """
    Represents a single executable step within an ExecutionPlan (Phase 18).
    Supports explicit step identification, dependency graphs, expected outcomes,
    and verification methods.
    """
    def __init__(self, action_type="tool", tool_name="", arguments=None, answer=None, description="",
                 step_id=0, depends_on=None, expected_outcome=None, verification_method="none", allow_failure=False):
        self.step_id = int(step_id)
        self.action_type = str(action_type).lower()  # "tool", "final", "capability"
        self.tool_name = str(tool_name).upper() if tool_name else ""
        self.arguments = arguments if isinstance(arguments, dict) else {}
        self.answer = str(answer) if answer is not None else None
        self.description = str(description)
        self.depends_on = list(depends_on) if depends_on else []
        self.expected_outcome = str(expected_outcome) if expected_outcome else None
        self.verification_method = str(verification_method).lower() if verification_method else "none"
        self.allow_failure = bool(allow_failure)
        self.status = "PENDING"  # PENDING, EXECUTING, COMPLETED, FAILED, SKIPPED
        self.result = None
        self.error = None
        self.timestamp = None

    def to_dict(self):
        d = {
            "step_id": self.step_id,
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
        if self.depends_on:
            d["depends_on"] = self.depends_on
        if self.expected_outcome:
            d["expected_outcome"] = self.expected_outcome
        if self.verification_method != "none":
            d["verification_method"] = self.verification_method
        if self.allow_failure:
            d["allow_failure"] = self.allow_failure
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
        sid = data.get("step_id", 0)
        deps = data.get("depends_on", [])
        exp = data.get("expected_outcome")
        ver = data.get("verification_method", "none")
        allow_fail = data.get("allow_failure", False)
        return cls(
            action_type=atype,
            tool_name=tool,
            arguments=args,
            answer=ans,
            description=desc,
            step_id=sid,
            depends_on=deps,
            expected_outcome=exp,
            verification_method=ver,
            allow_failure=allow_fail
        )


class ExecutionPlan:
    """
    Persistent Multi-Step Execution Plan for Brain.
    Stores and sequences multi-step tasks with explicit GoalState tracking.
    """
    def __init__(self, goal=""):
        self.goal = str(goal)
        self.steps = []
        self.current_step_idx = 0
        self.recovery_count = 0
        self.max_recovery_attempts = 2
        self.status = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, BLOCKED
        self.created_at = time.time()
        self.goal_state = GoalState(objective=self.goal, status="PENDING")

    def add_step(self, step):
        if isinstance(step, ExecutionStep):
            self.steps.append(step)
        elif isinstance(step, dict):
            st = ExecutionStep.from_dict(step)
            if st:
                self.steps.append(st)
        self._sync_goal_state()

    def _sync_goal_state(self):
        remaining = [s.tool_name or s.action_type for s in self.steps if s.status not in ("COMPLETED", "FAILED", "SKIPPED")]
        self.goal_state.current_step = self.current_step_idx
        self.goal_state.remaining_steps = remaining
        if not remaining and self.steps:
            self.goal_state.status = "COMPLETED" if not self.goal_state.failed_steps else "FAILED"

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
            step_name = step.tool_name or step.action_type
            if success:
                step.status = "COMPLETED"
                step.error = None
                if step_name not in self.goal_state.completed_steps:
                    self.goal_state.completed_steps.append(step_name)
            else:
                step.status = "FAILED"
                step.error = result.get("error") if isinstance(result, dict) else str(result)
                if step_name not in self.goal_state.failed_steps:
                    self.goal_state.failed_steps.append(step_name)
            self._sync_goal_state()

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
