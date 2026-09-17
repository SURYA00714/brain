"""
Brain Interaction Session Manager (Phase 7).
Tracks session lifecycle, generation tokens, and turn activity across conversational turns
without requiring process restarts.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


@dataclass
class InteractionSession:
    """Bounded, persistent interaction session snapshot."""
    session_id: str = field(default_factory=lambda: f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}")
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    current_task: Optional[str] = None
    current_goal: Optional[str] = None
    current_state: str = "ACTIVE"  # ACTIVE, PAUSED, IDLE, ENDED
    recent_user_input: Optional[str] = None
    recent_brain_response: Optional[str] = None
    interruption_status: str = "NONE"  # NONE, INTERRUPTED, CANCELLED
    generation_id: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SessionManager:
    """Thread-safe interaction session controller."""
    def __init__(self):
        self._current_session: Optional[InteractionSession] = None
        self.start_session()

    def start_session(self, session_id: Optional[str] = None) -> InteractionSession:
        now = time.time()
        sid = session_id or f"session_{int(now)}_{uuid.uuid4().hex[:6]}"
        self._current_session = InteractionSession(
            session_id=sid,
            started_at=now,
            last_activity=now,
            current_state="ACTIVE",
            generation_id=1
        )
        return self._current_session

    def get_active_session(self) -> InteractionSession:
        if not self._current_session or self._current_session.current_state == "ENDED":
            return self.start_session()
        return self._current_session

    def update_session(
        self,
        user_input: Optional[str] = None,
        brain_response: Optional[str] = None,
        task: Optional[str] = None,
        goal: Optional[str] = None,
        state: Optional[str] = None,
        interruption_status: Optional[str] = None
    ) -> InteractionSession:
        sess = self.get_active_session()
        now = time.time()
        sess.last_activity = now

        if user_input is not None:
            sess.recent_user_input = user_input
        if brain_response is not None:
            sess.recent_brain_response = brain_response
        if task is not None:
            sess.current_task = task
        if goal is not None:
            sess.current_goal = goal
        if state is not None:
            sess.current_state = state
        if interruption_status is not None:
            sess.interruption_status = interruption_status

        return sess

    def bump_generation(self) -> int:
        """Increments generation token when new user requests or interruptions arrive."""
        sess = self.get_active_session()
        sess.generation_id += 1
        sess.last_activity = time.time()
        return sess.generation_id

    def interrupt_session(self, reason: str = "user_request") -> InteractionSession:
        """Interrupts current session, updates interruption status, and bumps generation token."""
        sess = self.get_active_session()
        sess.interruption_status = "INTERRUPTED"
        sess.last_activity = time.time()
        self.bump_generation()
        return sess

    def reset_session(self) -> InteractionSession:
        return self.start_session()


    def end_session(self) -> None:
        if self._current_session:
            self._current_session.current_state = "ENDED"
            self._current_session.last_activity = time.time()


default_session_manager = SessionManager()
