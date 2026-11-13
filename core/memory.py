import re
import time
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brain_memory.db"

VALID_MEMORY_TYPES = {
    "FACT", "PREFERENCE", "TASK", "EVENT", "DECISION", "EXPERIENCE", "CONTEXT",
    "EPISODIC", "PROCEDURAL", "FAILURE"
}

MEMORY_CATEGORY_MAP = {
    "FACT": "LONG_TERM",
    "PREFERENCE": "LONG_TERM",
    "DECISION": "LONG_TERM",
    "TASK": "EPISODIC",
    "EVENT": "EPISODIC",
    "EXPERIENCE": "EPISODIC",
    "EPISODIC": "EPISODIC",
    "PROCEDURAL": "PROCEDURAL",
    "FAILURE": "FAILURE",
    "CONTEXT": "SHORT_TERM",
}

# Patterns for sensitive credentials, secrets, or API keys that must NEVER be persisted
SENSITIVE_PATTERNS = [
    r"\bgsk_[a-zA-Z0-9_-]{20,}\b",         # Groq API key
    r"\bAIza[0-9A-Za-z-_]{35}\b",          # Google API key
    r"\bsk-[a-zA-Z0-9_-]{20,}\b",          # OpenAI / generic key
    r"\bghp_[a-zA-Z0-9]{36}\b",            # GitHub personal token
    r"\b[A-Za-z0-9+/]{40,}\b={0,2}",        # High-entropy base64 tokens
    r"\b(password|passwd|pwd|secret)\s*[:=]\s*\S+", # Cleartext passwords
    r"\b(bearer|token)\s+[a-zA-Z0-9_\-\.]{20,}\b",
    r"-----BEGIN (RSA|OPENSSH|PGP|PRIVATE) KEY-----"
]

MAX_MEMORY_VALUE_LENGTH = 500


@dataclass
class MemoryRecord:
    """Structured representation of a single memory unit in Brain."""
    memory_type: str
    subject: str
    key: str
    value: str
    confidence: float = 1.0
    source: str = "user"
    id: Optional[int] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    verified: bool = True
    relevance_score: float = 0.0

    def is_stale(self, default_max_age: Optional[float] = None) -> bool:
        """Checks whether this memory has exceeded its TTL or max age."""
        limit = self.ttl_seconds if self.ttl_seconds is not None else default_max_age
        if limit is None or self.updated_at <= 0:
            return False
        return (time.time() - self.updated_at) > limit

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryPolicy:
    """
    Deterministic Quality Control & Privacy Boundary for Memory Persistence.
    Enforces quality checks, length boundaries, and secret filtering before storage.
    """
    @classmethod
    def evaluate(cls, memory_type: str, subject: str, key: str, value: str, verified: bool = True) -> Tuple[str, Optional[str], Optional[MemoryRecord]]:
        """
        Evaluates a candidate memory against safety, quality, and privacy rules.
        Returns: (Decision: "REMEMBER" | "TEMPORARY" | "IGNORE", reason, sanitized_record)
        """
        clean_type = str(memory_type).upper().strip()
        if clean_type not in VALID_MEMORY_TYPES:
            return "IGNORE", f"Invalid memory type '{memory_type}'.", None

        # Avoid storing unverified information as permanent long-term facts/preferences
        if not verified and clean_type in ("FACT", "PREFERENCE", "PROCEDURAL"):
            return "TEMPORARY", "Unverified information cannot be stored as a permanent fact.", None

        clean_sub = str(subject).strip().lower()
        clean_key = str(key).strip().lower()
        clean_val = str(value).strip()

        if not clean_key or not clean_val:
            return "IGNORE", "Memory key and value must be non-empty.", None

        # Check maximum length boundary
        if len(clean_val) > MAX_MEMORY_VALUE_LENGTH:
            return "IGNORE", f"Memory value exceeds maximum allowed length ({MAX_MEMORY_VALUE_LENGTH} chars).", None

        # Privacy Shield: Reject any sensitive credentials or secrets
        combined_text = f"{clean_key} {clean_val}"
        sensitive_keywords = ["password", "passwd", "secret", "api_key", "apikey", "credential"]
        if any(kw in clean_key for kw in sensitive_keywords):
            return "IGNORE", "Privacy Policy Violation: Memory contains sensitive credentials or secrets.", None

        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, combined_text, flags=re.IGNORECASE):
                return "IGNORE", "Privacy Policy Violation: Memory contains sensitive credentials or secrets.", None

        # Anti-Injection Shield: Reject raw command injection scripts disguised as memories
        dangerous_patterns = [
            r"rm\s+-rf", r"\bsudo\b", r";\s*rm\b", r":\(\)\s*\{",
            r"<untrusted_data", r"</untrusted_data>", r"\beval\s*\(", r"\bexec\s*\("
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, combined_text, flags=re.IGNORECASE):
                return "IGNORE", "Security Policy Violation: Memory contains forbidden command execution syntax.", None

        # Ephemeral / Temporary context detection (applies to facts/preferences/context, not failure/procedural logs)
        temporary_keywords = ["temporary", "just for now", "for now", "for this step", "current query", "for this session", "search "]
        if clean_type in ("FACT", "PREFERENCE", "CONTEXT") and any(kw in combined_text.lower() for kw in temporary_keywords):
            return "TEMPORARY", "Memory marked as temporary context.", None

        record = MemoryRecord(
            memory_type=clean_type,
            subject=clean_sub,
            key=clean_key,
            value=clean_val,
            created_at=time.time(),
            updated_at=time.time()
        )
        return "REMEMBER", None, record

    @classmethod
    def classify_memory_intent(cls, text: str) -> str:
        """
        Classifies input text into Stage 7M memory policy categories:
        EPHEMERAL | TASK_CONTEXT | POTENTIAL_MEMORY | SENSITIVE | IGNORE
        """
        if not text or not isinstance(text, str):
            return "IGNORE"

        lowered = text.lower().strip()

        # Check sensitive
        sensitive_keywords = ["password", "passwd", "secret", "api_key", "apikey", "credential", "token"]
        if any(kw in lowered for kw in sensitive_keywords):
            return "SENSITIVE"

        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                return "SENSITIVE"

        # Check ephemeral requests
        ephemeral_patterns = [r"^search\b", r"^open\b", r"^close\b", r"^focus\b", r"^click\b", r"^type\b"]
        if any(re.search(p, lowered) for p in ephemeral_patterns):
            return "EPHEMERAL"

        # Check potential persistent memory / project facts
        memory_triggers = ["uses ", "located at ", "path is ", "prefer ", "my name is ", "remember ", "always "]
        if any(trig in lowered for trig in memory_triggers):
            return "POTENTIAL_MEMORY"

def classify_memory_intent(text: str) -> str:
    """Stage 7M memory policy classification helper."""
    return MemoryPolicy.classify_memory_intent(text)


class MemoryStore:
    """
    Lightweight, embedded persistent memory storage powered by SQLite.
    Zero external database daemons, bounded file-based storage (<50 GB budget compliant).
    """
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
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
        """Initializes relational tables and search indexes."""
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    ttl_seconds REAL,
                    verified INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(memory_type, subject, key)
                )
            """)
            # Safe schema migration for existing DBs
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(memories)").fetchall()}
            if "ttl_seconds" not in cols:
                self._conn.execute("ALTER TABLE memories ADD COLUMN ttl_seconds REAL")
            if "verified" not in cols:
                self._conn.execute("ALTER TABLE memories ADD COLUMN verified INTEGER NOT NULL DEFAULT 1")
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_type_sub ON memories (memory_type, subject);
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    task_id TEXT,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SUCCESS',
                    metadata TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_events_time ON task_events (timestamp DESC);
            """)

    def detect_conflicting_memories(self, subject: str, key: str, value: str) -> List[MemoryRecord]:
        """Detects existing memories for the same subject and key with a different value."""
        sub = str(subject).strip().lower()
        k = str(key).strip().lower()
        val = str(value).strip()
        cursor = self._conn.execute("""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count, ttl_seconds, verified
            FROM memories
            WHERE subject = ? AND key = ? AND LOWER(TRIM(value)) != LOWER(TRIM(?))
        """, (sub, k, val))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: sqlite3.Row, relevance_score: float = 0.0) -> MemoryRecord:
        keys = row.keys()
        return MemoryRecord(
            id=row["id"],
            memory_type=row["memory_type"],
            subject=row["subject"],
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            ttl_seconds=row["ttl_seconds"] if "ttl_seconds" in keys else None,
            verified=bool(row["verified"]) if "verified" in keys else True,
            relevance_score=relevance_score,
        )

    def add_memory(
        self,
        memory_type: str,
        subject: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "user",
        ttl_seconds: Optional[float] = None,
        verified: bool = True,
        allow_overwrite: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates through MemoryPolicy and stores/updates a persistent memory.
        Detects conflicting memories and prevents duplicate or unverified permanent facts.
        Returns (success: bool, error_or_reason: Optional[str]).
        """
        decision, reason, record = MemoryPolicy.evaluate(memory_type, subject, key, value, verified=verified)
        if decision != "REMEMBER" or record is None:
            return False, reason or "Memory rejected by policy."

        conflicts = self.detect_conflicting_memories(record.subject, record.key, record.value)
        if conflicts and not allow_overwrite:
            existing_vals = ", ".join(c.value for c in conflicts)
            return False, f"Conflicting memory detected for {record.subject}.{record.key}: existing='{existing_vals}', new='{record.value}'"

        now = time.time()
        try:
            with self._conn:
                self._conn.execute("""
                    INSERT INTO memories (memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count, ttl_seconds, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    ON CONFLICT(memory_type, subject, key) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        updated_at = excluded.updated_at,
                        ttl_seconds = excluded.ttl_seconds,
                        verified = excluded.verified
                """, (
                    record.memory_type,
                    record.subject,
                    record.key,
                    record.value,
                    confidence,
                    source,
                    now,
                    now,
                    ttl_seconds,
                    1 if verified else 0,
                ))
            if conflicts:
                self.record_event(
                    "MEMORY_CONFLICT_RESOLVED",
                    f"Updated {record.subject}.{record.key} from '{conflicts[0].value}' to '{record.value}'",
                    status="SUCCESS",
                    metadata={"source": source}
                )
            return True, None
        except Exception as e:
            return False, f"Database write error: {str(e)}"

    def correct_memory(
        self,
        memory_type: str,
        subject: str,
        key: str,
        new_value: str,
        source: str = "user_correction"
    ) -> Tuple[bool, Optional[str]]:
        """Explicitly applies a user correction to an existing or new memory record."""
        ok, err = self.add_memory(
            memory_type=memory_type,
            subject=subject,
            key=key,
            value=new_value,
            confidence=1.0,
            source=source,
            verified=True,
            allow_overwrite=True,
        )
        if ok:
            self.record_event("USER_CORRECTION", f"Corrected {subject}.{key} = {new_value}", status="SUCCESS")
        return ok, err

    def record_procedural_workflow(self, goal: str, steps: List[str], verified: bool = True) -> Tuple[bool, Optional[str]]:
        """Stores a verified successful workflow in PROCEDURAL memory."""
        if not verified or not steps:
            return False, "Only verified non-empty workflows can be stored in procedural memory."
        key = re.sub(r"[^a-z0-9_]+", "_", goal.lower().strip())[:64].strip("_") or "workflow"
        val = " -> ".join(steps)[:MAX_MEMORY_VALUE_LENGTH]
        return self.add_memory("PROCEDURAL", "workflow", key, val, confidence=1.0, source="execution", verified=True)

    def record_failure_memory(self, error_pattern: str, corrective_action: str, tool_name: str = "") -> Tuple[bool, Optional[str]]:
        """Stores a failure pattern and its corrective action in FAILURE memory."""
        sub = (tool_name or "system").lower().strip()
        key = re.sub(r"[^a-z0-9_]+", "_", error_pattern.lower().strip())[:64].strip("_") or "error"
        val = f"Error: {error_pattern[:150]} | Fix: {corrective_action[:250]}"[:MAX_MEMORY_VALUE_LENGTH]
        return self.add_memory("FAILURE", sub, key, val, confidence=1.0, source="recovery", verified=True)

    def get_memory(self, memory_type: str, subject: str, key: str) -> Optional[MemoryRecord]:
        """Retrieves a single exact memory match by type, subject, and key."""
        cursor = self._conn.execute("""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count, ttl_seconds, verified
            FROM memories
            WHERE memory_type = ? AND subject = ? AND key = ?
        """, (str(memory_type).upper(), str(subject).lower(), str(key).lower()))
        row = cursor.fetchone()
        if not row:
            return None

        # Update access count
        with self._conn:
            self._conn.execute("UPDATE memories SET access_count = access_count + 1 WHERE id = ?", (row["id"],))

        rec = self._row_to_record(row)
        rec.access_count += 1
        return rec

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        exclude_stale: bool = True,
        min_relevance: float = 0.15
    ) -> List[MemoryRecord]:
        """
        Relevance-ranked metadata & keyword retrieval for memories.
        Scores by keyword match ratio, confidence, and freshness; avoids injecting irrelevant or stale memories.
        """
        clean_q = str(query).strip().lower()
        if not clean_q:
            return []

        STOPWORDS = {
            "can", "you", "find", "something", "using", "with", "about", "what", "which", "where",
            "when", "how", "the", "and", "for", "that", "this", "from", "have", "please", "tell",
            "are", "was", "were", "been", "will", "would", "could", "should", "does", "did"
        }
        tokens = [w for w in re.split(r"[^a-zA-Z0-9_]+", clean_q) if len(w) >= 3]
        expanded = []
        for t in tokens:
            expanded.append(t)
            if "_" in t:
                for sub in t.split("_"):
                    if len(sub) >= 3:
                        expanded.append(sub)

        meaningful = [w for w in expanded if w not in STOPWORDS]
        keywords = list(dict.fromkeys(meaningful if meaningful else expanded))[:10]
        if not keywords:
            keywords = [clean_q]

        like_clauses = " OR ".join(["key LIKE ? OR value LIKE ? OR subject LIKE ?"] * len(keywords))
        params: List[Any] = []
        for kw in keywords:
            pat = f"%{kw}%"
            params.extend([pat, pat, pat])

        type_clause = ""
        if memory_type:
            type_clause = "AND memory_type = ? "
            params.append(str(memory_type).upper())

        sql = f"""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count, ttl_seconds, verified
            FROM memories
            WHERE ({like_clauses}) {type_clause}
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
        """
        params.append(max(limit * 4, 20))

        try:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
            scored: List[MemoryRecord] = []
            now = time.time()
            for row in rows:
                rec = self._row_to_record(row)
                if exclude_stale and rec.is_stale():
                    continue
                blob = f"{rec.subject} {rec.key} {rec.value}".lower()
                hits = sum(1 for kw in keywords if kw in blob)
                kw_ratio = hits / len(keywords)
                age_days = max(0.0, (now - rec.updated_at) / 86400.0) if rec.updated_at else 0.0
                freshness = 1.0 / (1.0 + 0.05 * age_days)
                relevance = round(0.60 * kw_ratio + 0.25 * rec.confidence + 0.15 * freshness, 4)
                if hits == 0 or relevance < min_relevance:
                    continue
                rec.relevance_score = relevance
                scored.append(rec)

            scored.sort(key=lambda r: (r.relevance_score, r.updated_at), reverse=True)
            return scored[:limit]
        except Exception:
            return []

    def list_memories(self, limit: int = 50, memory_type: Optional[str] = None) -> List[MemoryRecord]:
        """Lists stored memory records, optionally filtered by type."""
        type_clause = "WHERE memory_type = ?" if memory_type else ""
        params = [str(memory_type).upper()] if memory_type else []
        sql = f"""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count
            FROM memories
            {type_clause}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params.append(limit)
        cursor = self._conn.execute(sql, tuple(params))
        records = []
        for row in cursor.fetchall():
            records.append(MemoryRecord(
                id=row["id"],
                memory_type=row["memory_type"],
                subject=row["subject"],
                key=row["key"],
                value=row["value"],
                confidence=row["confidence"],
                source=row["source"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                access_count=row["access_count"]
            ))
        return records

    def record_event(
        self,
        event_type: str,
        description: str,
        status: str = "SUCCESS",
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Records an execution or milestone event in persistent audit history."""
        import json
        meta_str = json.dumps(metadata) if metadata else None
        try:
            with self._conn:
                self._conn.execute("""
                    INSERT INTO task_events (event_type, task_id, description, status, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(event_type).upper(),
                    str(task_id) if task_id else None,
                    str(description),
                    str(status).upper(),
                    meta_str,
                    time.time()
                ))
            return True
        except Exception:
            return False

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches recent task events in chronological order."""
        import json
        cursor = self._conn.execute("""
            SELECT id, event_type, task_id, description, status, metadata, timestamp
            FROM task_events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        events = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            events.append({
                "id": r["id"],
                "event_type": r["event_type"],
                "task_id": r["task_id"],
                "description": r["description"],
                "status": r["status"],
                "metadata": meta,
                "timestamp": r["timestamp"]
            })
        return events

    def purge_memory(self, memory_id: Optional[int] = None, subject: Optional[str] = None, key: Optional[str] = None) -> int:
        """
        User Privacy Control: Selectively purges memories by ID or subject/key match.
        Returns the number of deleted records.
        """
        deleted_count = 0
        with self._conn:
            if memory_id is not None:
                cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                deleted_count = cursor.rowcount
            elif subject is not None and key is not None:
                cursor = self._conn.execute("DELETE FROM memories WHERE subject = ? AND key = ?", (subject, key))
                deleted_count = cursor.rowcount
            elif subject is not None:
                cursor = self._conn.execute("DELETE FROM memories WHERE subject = ?", (subject,))
                deleted_count = cursor.rowcount
            elif key is not None:
                cursor = self._conn.execute("DELETE FROM memories WHERE key = ?", (key,))
                deleted_count = cursor.rowcount
        return deleted_count

    def clear(self) -> None:
        """Clears all stored memories and events (primarily for test resets)."""
        with self._conn:
            self._conn.execute("DELETE FROM memories")
            self._conn.execute("DELETE FROM task_events")

    def close(self) -> None:
        """Closes the underlying database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


default_memory = MemoryStore()
