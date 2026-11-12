"""
Adaptive Intelligence & Experience Learning Engine for Brain (Phase 1.8).
SQLite-first, lightweight, zero vector-DB bloat, zero background inference.
Implements:
- Stage 1: Experience Learning (SUCCESS, PARTIAL_SUCCESS, FAILURE, USER_CORRECTED, UNVERIFIED)
- Stage 2: Adaptive Strategy Engine (classify -> retrieve experiences -> select strategy -> plan)
- Stage 4: Structured Procedural Memory (preconditions, permissions, steps, verification, invalidation)
- Stage 5: User Feedback Intelligence (temporary vs task vs long-term vs factual correction)
- Stage 6: Deterministic Self-Evaluation Engine
- Stage 8: Strategy Performance Tracking (with minimum sample-size guards)
"""

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.accuracy import AccuracyEngine
from core.learning import ControlledLearningPipeline
from core.memory import MemoryStore, default_memory


DEFAULT_ADAPTIVE_DB = Path(__file__).resolve().parent.parent / "data" / "brain_adaptive.db"

EXPERIENCE_OUTCOMES = {
    "SUCCESS",
    "PARTIAL_SUCCESS",
    "FAILURE",
    "USER_CORRECTED",
    "UNVERIFIED",
}


@dataclass
class ExperienceRecord:
    user_request: str
    task_category: str
    strategy_used: str
    plan_json: str
    tools_selected: List[str]
    tool_results: List[Dict[str, Any]]
    duration_ms: float
    verification_outcome: str  # VERIFIED | FAILED | UNVERIFIED
    errors: List[str] = field(default_factory=list)
    recovery_attempts: int = 0
    user_correction: Optional[str] = None
    outcome: str = "UNVERIFIED"
    model_calls: int = 0
    model_id: str = "default"
    id: Optional[int] = None
    created_at: float = 0.0
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProceduralRecord:
    name: str
    task_category: str
    preconditions: List[str]
    required_permissions: str
    steps: List[Dict[str, Any]]
    expected_outputs: str
    verification_conditions: str
    known_failure_conditions: List[str] = field(default_factory=list)
    model_id: str = "default"
    last_success_at: float = 0.0
    success_count: int = 1
    failure_count: int = 0
    confidence: float = 1.0
    is_valid: bool = True
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdaptiveIntelligenceEngine:
    """
    Unified adaptive intelligence layer reusing SQLite memory and learning pipelines.
    Never modifies executable code, model weights, system prompts, or safety policies.
    """
    AUTO_MODIFY_CODE = False
    AUTO_MODIFY_WEIGHTS = False

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory_store: Optional[MemoryStore] = None,
        learning_pipeline: Optional[ControlledLearningPipeline] = None,
    ):
        if db_path is None:
            self.db_path = DEFAULT_ADAPTIVE_DB
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.memory = memory_store or default_memory
        self.learning = learning_pipeline
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS task_experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_request TEXT NOT NULL,
                    task_category TEXT NOT NULL,
                    strategy_used TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    tools_selected TEXT NOT NULL,
                    tool_results_json TEXT NOT NULL,
                    duration_ms REAL NOT NULL DEFAULT 0.0,
                    verification_outcome TEXT NOT NULL,
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    recovery_attempts INTEGER NOT NULL DEFAULT 0,
                    user_correction TEXT,
                    outcome TEXT NOT NULL,
                    model_calls INTEGER NOT NULL DEFAULT 0,
                    model_id TEXT NOT NULL DEFAULT 'default',
                    created_at REAL NOT NULL
                )
            """)
            try:
                self._conn.execute("ALTER TABLE task_experiences ADD COLUMN model_id TEXT NOT NULL DEFAULT 'default'")
            except Exception:
                pass

            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exp_cat ON task_experiences (task_category, outcome, created_at DESC)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exp_model ON task_experiences (model_id, created_at DESC)
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    task_category TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    required_permissions TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    expected_outputs TEXT NOT NULL,
                    verification_conditions TEXT NOT NULL,
                    known_failure_conditions TEXT NOT NULL DEFAULT '[]',
                    model_id TEXT NOT NULL DEFAULT 'default',
                    last_success_at REAL NOT NULL DEFAULT 0.0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    is_valid INTEGER NOT NULL DEFAULT 1
                )
            """)
            try:
                self._conn.execute("ALTER TABLE procedures ADD COLUMN model_id TEXT NOT NULL DEFAULT 'default'")
            except Exception:
                pass

    @staticmethod
    def classify_task(user_request: str) -> str:
        lowered = (user_request or "").lower()
        if any(k in lowered for k in ("cpu", "ram", "memory", "disk", "system health")):
            return "SYSTEM_HEALTH"
        if any(k in lowered for k in ("file", "folder", "directory", "create ", "read ", "delete ")):
            return "FILE_OPS"
        if any(k in lowered for k in ("search", "web", "look up", "news", "latest")):
            return "WEB_RESEARCH"
        if any(k in lowered for k in ("open ", "close ", "focus ", "launch ")):
            return "APP_CONTROL"
        return "GENERAL"

    # ------------------------------------------------------------------
    # Stage 1: Experience Learning
    # ------------------------------------------------------------------
    def record_experience(
        self,
        user_request: str,
        strategy_used: str,
        plan_dict: Dict[str, Any],
        tools_selected: List[str],
        tool_results: List[Dict[str, Any]],
        duration_ms: float,
        verification_outcome: str,
        outcome: str,
        errors: Optional[List[str]] = None,
        recovery_attempts: int = 0,
        user_correction: Optional[str] = None,
        model_calls: int = 0,
        task_category: Optional[str] = None,
        model_id: str = "default",
    ) -> int:
        cat = task_category or self.classify_task(user_request)
        ver = str(verification_outcome).upper()
        out = str(outcome).upper()
        if out not in EXPERIENCE_OUTCOMES:
            out = "UNVERIFIED"
        # Never treat an unverified result as SUCCESS
        if out == "SUCCESS" and ver != "VERIFIED":
            out = "UNVERIFIED"

        now = time.time()
        with self._conn:
            cur = self._conn.execute("""
                INSERT INTO task_experiences (
                    user_request, task_category, strategy_used, plan_json,
                    tools_selected, tool_results_json, duration_ms,
                    verification_outcome, errors_json, recovery_attempts,
                    user_correction, outcome, model_calls, model_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_request,
                cat,
                strategy_used,
                json.dumps(plan_dict or {}),
                json.dumps(tools_selected or []),
                json.dumps(tool_results or []),
                float(duration_ms),
                ver,
                json.dumps(errors or []),
                int(recovery_attempts),
                user_correction,
                out,
                int(model_calls),
                str(model_id),
                now,
            ))
            return int(cur.lastrowid)

    def search_experiences(
        self,
        user_request: str,
        task_category: Optional[str] = None,
        limit: int = 3,
        min_relevance: float = 0.25,
        model_id: Optional[str] = None,
    ) -> List[ExperienceRecord]:
        q_kw = AccuracyEngine.extract_keywords(user_request)
        cat = task_category or self.classify_task(user_request)
        if model_id:
            rows = self._conn.execute("""
                SELECT * FROM task_experiences
                WHERE (task_category = ? OR ? = 'GENERAL') AND model_id = ?
                ORDER BY created_at DESC LIMIT 50
            """, (cat, cat, model_id)).fetchall()
        else:
            rows = self._conn.execute("""
                SELECT * FROM task_experiences
                WHERE task_category = ? OR ? = 'GENERAL'
                ORDER BY created_at DESC LIMIT 50
            """, (cat, cat)).fetchall()

        scored: List[ExperienceRecord] = []
        for r in rows:
            req_kw = AccuracyEngine.extract_keywords(r["user_request"])
            if q_kw and req_kw:
                overlap = len(set(q_kw) & set(req_kw)) / len(set(q_kw))
            else:
                overlap = 0.0
            if overlap < min_relevance:
                continue
            scored.append(ExperienceRecord(
                id=r["id"],
                user_request=r["user_request"],
                task_category=r["task_category"],
                strategy_used=r["strategy_used"],
                plan_json=r["plan_json"],
                tools_selected=json.loads(r["tools_selected"]),
                tool_results=json.loads(r["tool_results_json"]),
                duration_ms=r["duration_ms"],
                verification_outcome=r["verification_outcome"],
                errors=json.loads(r["errors_json"]),
                recovery_attempts=r["recovery_attempts"],
                user_correction=r["user_correction"],
                outcome=r["outcome"],
                model_calls=r["model_calls"],
                model_id=r["model_id"] if "model_id" in r.keys() else "default",
                created_at=r["created_at"],
                relevance_score=round(overlap, 3),
            ))

        scored.sort(key=lambda e: (e.relevance_score, e.created_at), reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Stage 4: Structured Procedural Memory
    # ------------------------------------------------------------------
    def store_procedure(self, proc: ProceduralRecord) -> None:
        total = max(1, proc.success_count + proc.failure_count)
        conf = round(proc.success_count / total, 3)
        with self._conn:
            self._conn.execute("""
                INSERT INTO procedures (
                    name, task_category, preconditions_json, required_permissions,
                    steps_json, expected_outputs, verification_conditions,
                    known_failure_conditions, model_id, last_success_at, success_count,
                    failure_count, confidence, is_valid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    steps_json = excluded.steps_json,
                    model_id = excluded.model_id,
                    last_success_at = excluded.last_success_at,
                    success_count = excluded.success_count,
                    failure_count = excluded.failure_count,
                    confidence = excluded.confidence,
                    is_valid = excluded.is_valid
            """, (
                proc.name,
                proc.task_category,
                json.dumps(proc.preconditions),
                proc.required_permissions,
                json.dumps(proc.steps),
                proc.expected_outputs,
                proc.verification_conditions,
                json.dumps(proc.known_failure_conditions),
                proc.model_id or "default",
                proc.last_success_at or time.time(),
                proc.success_count,
                proc.failure_count,
                conf,
                1 if proc.is_valid else 0,
            ))

    def find_matching_procedure(
        self,
        user_request: str,
        task_category: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Optional[ProceduralRecord]:
        cat = task_category or self.classify_task(user_request)
        q_kw = set(AccuracyEngine.extract_keywords(user_request))
        if model_id:
            rows = self._conn.execute("""
                SELECT * FROM procedures
                WHERE is_valid = 1 AND task_category = ? AND (model_id = ? OR model_id = 'default')
                ORDER BY confidence DESC, success_count DESC
            """, (cat, model_id)).fetchall()
        else:
            rows = self._conn.execute("""
                SELECT * FROM procedures
                WHERE is_valid = 1 AND task_category = ?
                ORDER BY confidence DESC, success_count DESC
            """, (cat,)).fetchall()
        for r in rows:
            proc_kw = set(AccuracyEngine.extract_keywords(r["name"] + " " + r["expected_outputs"]))
            if not q_kw or (q_kw & proc_kw):
                return ProceduralRecord(
                    id=r["id"],
                    name=r["name"],
                    task_category=r["task_category"],
                    preconditions=json.loads(r["preconditions_json"]),
                    required_permissions=r["required_permissions"],
                    steps=json.loads(r["steps_json"]),
                    expected_outputs=r["expected_outputs"],
                    verification_conditions=r["verification_conditions"],
                    known_failure_conditions=json.loads(r["known_failure_conditions"]),
                    last_success_at=r["last_success_at"],
                    success_count=r["success_count"],
                    failure_count=r["failure_count"],
                    confidence=r["confidence"],
                    is_valid=bool(r["is_valid"]),
                )
        return None

    def invalidate_procedure(self, name: str) -> bool:
        with self._conn:
            cur = self._conn.execute("UPDATE procedures SET is_valid = 0 WHERE name = ?", (name,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Stage 2: Adaptive Strategy Engine
    # ------------------------------------------------------------------
    def select_strategy(self, user_request: str) -> Dict[str, Any]:
        """
        Classifies task, retrieves relevant verified experiences & procedures,
        avoids repeatedly failing tools/strategies, and selects the best strategy.
        """
        cat = self.classify_task(user_request)
        relevant_exps = self.search_experiences(user_request, task_category=cat, limit=5)

        failed_strategies = {
            e.strategy_used for e in relevant_exps if e.outcome == "FAILURE"
        }
        avoid_tools = []
        for e in relevant_exps:
            if e.outcome == "FAILURE":
                for t in e.tools_selected:
                    if t not in avoid_tools:
                        avoid_tools.append(t)

        # Check verified procedural memory
        proc = self.find_matching_procedure(user_request, task_category=cat)
        if proc and proc.confidence >= 0.7:
            return {
                "task_category": cat,
                "strategy": "REUSE_PROCEDURE",
                "procedure": proc.to_dict(),
                "avoid_tools": avoid_tools,
                "relevant_experiences": len(relevant_exps),
                "reason": f"Matched verified procedure '{proc.name}' (confidence={proc.confidence}).",
            }

        # Check if a prior strategy failed repeatedly -> switch to alternative
        if failed_strategies:
            return {
                "task_category": cat,
                "strategy": "ALTERNATIVE_STRATEGY",
                "procedure": None,
                "avoid_tools": avoid_tools,
                "avoid_strategies": sorted(failed_strategies),
                "relevant_experiences": len(relevant_exps),
                "reason": f"Prior strategy {sorted(failed_strategies)} failed; selecting alternative approach.",
            }

        return {
            "task_category": cat,
            "strategy": "STANDARD_PLANNING",
            "procedure": None,
            "avoid_tools": [],
            "relevant_experiences": len(relevant_exps),
            "reason": "No conflicting failures; using standard validated planning.",
        }

    # ------------------------------------------------------------------
    # Stage 5: User Feedback Intelligence
    # ------------------------------------------------------------------
    def process_user_feedback(
        self,
        feedback_text: str,
        subject: str = "user",
        key: str = "",
        corrected_value: str = "",
    ) -> Dict[str, Any]:
        """
        Distinguishes temporary instructions, task-specific preferences,
        long-term user preferences, and verified factual corrections.
        """
        lowered = (feedback_text or "").lower().strip()

        # 1. Temporary instructions must NOT become permanent memory
        if any(k in lowered for k in ("for now", "just this time", "temporarily", "only today")):
            return {
                "classification": "TEMPORARY_INSTRUCTION",
                "persisted": False,
                "reason": "Temporary instruction kept in short-term session only.",
            }

        # 2. Failure avoidance ("do not repeat that")
        if any(k in lowered for k in ("do not repeat", "don't repeat", "never do that", "stop doing that")):
            if key:
                self.memory.record_failure_memory(key, corrected_value or "Avoid repeated action", tool_name=subject)
            return {
                "classification": "FAILURE_AVOIDANCE",
                "persisted": True,
                "reason": "Recorded failure avoidance rule.",
            }

        # 3. Factual correction ("that is incorrect")
        if any(k in lowered for k in ("that is incorrect", "that's wrong", "incorrect", "actually ")):
            if key and corrected_value:
                self.memory.correct_memory("FACT", subject, key, corrected_value, source="user_correction")
            return {
                "classification": "VERIFIED_FACTUAL_CORRECTION",
                "persisted": bool(key and corrected_value),
                "reason": "Updated verified factual memory.",
            }

        # 4. Long-term preference ("this is how I want it done", "always")
        if any(k in lowered for k in ("this is how i want", "always ", "i prefer ")):
            if key and corrected_value:
                self.memory.correct_memory("PREFERENCE", subject, key, corrected_value, source="user_preference")
            return {
                "classification": "LONG_TERM_PREFERENCE",
                "persisted": bool(key and corrected_value),
                "reason": "Stored long-term user preference.",
            }

        # 5. Task-specific preference ("use another method")
        if any(k in lowered for k in ("use another method", "different approach", "try another")):
            return {
                "classification": "TASK_PREFERENCE",
                "persisted": False,
                "reason": "Task-level strategy override noted.",
            }

        return {
            "classification": "CONVERSATIONAL",
            "persisted": False,
            "reason": "Conversational statement not persisted as permanent memory.",
        }

    def inspect_learning_records(self, limit: int = 20) -> Dict[str, Any]:
        exps = [dict(r) for r in self._conn.execute(
            "SELECT id, user_request, task_category, strategy_used, outcome, verification_outcome, duration_ms FROM task_experiences ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()]
        procs = [dict(r) for r in self._conn.execute(
            "SELECT id, name, task_category, confidence, success_count, failure_count, is_valid FROM procedures ORDER BY confidence DESC LIMIT ?",
            (limit,)
        ).fetchall()]
        return {"experiences": exps, "procedures": procs}

    # ------------------------------------------------------------------
    # Stage 6: Deterministic Self-Evaluation Engine
    # ------------------------------------------------------------------
    @staticmethod
    def evaluate_task_execution(
        user_request: str,
        strategy_decision: Dict[str, Any],
        plan_valid: bool,
        execution_result: Dict[str, Any],
        model_calls: int = 0,
    ) -> Dict[str, Any]:
        """Deterministically audits a completed task without letting the LLM grade itself."""
        plan_dict = execution_result.get("plan", {}) or {}
        steps = plan_dict.get("steps", [])
        all_verified = bool(steps) and all(
            s.get("verification_status") == "VERIFIED" or s.get("status") in ("SUCCESS", "SKIPPED")
            for s in steps
        )
        exec_ok = execution_result.get("status") == "SUCCESS"
        tools_ok = bool(steps) and all(bool(s.get("tool") or s.get("action_type") == "final") for s in steps)

        efficiency_notes: List[str] = []
        if model_calls > 2:
            efficiency_notes.append(f"High model call count ({model_calls}); consider procedural reuse.")
        if any((s.get("retry_count", 0) > 0) for s in steps):
            efficiency_notes.append("Retries occurred during execution.")

        return {
            "request_understood": bool(user_request and user_request.strip()),
            "strategy_appropriate": bool(strategy_decision and strategy_decision.get("strategy")),
            "plan_valid": bool(plan_valid),
            "tools_correct": tools_ok,
            "execution_succeeded": exec_ok,
            "independently_verified": all_verified and exec_ok,
            "completion_criteria_met": exec_ok and all_verified,
            "efficiency_notes": efficiency_notes,
        }

    # ------------------------------------------------------------------
    # Stage 8: Strategy Performance Tracking
    # ------------------------------------------------------------------
    def get_strategy_stats(self, task_category: str, strategy_used: str, min_samples: int = 3) -> Dict[str, Any]:
        rows = self._conn.execute("""
            SELECT outcome, verification_outcome, duration_ms, recovery_attempts, user_correction, model_calls, errors_json
            FROM task_experiences
            WHERE task_category = ? AND strategy_used = ?
        """, (task_category, strategy_used)).fetchall()

        n = len(rows)
        if n == 0:
            return {"sample_size": 0, "insufficient_samples": True}

        success_cnt = sum(1 for r in rows if r["outcome"] == "SUCCESS")
        verified_cnt = sum(1 for r in rows if r["verification_outcome"] == "VERIFIED")
        recovered_cnt = sum(1 for r in rows if r["recovery_attempts"] > 0 and r["outcome"] == "SUCCESS")
        recovery_total = sum(1 for r in rows if r["recovery_attempts"] > 0)
        corr_cnt = sum(1 for r in rows if r["user_correction"])
        tool_fail_cnt = sum(1 for r in rows if json.loads(r["errors_json"]))

        return {
            "task_category": task_category,
            "strategy_used": strategy_used,
            "sample_size": n,
            "insufficient_samples": n < min_samples,
            "task_success_rate": round(success_cnt / n, 3),
            "verified_completion_rate": round(verified_cnt / n, 3),
            "recovery_success_rate": round(recovered_cnt / recovery_total, 3) if recovery_total else 1.0,
            "avg_execution_ms": round(sum(r["duration_ms"] for r in rows) / n, 2),
            "avg_model_calls": round(sum(r["model_calls"] for r in rows) / n, 2),
            "tool_failure_freq": round(tool_fail_cnt / n, 3),
            "user_correction_freq": round(corr_cnt / n, 3),
        }

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
