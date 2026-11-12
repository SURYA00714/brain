"""
Reliable Autonomous Execution Manager & SQLite Task Persistence (Phase 1.7).
Covers:
- Explicit task/step states: PENDING, RUNNING, SUCCESS, FAILED, BLOCKED, RETRYING, SKIPPED, CANCELLED
- 3-level permission enforcement (LEVEL_1_SAFE, LEVEL_2_CONTROLLED, LEVEL_3_CONFIRMATION_REQUIRED)
- Tool execution + multi-signal verification lifecycle
- Bounded failure recovery (CONTINUE, RETRY, REPLAN, ASK_USER, STOP) + learning pipeline logging
- SQLite task persistence, interrupted task resumption, cancellation, and duplicate-action prevention
"""

import json
import os
import sqlite3
import time
import uuid
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.cognition import (
    CognitiveEngine,
    default_cognition,
    validate_step_parameters,
    validate_step_permissions,
    verify_step_execution,
)
from core.learning import ControlledLearningPipeline
from tools.plan import ExecutionPlan, ExecutionStep
from tools.registry import default_registry


DEFAULT_TASK_DB = Path(__file__).resolve().parent.parent / "data" / "brain_tasks.db"


class PermissionLevel(IntEnum):
    LEVEL_1_SAFE = 1
    LEVEL_2_CONTROLLED = 2
    LEVEL_3_CONFIRMATION_REQUIRED = 3


LEVEL_1_SAFE_TOOLS = {
    "MEMORY_STATUS", "CPU_STATUS", "CHECK_DISK_SPACE", "GET_SYSTEM_INFO",
    "GET_CURRENT_TIME", "TIME", "WEB_SEARCH", "LIST_FILES", "FIND_FILES",
    "READ_TEXT_FILE", "LIST_APPS", "SCREENSHOT", "ANALYZE_SCREEN", "RECALL",
}

LEVEL_2_CONTROLLED_TOOLS = {
    "CREATE_FILE", "CREATE_FOLDER", "OPEN_APP", "FOCUS_APP", "CLOSE_APP",
    "BROWSER_SEARCH", "BROWSER_NAVIGATE", "BROWSER_SEARCH_FOREGROUND",
    "NEW_TAB", "CLICK_FIRST_RESULT", "REMEMBER",
}

LEVEL_3_CONFIRMATION_TOOLS = {
    "DELETE_FILE", "SHUTDOWN", "RESTART", "LOGOUT", "RUN_COMMAND", "EXECUTE_SHELL",
}


def get_tool_permission_level(tool_name: str) -> PermissionLevel:
    t = str(tool_name).upper().strip()
    if t in LEVEL_3_CONFIRMATION_TOOLS:
        return PermissionLevel.LEVEL_3_CONFIRMATION_REQUIRED
    if t in LEVEL_2_CONTROLLED_TOOLS:
        return PermissionLevel.LEVEL_2_CONTROLLED
    if t in LEVEL_1_SAFE_TOOLS:
        return PermissionLevel.LEVEL_1_SAFE
    # Unknown/unlisted tools default to controlled or confirmation-required
    return PermissionLevel.LEVEL_2_CONTROLLED


def validate_safe_path(path_str: str) -> Tuple[bool, str]:
    """Blocks traversal or destructive OS root modifications."""
    if not path_str or not isinstance(path_str, str):
        return False, "Path must be a non-empty string."
    norm = os.path.normpath(path_str.strip())
    forbidden_roots = ("/", "/etc", "/usr", "/bin", "/sbin", "/boot", "/dev", "/proc", "/sys", "/root")
    if norm in forbidden_roots:
        return False, f"Permission Denied: Path '{norm}' is a protected system directory."
    return True, "Path valid"


class ExecutionTaskStore:
    """SQLite persistence for ExecutionPlan tasks, supporting resumption and duplicate prevention."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = DEFAULT_TASK_DB
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_request TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step_idx INTEGER NOT NULL DEFAULT 0,
                    plan_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON execution_tasks (status, updated_at DESC)
            """)

    def save_task(self, task_id: str, user_request: str, plan: ExecutionPlan) -> None:
        now = time.time()
        payload = json.dumps(plan.to_dict())
        with self._conn:
            self._conn.execute("""
                INSERT INTO execution_tasks (task_id, user_request, status, current_step_idx, plan_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    current_step_idx = excluded.current_step_idx,
                    plan_json = excluded.plan_json,
                    updated_at = excluded.updated_at
            """, (task_id, user_request, plan.status, plan.current_step_idx, payload, now, now))

    def load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM execution_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not row:
            return None
        plan_data = json.loads(row["plan_json"])
        plan = ExecutionPlan.from_dict(plan_data)
        return {
            "task_id": row["task_id"],
            "user_request": row["user_request"],
            "status": row["status"],
            "current_step_idx": row["current_step_idx"],
            "plan": plan,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_unfinished_tasks(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute("""
            SELECT task_id, user_request, status, current_step_idx, updated_at
            FROM execution_tasks
            WHERE status IN ('PENDING', 'RUNNING', 'BLOCKED', 'RETRYING')
            ORDER BY updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def find_active_duplicate(self, user_request: str) -> Optional[str]:
        """Returns task_id if an identical task is currently RUNNING or RETRYING."""
        row = self._conn.execute("""
            SELECT task_id FROM execution_tasks
            WHERE LOWER(TRIM(user_request)) = LOWER(TRIM(?))
              AND status IN ('RUNNING', 'RETRYING')
            ORDER BY updated_at DESC LIMIT 1
        """, (user_request,)).fetchone()
        return row["task_id"] if row else None

    def cancel_task(self, task_id: str) -> bool:
        loaded = self.load_task(task_id)
        if not loaded or not loaded["plan"]:
            return False
        plan: ExecutionPlan = loaded["plan"]
        plan.status = "CANCELLED"
        for st in plan.steps:
            if st.status in ("PENDING", "RUNNING", "RETRYING", "BLOCKED"):
                st.set_status("CANCELLED")
        self.save_task(task_id, loaded["user_request"], plan)
        return True

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


class AutonomousExecutionManager:
    """
    Executes validated ExecutionPlans with:
    - Unique task IDs & SQLite state persistence after each step
    - 3-level permission checks & safe path validation
    - Multi-signal verification (step only becomes SUCCESS when verified)
    - Bounded recovery (max 2 retries, no destructive retries, preserves completed steps)
    - Duplicate action prevention on resumption
    """

    def __init__(
        self,
        registry=None,
        cognition: Optional[CognitiveEngine] = None,
        task_store: Optional[ExecutionTaskStore] = None,
        learning_pipeline: Optional[ControlledLearningPipeline] = None,
    ):
        self.registry = registry or default_registry
        self.cognition = cognition or default_cognition
        self.task_store = task_store or ExecutionTaskStore()
        self.learning = learning_pipeline

    def check_permission(self, step: ExecutionStep, user_confirmed: bool = False) -> Tuple[bool, str, PermissionLevel]:
        level = get_tool_permission_level(step.tool_name)
        if level == PermissionLevel.LEVEL_3_CONFIRMATION_REQUIRED:
            if not user_confirmed and not step.arguments.get("confirmed", False):
                step.requires_confirmation = True
                return False, f"Level 3 confirmation required for '{step.tool_name}'.", level

        # Path validation for file operations
        for k in ("path", "file_path", "folder_path"):
            if k in step.arguments and step.arguments[k]:
                ok_path, path_err = validate_safe_path(str(step.arguments[k]))
                if not ok_path:
                    return False, path_err, level

        ok_perm, perm_reason = validate_step_permissions(step, user_confirmed=user_confirmed)
        return ok_perm, perm_reason, level

    def execute_task(
        self,
        user_request: str,
        plan: ExecutionPlan,
        task_id: Optional[str] = None,
        user_confirmed: bool = False,
        max_retries_per_step: int = 2,
    ) -> Dict[str, Any]:
        """
        Runs or resumes `plan` under full verification, permission, and persistence controls.
        """
        # Duplicate task prevention
        if task_id is None:
            dup_id = self.task_store.find_active_duplicate(user_request)
            if dup_id:
                return {
                    "task_id": dup_id,
                    "status": "BLOCKED",
                    "message": f"Duplicate task already active (task_id={dup_id}).",
                    "plan": plan.to_dict(),
                }
            task_id = f"task_{uuid.uuid4().hex[:12]}"

        plan.status = "RUNNING"
        self.task_store.save_task(task_id, user_request, plan)

        for idx, step in enumerate(plan.steps):
            plan.current_step_idx = idx

            # Duplicate action prevention / task continuity
            if step.is_successful or step.status in ("SKIPPED", "CANCELLED"):
                continue

            if step.action_type == "final":
                step.set_status("SUCCESS")
                plan.status = "SUCCESS"
                self.task_store.save_task(task_id, user_request, plan)
                return {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "message": step.answer or "Task completed and verified.",
                    "plan": plan.to_dict(),
                }

            # 1. Dependency check
            if step.depends_on:
                unmet = [
                    d for d in step.depends_on
                    if not any(s.step_id == d and s.is_successful for s in plan.steps)
                ]
                if unmet:
                    step.set_status("BLOCKED")
                    step.error = f"Unmet dependencies: {unmet}"
                    plan.status = "FAILED"
                    self.task_store.save_task(task_id, user_request, plan)
                    return {
                        "task_id": task_id,
                        "status": "FAILED",
                        "message": step.error,
                        "plan": plan.to_dict(),
                    }

            # 2. Tool & parameter check
            if not self.registry.has_tool(step.tool_name):
                err = f"Tool '{step.tool_name}' is not registered."
                step.record_execution({"success": False, "error": err}, success=False, verification_status="FAILED")
                plan.status = "FAILED"
                self.task_store.save_task(task_id, user_request, plan)
                return {"task_id": task_id, "status": "FAILED", "message": err, "plan": plan.to_dict()}

            param_ok, param_err = validate_step_parameters(step, self.registry)
            if not param_ok:
                step.record_execution({"success": False, "error": param_err}, success=False, verification_status="FAILED")
                plan.status = "FAILED"
                self.task_store.save_task(task_id, user_request, plan)
                return {"task_id": task_id, "status": "FAILED", "message": param_err, "plan": plan.to_dict()}

            # 3. Permission check
            perm_ok, perm_reason, perm_level = self.check_permission(step, user_confirmed=user_confirmed)
            if not perm_ok:
                step.set_status("BLOCKED")
                step.error = perm_reason
                plan.status = "BLOCKED"
                self.task_store.save_task(task_id, user_request, plan)
                return {
                    "task_id": task_id,
                    "status": "BLOCKED",
                    "decision": "ASK_USER",
                    "permission_level": perm_level.name,
                    "message": perm_reason,
                    "plan": plan.to_dict(),
                }

            # 4. Execute + Verify + Bounded Retry loop
            while True:
                step.set_status("RUNNING")
                t0 = time.perf_counter()
                result = self.registry.execute(step.tool_name, step.arguments)
                dur_ms = (time.perf_counter() - t0) * 1000.0

                verified, ver_status, ver_msg = verify_step_execution(step.tool_name, step.arguments, result)
                step_ok = bool(result.get("success", False)) and verified

                if step_ok:
                    step.record_execution(
                        result=result,
                        success=True,
                        duration_ms=dur_ms,
                        verification_status=ver_status,
                    )
                    self.task_store.save_task(task_id, user_request, plan)
                    break

                # Execution or verification failed
                err_msg = result.get("error") or ver_msg
                step.record_execution(
                    result=result,
                    success=False,
                    duration_ms=dur_ms,
                    verification_status="FAILED",
                    error=err_msg,
                )

                if self.learning is not None:
                    self.learning.record_failure(
                        "TOOL_FAILURE",
                        user_request,
                        json.dumps(result),
                        error_reason=str(err_msg),
                    )

                recovery = self.cognition.evaluate_step_result(step, {"success": False, "error": err_msg}, plan.goal_state)
                decision = recovery.get("decision", "STOP")

                if decision == "RETRY" and step.retry_count < max_retries_per_step:
                    step.retry_count += 1
                    step.set_status("RETRYING")
                    self.task_store.save_task(task_id, user_request, plan)
                    continue

                if decision == "REPLAN" and recovery.get("recommended_tool"):
                    alt_tool = recovery["recommended_tool"]
                    if self.registry.has_tool(alt_tool) and step.retry_count < max_retries_per_step:
                        step.retry_count += 1
                        step.tool_name = alt_tool
                        step.set_status("RETRYING")
                        self.task_store.save_task(task_id, user_request, plan)
                        continue

                # Unrecoverable or destructive failure -> STOP
                plan.status = "FAILED"
                self.task_store.save_task(task_id, user_request, plan)
                return {
                    "task_id": task_id,
                    "status": "FAILED",
                    "decision": decision,
                    "message": recovery.get("message") or err_msg,
                    "plan": plan.to_dict(),
                }

        plan.status = "SUCCESS"
        self.task_store.save_task(task_id, user_request, plan)
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "message": f"Completed {len(plan.steps)} verified step(s).",
            "plan": plan.to_dict(),
        }

    def resume_task(self, task_id: str, user_confirmed: bool = False) -> Dict[str, Any]:
        """Resumes an interrupted task from SQLite without re-executing completed steps."""
        loaded = self.task_store.load_task(task_id)
        if not loaded or not loaded["plan"]:
            return {"task_id": task_id, "status": "FAILED", "message": f"Task '{task_id}' not found."}
        if loaded["status"] in ("SUCCESS", "CANCELLED"):
            return {"task_id": task_id, "status": loaded["status"], "message": f"Task already {loaded['status']}."}
        return self.execute_task(
            user_request=loaded["user_request"],
            plan=loaded["plan"],
            task_id=task_id,
            user_confirmed=user_confirmed,
        )
