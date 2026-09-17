"""
Brain Task Decomposition & Multi-Step Task State (Stage 8I/8J).
Decomposes complex user goals into structured, step-level action plans
and tracks multi-step task lifecycle, step progress, retries, and generation invalidation.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


TASK_STEP_STATUSES = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED", "CANCELLED"}


@dataclass
class TaskStep:
    """Individual step within a multi-step task plan."""
    step_id: int
    action_type: str                  # tool, thought, final
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: str = "PENDING"           # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, CANCELLED
    result: Optional[Dict[str, Any]] = None
    verification: str = "PENDING"     # PENDING, VERIFIED, FAILED
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiStepTask:
    """Multi-step task execution model integrating step progress and generation tokens."""
    task_id: str
    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    current_step_index: int = 0
    max_retries_per_step: int = 2
    generation_id: int = 1
    status: str = "ACTIVE"            # ACTIVE, COMPLETED, FAILED, PAUSED, CANCELLED
    created_at: float = field(default_factory=time.time)

    def current_step(self) -> Optional[TaskStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_step(self) -> Optional[TaskStep]:
        if self.current_step_index < len(self.steps):
            self.steps[self.current_step_index].status = "COMPLETED"
            self.current_step_index += 1
        if self.current_step_index >= len(self.steps):
            self.status = "COMPLETED"
            return None
        return self.current_step()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "status": self.status,
            "generation_id": self.generation_id,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at
        }


class TaskPlanner:
    """Decomposes user requests into bounded step plans."""

    def decompose_task(self, user_request: str, generation_id: int = 1) -> MultiStepTask:
        req_lower = user_request.lower().strip()
        now = time.time()
        tid = f"task_{int(now*1000)}_{uuid.uuid4().hex[:6]}"

        steps = []

        # Rule-based decomposition heuristics
        if "open brave and search" in req_lower:
            query = req_lower.split("search for", 1)[-1].split("search", 1)[-1].strip()
            steps = [
                TaskStep(1, "tool", "OPEN_APP", {"app_name": "brave"}, "Open Brave Browser"),
                TaskStep(2, "tool", "FOCUS_APP", {"app_name": "brave"}, "Focus Brave Window"),
                TaskStep(3, "tool", "BROWSER_SEARCH_FOREGROUND", {"query": query or "python"}, f"Search for {query}"),
                TaskStep(4, "tool", "CLICK_FIRST_RESULT", {}, "Open top search result"),
                TaskStep(5, "tool", "ANALYZE_SCREEN", {}, "Observe results screen")
            ]
        elif "open brave" in req_lower:
            steps = [
                TaskStep(1, "tool", "OPEN_APP", {"app_name": "brave"}, "Open Brave Browser"),
                TaskStep(2, "tool", "FOCUS_APP", {"app_name": "brave"}, "Focus Brave Window")
            ]
        elif "search for" in req_lower or "search" in req_lower:
            query = req_lower.split("search for", 1)[-1].split("search", 1)[-1].strip()
            steps = [
                TaskStep(1, "tool", "WEB_SEARCH", {"query": query}, f"Perform search query '{query}'")
            ]
        else:
            steps = [
                TaskStep(1, "tool", "ANALYZE_SCREEN", {}, "Observe desktop state")
            ]

        return MultiStepTask(
            task_id=tid,
            goal=user_request,
            steps=steps,
            generation_id=generation_id,
            status="ACTIVE"
        )


default_task_planner = TaskPlanner()
