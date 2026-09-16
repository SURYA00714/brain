from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class RequestTelemetry:
    """
    Granular Phase 16/17 Telemetry & LLM Call Audit record.
    Tracks every millisecond spent across pipeline phases and audits model usage and provenance.
    """
    request: str = ""
    safety_ms: float = 0.0
    classifier_ms: float = 0.0
    state_lookup_ms: float = 0.0
    memory_lookup_ms: float = 0.0
    planner_ms: float = 0.0
    reasoning_required: bool = False
    llm_provider: str = "NONE"
    llm_calls_this_request: int = 0
    llm_time_ms: float = 0.0
    cloud_attempted: bool = False
    cloud_failure_reason: Optional[str] = None
    fallback_used: bool = False
    tool_ms: float = 0.0
    verification_ms: float = 0.0
    total_ms: float = 0.0
    deterministic_success: bool = True
    provenance: str = "STATIC"
    goal_status: Optional[str] = None
    unnecessary_llm_call: bool = False
    false_verification: bool = False
    replan_count: int = 0
    goal_step_count: int = 0
    verification_method: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Sanitize any accidental secret leakage in string fields
        for k, v in list(d.items()):
            if isinstance(v, str):
                for secret_kw in ("gsk_", "AIza", "Bearer "):
                    if secret_kw in v:
                        d[k] = "[REDACTED_SECRET]"
        return d

    def summary(self) -> str:
        return (
            f"REQUEST: '{self.request}'\n"
            f"  safety:       {self.safety_ms:>7.2f} ms\n"
            f"  classifier:   {self.classifier_ms:>7.2f} ms\n"
            f"  state_lookup: {self.state_lookup_ms:>7.2f} ms\n"
            f"  memory_lookup:{self.memory_lookup_ms:>7.2f} ms\n"
            f"  planner:      {self.planner_ms:>7.2f} ms\n"
            f"  llm_calls:    {self.llm_calls_this_request} (provider: {self.llm_provider}, time: {self.llm_time_ms:.2f} ms)\n"
            f"  tool_exec:    {self.tool_ms:>7.2f} ms\n"
            f"  verification: {self.verification_ms:>7.2f} ms\n"
            f"  TOTAL:        {self.total_ms:>7.2f} ms (deterministic: {self.deterministic_success})"
        )


class TelemetryTracker:
    """Singleton tracker for request execution telemetry."""
    def __init__(self):
        self._current: Optional[RequestTelemetry] = None
        self._history: list[RequestTelemetry] = []

    def start_request(self, request_text: str) -> RequestTelemetry:
        self._current = RequestTelemetry(request=request_text)
        return self._current

    @property
    def current(self) -> RequestTelemetry:
        if self._current is None:
            self._current = RequestTelemetry()
        return self._current

    def finish_request(self) -> RequestTelemetry:
        rec = self.current
        self._history.append(rec)
        return rec

    def get_last(self) -> Optional[RequestTelemetry]:
        return self._history[-1] if self._history else self._current


default_telemetry = TelemetryTracker()
