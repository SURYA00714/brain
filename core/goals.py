"""
Brain Persistent Goal Management & Task Continuity (Phase 19 Companion Evolution).
Stores persistent long-running goals with sequenced subtasks, live evidence logs,
and session resumption capabilities saved in data/goals.json.
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class SubTask:
    """A granular subtask within a persistent goal."""
    id: int
    title: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, BLOCKED
    result: Optional[str] = None
    blocking_reason: Optional[str] = None
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubTask":
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            status=data.get("status", "PENDING"),
            result=data.get("result"),
            blocking_reason=data.get("blocking_reason"),
            evidence=data.get("evidence", [])
        )


@dataclass
class PersistentGoal:
    """Full lifecycle tracking for a long-running user objective."""
    id: str
    objective: str
    status: str = "PENDING"  # PENDING, RUNNING, PAUSED, COMPLETED, FAILED, BLOCKED
    subtasks: List[SubTask] = field(default_factory=list)
    current_subtask_idx: int = 0
    evidence: List[str] = field(default_factory=list)
    last_action: Optional[str] = None
    next_action: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["subtasks"] = [s.to_dict() if isinstance(s, SubTask) else s for s in self.subtasks]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistentGoal":
        raw_subtasks = data.get("subtasks", [])
        subtasks = [SubTask.from_dict(s) if isinstance(s, dict) else s for s in raw_subtasks]
        return cls(
            id=data.get("id", str(int(time.time()))),
            objective=data.get("objective", ""),
            status=data.get("status", "PENDING"),
            subtasks=subtasks,
            current_subtask_idx=data.get("current_subtask_idx", 0),
            evidence=data.get("evidence", []),
            last_action=data.get("last_action"),
            next_action=data.get("next_action"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )

    def add_subtask(self, title: str) -> SubTask:
        new_id = len(self.subtasks) + 1
        st = SubTask(id=new_id, title=title)
        self.subtasks.append(st)
        self.updated_at = time.time()
        return st

    def update_subtask(self, subtask_id: int, status: str, result: Optional[str] = None):
        for s in self.subtasks:
            if s.id == subtask_id:
                s.status = status
                if result:
                    s.result = result
                self.updated_at = time.time()
                break

    def progress_summary(self) -> str:
        """Returns concise human-readable progress string."""
        total = len(self.subtasks)
        completed = sum(1 for s in self.subtasks if s.status == "COMPLETED")
        status_line = f"Goal: '{self.objective}' [{self.status}] ({completed}/{total} subtasks done)"
        subtask_lines = []
        for s in self.subtasks:
            mark = "✓" if s.status == "COMPLETED" else ("✗" if s.status == "FAILED" else "○")
            subtask_lines.append(f"  {mark} {s.title}")
        return status_line + "\n" + "\n".join(subtask_lines)


class PersistentGoalManager:
    """Manages persistent goals across sessions and system reboots."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "goals.json")
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.goals: Dict[str, PersistentGoal] = {}
        self.active_goal_id: Optional[str] = None
        self.load()

    def create_goal(self, objective: str, subtask_titles: Optional[List[str]] = None) -> PersistentGoal:
        goal_id = f"goal_{int(time.time())}"
        subtasks = []
        if subtask_titles:
            for idx, title in enumerate(subtask_titles, start=1):
                subtasks.append(SubTask(id=idx, title=title))
        else:
            subtasks.append(SubTask(id=1, title=objective))

        goal = PersistentGoal(
            id=goal_id,
            objective=objective,
            status="RUNNING",
            subtasks=subtasks,
            next_action=subtasks[0].title if subtasks else None
        )
        self.goals[goal_id] = goal
        self.active_goal_id = goal_id
        self.save()
        return goal

    def get_active_goal(self) -> Optional[PersistentGoal]:
        if self.active_goal_id and self.active_goal_id in self.goals:
            return self.goals[self.active_goal_id]
        # Fallback to most recently updated non-completed goal
        active = [g for g in self.goals.values() if g.status in ("RUNNING", "PENDING", "PAUSED")]
        if active:
            active.sort(key=lambda x: x.updated_at, reverse=True)
            self.active_goal_id = active[0].id
            return active[0]
        return None

    def update_subtask(self, goal_id: str, subtask_id: int, status: str, result: Optional[str] = None):
        goal = self.goals.get(goal_id)
        if not goal:
            return
        for s in goal.subtasks:
            if s.id == subtask_id:
                s.status = status
                if result:
                    s.result = result
                break

        # Check if all completed
        if all(s.status == "COMPLETED" for s in goal.subtasks):
            goal.status = "COMPLETED"
            goal.next_action = None
        else:
            # Advance next_action
            pending = [s for s in goal.subtasks if s.status == "PENDING"]
            goal.next_action = pending[0].title if pending else None

        goal.updated_at = time.time()
        self.save()

    def record_evidence(self, goal_id: str, evidence_item: str):
        goal = self.goals.get(goal_id)
        if goal:
            goal.evidence.append(evidence_item)
            goal.updated_at = time.time()
            self.save()

    def save(self):
        try:
            data = {
                "active_goal_id": self.active_goal_id,
                "goals": {k: v.to_dict() for k, v in self.goals.items()}
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self):
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                self.active_goal_id = data.get("active_goal_id")
                raw_goals = data.get("goals", {})
                self.goals = {k: PersistentGoal.from_dict(v) for k, v in raw_goals.items()}
        except Exception:
            pass


default_goals = PersistentGoalManager()
