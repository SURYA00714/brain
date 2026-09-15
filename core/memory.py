import re
import time
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "brain_memory.db"

VALID_MEMORY_TYPES = {
    "FACT", "PREFERENCE", "TASK", "EVENT", "DECISION", "EXPERIENCE", "CONTEXT"
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryPolicy:
    """
    Deterministic Quality Control & Privacy Boundary for Memory Persistence.
    Enforces quality checks, length boundaries, and secret filtering before storage.
    """
    @classmethod
    def evaluate(cls, memory_type: str, subject: str, key: str, value: str) -> Tuple[str, Optional[str], Optional[MemoryRecord]]:
        """
        Evaluates a candidate memory against safety, quality, and privacy rules.
        Returns: (Decision: "REMEMBER" | "TEMPORARY" | "IGNORE", reason, sanitized_record)
        """
        clean_type = str(memory_type).upper().strip()
        if clean_type not in VALID_MEMORY_TYPES:
            return "IGNORE", f"Invalid memory type '{memory_type}'.", None

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

        # Ephemeral / Temporary context detection
        temporary_keywords = ["temporary", "just for now", "for now", "for this step", "current query", "for this session"]
        if any(kw in combined_text.lower() for kw in temporary_keywords):
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
                    UNIQUE(memory_type, subject, key)
                )
            """)
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

    def add_memory(
        self,
        memory_type: str,
        subject: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "user"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates through MemoryPolicy and stores/updates a persistent memory.
        Returns (success: bool, error_or_reason: Optional[str]).
        """
        decision, reason, record = MemoryPolicy.evaluate(memory_type, subject, key, value)
        if decision != "REMEMBER" or record is None:
            return False, reason or "Memory rejected by policy."

        now = time.time()
        try:
            with self._conn:
                self._conn.execute("""
                    INSERT INTO memories (memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(memory_type, subject, key) DO UPDATE SET
                        value = excluded.value,
                        confidence = excluded.confidence,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                """, (
                    record.memory_type,
                    record.subject,
                    record.key,
                    record.value,
                    confidence,
                    source,
                    now,
                    now
                ))
            return True, None
        except Exception as e:
            return False, f"Database write error: {str(e)}"

    def get_memory(self, memory_type: str, subject: str, key: str) -> Optional[MemoryRecord]:
        """Retrieves a single exact memory match by type, subject, and key."""
        cursor = self._conn.execute("""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count
            FROM memories
            WHERE memory_type = ? AND subject = ? AND key = ?
        """, (str(memory_type).upper(), str(subject).lower(), str(key).lower()))
        row = cursor.fetchone()
        if not row:
            return None

        # Update access count
        with self._conn:
            self._conn.execute("UPDATE memories SET access_count = access_count + 1 WHERE id = ?", (row["id"],))

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
            access_count=row["access_count"] + 1
        )

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None
    ) -> List[MemoryRecord]:
        """
        Lightweight metadata & keyword retrieval for relevant memories.
        Ranks by keyword match, confidence, and recency without bloated vector DBs.
        """
        clean_q = str(query).strip().lower()
        if not clean_q:
            return []

        # Extract search keywords with stopword filtering and sub-tokenization
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
        keywords = (meaningful if meaningful else expanded)[:10]
        if not keywords:
            keywords = [clean_q]

        like_clauses = " OR ".join(["key LIKE ? OR value LIKE ? OR subject LIKE ?"] * len(keywords))
        params = []
        for kw in keywords:
            pat = f"%{kw}%"
            params.extend([pat, pat, pat])

        type_clause = ""
        if memory_type:
            type_clause = "AND memory_type = ? "
            params.append(str(memory_type).upper())

        sql = f"""
            SELECT id, memory_type, subject, key, value, confidence, source, created_at, updated_at, access_count
            FROM memories
            WHERE ({like_clauses}) {type_clause}
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
        """
        params.append(limit)

        try:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append(MemoryRecord(
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
            return results
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
