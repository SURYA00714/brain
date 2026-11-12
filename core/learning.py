"""
Controlled Offline Learning Pipeline for Brain (Phase 1.6).
Observes failures and user corrections, classifies root causes,
evaluates candidate corrections deterministically, and curates an
offline training dataset.
NEVER automatically modifies source code or model weights.
NEVER performs online self-training.
"""

import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


DEFAULT_LEARNING_DB = Path(__file__).resolve().parent.parent / "data" / "learning_pipeline.db"

OBSERVATION_TYPES = {
    "INCORRECT_ANSWER",
    "FAILED_PLAN",
    "TOOL_FAILURE",
    "USER_CORRECTION",
    "REPEATED_MISUNDERSTANDING",
}

ROOT_CAUSES = {
    "MODEL_ERROR",
    "PLANNING_ERROR",
    "TOOL_SELECTION_ERROR",
    "INVALID_PARAMETERS",
    "TOOL_EXECUTION_ERROR",
    "VERIFICATION_ERROR",
    "CONTEXT_ERROR",
    "SEARCH_EVIDENCE_ERROR",
    "USER_INPUT_AMBIGUITY",
    "PERMISSION_BLOCK",
    # Backward-compatible Phase 1.6 aliases
    "CONSTRAINT_VIOLATION",
    "INCOMPLETE_PLAN",
    "OFF_TOPIC_EVIDENCE",
    "AMBIGUITY_MISSED",
    "TOOL_PARAMETER_ERROR",
    "UNREGISTERED_TOOL",
    "MEMORY_CONFLICT",
    "OTHER",
}


@dataclass
class FailureObservation:
    observation_type: str
    user_input: str
    bad_output: str
    root_cause: str
    context: str = ""
    corrected_output: Optional[str] = None
    eval_passed: bool = False
    approved: bool = False
    id: Optional[int] = None
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ControlledLearningPipeline:
    """
    Controlled offline curation pipeline for failure analysis and dataset building.
    """
    AUTO_MODIFY_CODE = False
    AUTO_MODIFY_WEIGHTS = False
    ONLINE_SELF_TRAINING = False

    def __init__(self, db_path: Optional[Path] = None, min_examples_for_finetune: int = 50):
        if db_path is None:
            self.db_path = DEFAULT_LEARNING_DB
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.min_examples_for_finetune = min_examples_for_finetune
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS failure_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observation_type TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    bad_output TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    corrected_output TEXT,
                    eval_passed INTEGER NOT NULL DEFAULT 0,
                    approved INTEGER NOT NULL DEFAULT 0,
                    source TEXT DEFAULT 'runtime',
                    eval_history TEXT DEFAULT '[]',
                    created_at REAL NOT NULL
                )
            """)
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(failure_observations)").fetchall()}
            if "source" not in cols:
                self._conn.execute("ALTER TABLE failure_observations ADD COLUMN source TEXT DEFAULT 'runtime'")
            if "eval_history" not in cols:
                self._conn.execute("ALTER TABLE failure_observations ADD COLUMN eval_history TEXT DEFAULT '[]'")

    @staticmethod
    def classify_root_cause(observation_type: str, error_reason: str = "") -> str:
        """Deterministically classifies a failure into the 10 standardized root-cause categories."""
        err = (error_reason or "").lower()
        obs = (observation_type or "").upper()
        if "permission" in err or "confirmation" in err or "safety block" in err or "protected system" in err:
            return "PERMISSION_BLOCK"
        if "parameter" in err or "requires '" in err or "missing param" in err:
            return "INVALID_PARAMETERS"
        if "hallucinated tool" in err or "not registered" in err:
            return "TOOL_SELECTION_ERROR"
        if "incomplete plan" in err or "circular dependency" in err or "missing step_id" in err or "malformed json" in err or "completion_criteria" in err:
            return "PLANNING_ERROR"
        if "verification" in err or "unverified" in err or "empty payload" in err or "zero results" in err:
            return "VERIFICATION_ERROR"
        if "could not verify" in err or "off-topic" in err or "portal" in err or "evidence" in err:
            return "SEARCH_EVIDENCE_ERROR"
        if "clarify" in err or "ambiguous" in err or obs == "REPEATED_MISUNDERSTANDING":
            return "USER_INPUT_AMBIGUITY"
        if "conflict" in err or "stale" in err or "context" in err:
            return "CONTEXT_ERROR"
        if "timeout" in err or "execution" in err or obs == "TOOL_FAILURE":
            return "TOOL_EXECUTION_ERROR"
        if "forbidden" in err or "constraint" in err or "token limit" in err:
            return "MODEL_ERROR"
        return "MODEL_ERROR" if obs == "INCORRECT_ANSWER" else "TOOL_EXECUTION_ERROR"

    def record_failure(
        self,
        observation_type: str,
        user_input: str,
        bad_output: str,
        error_reason: str = "",
        context: str = ""
    ) -> int:
        obs_type = observation_type.upper()
        if obs_type not in OBSERVATION_TYPES:
            obs_type = "INCORRECT_ANSWER"
        cause = self.classify_root_cause(obs_type, error_reason)
        now = time.time()
        with self._conn:
            cur = self._conn.execute("""
                INSERT INTO failure_observations
                (observation_type, user_input, bad_output, root_cause, context, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (obs_type, user_input, bad_output, cause, context, now))
            return int(cur.lastrowid)

    def propose_and_evaluate_correction(
        self,
        observation_id: int,
        corrected_output: str,
        evaluator_fn=None
    ) -> Tuple[bool, str]:
        """
        Attaches a corrected example to an observation and evaluates it deterministically.
        Approves into training dataset ONLY if deterministic evaluation passes.
        """
        row = self._conn.execute(
            "SELECT * FROM failure_observations WHERE id = ?", (observation_id,)
        ).fetchone()
        if not row:
            return False, f"Observation {observation_id} not found."

        if not corrected_output or not corrected_output.strip():
            return False, "Corrected output cannot be empty."

        passed = True
        reason = "Passed basic non-empty check"
        if evaluator_fn is not None:
            passed, reason = evaluator_fn(row["user_input"], corrected_output)

        hist = json.loads(row["eval_history"]) if "eval_history" in row.keys() and row["eval_history"] else []
        hist.append({"timestamp": time.time(), "passed": bool(passed), "reason": str(reason)})

        with self._conn:
            self._conn.execute("""
                UPDATE failure_observations
                SET corrected_output = ?, eval_passed = ?, approved = ?, eval_history = ?
                WHERE id = ?
            """, (corrected_output, 1 if passed else 0, 1 if passed else 0, json.dumps(hist), observation_id))

        return passed, reason

    def get_approved_examples(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute("""
            SELECT id, observation_type, user_input, bad_output, corrected_output, root_cause, context, created_at
            FROM failure_observations
            WHERE approved = 1 AND eval_passed = 1 AND corrected_output IS NOT NULL
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def export_training_dataset(self, output_path: Path) -> int:
        """Exports deduplicated, secret-scrubbed approved examples to JSONL."""
        from models.gateway import ModelGateway
        examples = self.get_approved_examples()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        seen = set()
        written = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in examples:
                prompt = ex["user_input"]
                comp = ex["corrected_output"]
                if ModelGateway.contains_sensitive_data(prompt) or ModelGateway.contains_sensitive_data(comp):
                    continue
                key = (prompt.strip().lower(), comp.strip().lower())
                if key in seen:
                    continue
                seen.add(key)
                record = {
                    "prompt": prompt,
                    "completion": comp,
                    "root_cause": ex["root_cause"],
                    "observation_type": ex["observation_type"],
                }
                f.write(json.dumps(record) + "\n")
                written += 1
        return written

    def export_split_datasets(self, train_path: Path, eval_path: Path, eval_ratio: float = 0.2) -> Tuple[int, int]:
        """Deduplicates, scrubs secrets, and splits approved examples into train and held-out eval JSONL files."""
        from models.gateway import ModelGateway
        examples = self.get_approved_examples()
        clean_records = []
        seen = set()
        for ex in examples:
            prompt = ex["user_input"]
            comp = ex["corrected_output"]
            if ModelGateway.contains_sensitive_data(prompt) or ModelGateway.contains_sensitive_data(comp):
                continue
            key = (prompt.strip().lower(), comp.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            clean_records.append({
                "prompt": prompt,
                "completion": comp,
                "root_cause": ex["root_cause"],
                "observation_type": ex["observation_type"],
            })

        if not clean_records:
            return 0, 0

        eval_n = max(1, int(round(len(clean_records) * eval_ratio))) if len(clean_records) >= 2 else 0
        eval_recs = clean_records[:eval_n]
        train_recs = clean_records[eval_n:]

        for path, recs in ((train_path, train_recs), (eval_path, eval_recs)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")

        return len(train_recs), len(eval_recs)

    REASONING_CAUSES = {
        "MODEL_ERROR", "PLANNING_ERROR", "SEARCH_EVIDENCE_ERROR",
        "USER_INPUT_AMBIGUITY", "CONTEXT_ERROR", "CONSTRAINT_VIOLATION",
        "INCOMPLETE_PLAN", "OFF_TOPIC_EVIDENCE", "AMBIGUITY_MISSED", "MEMORY_CONFLICT"
    }
    TOOL_CAUSES = {
        "TOOL_SELECTION_ERROR", "INVALID_PARAMETERS", "TOOL_EXECUTION_ERROR",
        "VERIFICATION_ERROR", "PERMISSION_BLOCK", "TOOL_PARAMETER_ERROR", "UNREGISTERED_TOOL"
    }

    def export_curated_datasets(
        self,
        reasoning_path: Path,
        tool_path: Path,
        benchmark_inputs: Optional[set] = None
    ) -> Dict[str, int]:
        """
        Exports high-quality, deduplicated, secret-scrubbed, non-contradictory,
        leak-free datasets separated into reasoning vs tool failures.
        """
        from models.gateway import ModelGateway
        examples = self.get_approved_examples()
        bench_norm = {b.strip().lower() for b in (benchmark_inputs or set())}

        # Detect contradictory labels for identical prompts
        prompt_completions: Dict[str, set] = {}
        for ex in examples:
            p_norm = ex["user_input"].strip().lower()
            prompt_completions.setdefault(p_norm, set()).add(ex["corrected_output"].strip().lower())

        seen = set()
        reasoning_recs = []
        tool_recs = []
        skipped_leak = 0
        skipped_contradiction = 0

        for ex in examples:
            prompt = ex["user_input"]
            comp = ex["corrected_output"]
            p_norm = prompt.strip().lower()
            c_norm = comp.strip().lower()

            if p_norm in bench_norm:
                skipped_leak += 1
                continue
            if len(prompt_completions.get(p_norm, set())) > 1:
                skipped_contradiction += 1
                continue
            if ModelGateway.contains_sensitive_data(prompt) or ModelGateway.contains_sensitive_data(comp):
                continue
            if (p_norm, c_norm) in seen:
                continue
            seen.add((p_norm, c_norm))

            rec = {
                "prompt": prompt,
                "completion": comp,
                "root_cause": ex["root_cause"],
                "observation_type": ex["observation_type"],
            }
            if ex["root_cause"] in self.TOOL_CAUSES:
                tool_recs.append(rec)
            else:
                reasoning_recs.append(rec)

        for path, recs in ((reasoning_path, reasoning_recs), (tool_path, tool_recs)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")

        return {
            "reasoning_count": len(reasoning_recs),
            "tool_count": len(tool_recs),
            "skipped_benchmark_leak": skipped_leak,
            "skipped_contradictions": skipped_contradiction,
        }

    def check_finetune_readiness(self, independent_eval_passed: bool = False) -> Dict[str, Any]:
        """
        Evaluates whether sufficient offline evidence exists to consider manual fine-tuning.
        Never triggers automatic weight updates.
        """
        approved_count = len(self.get_approved_examples())
        ready = (approved_count >= self.min_examples_for_finetune) and independent_eval_passed
        return {
            "ready_for_offline_finetune": ready,
            "approved_examples": approved_count,
            "required_examples": self.min_examples_for_finetune,
            "independent_eval_passed": independent_eval_passed,
            "auto_modify_weights": self.AUTO_MODIFY_WEIGHTS,
            "online_self_training": self.ONLINE_SELF_TRAINING,
        }

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
