"""
Brain Unified Companion State & Event Broadcasting (Phase 19 Companion Evolution).
Acts as the single source of truth across Mind, Mouth, Face, Hands, and Presence.
"""

import time
import json
import threading
from queue import Queue
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


class CompanionActivity:
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SEARCHING = "SEARCHING"
    WORKING = "WORKING"
    WAITING = "WAITING"
    SUCCESS = "SUCCESS"
    CONFUSED = "CONFUSED"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SPEAKING = "SPEAKING"
    SLEEPING = "SLEEPING"


@dataclass
class CompanionEvent:
    event_type: str
    data: Any
    timestamp: float = field(default_factory=time.time)


@dataclass
class CompanionState:
    """Unified companion runtime state model."""
    activity: str = CompanionActivity.IDLE
    status_text: str = "Standing by"
    mood: str = "FOCUSED"
    speaking: bool = False
    listening: bool = False
    current_goal: Optional[str] = None
    current_application: Optional[str] = None
    current_task: Optional[str] = None
    progress: float = 0.0
    last_action: Optional[str] = None
    last_result: Optional[str] = None
    verification: str = "PENDING"  # PENDING, VERIFIED, FAILED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.activity  # Backwards compatibility with avatar UI
        return d


class CompanionStateManager:
    """Thread-safe manager for companion state and SSE subscriber fanout."""

    def __init__(self):
        self._state = CompanionState()
        self._lock = threading.Lock()
        self._subscribers: List[Queue] = []
        self._sub_lock = threading.Lock()

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def set_state(
        self,
        activity: Optional[str] = None,
        status_text: Optional[str] = None,
        mood: Optional[str] = None,
        speaking: Optional[bool] = None,
        listening: Optional[bool] = None,
        goal: Optional[str] = None,
        app: Optional[str] = None,
        task: Optional[str] = None,
        progress: Optional[float] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        verification: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates the unified companion state and broadcasts an SSE event."""
        with self._lock:
            if activity:
                self._state.activity = activity.upper()
            if status_text:
                self._state.status_text = status_text
            elif activity:
                self._state.status_text = activity.title()

            if mood:
                self._state.mood = mood.upper()
            if speaking is not None:
                self._state.speaking = speaking
            if listening is not None:
                self._state.listening = listening
            if goal is not None:
                self._state.current_goal = goal
            if app is not None:
                self._state.current_application = app
            if task is not None:
                self._state.current_task = task
            if progress is not None:
                self._state.progress = max(0.0, min(1.0, progress))
            if action is not None:
                self._state.last_action = action
            if result is not None:
                self._state.last_result = result
            if verification is not None:
                self._state.verification = verification

            self._state.timestamp = time.time()
            snapshot = self._state.to_dict()

        # Fan out SSE update event
        self.broadcast("STATE_CHANGE", snapshot)
        return snapshot

    def broadcast(self, event_type_or_event: Any, data: Any = None):
        """Sends an SSE formatted event to all active subscriber queues."""
        if isinstance(event_type_or_event, CompanionEvent):
            event = event_type_or_event
        else:
            event = CompanionEvent(event_type=str(event_type_or_event), data=data)

        with self._sub_lock:
            alive_subs = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                    alive_subs.append(q)
                except Exception:
                    pass
            self._subscribers = alive_subs

    def subscribe(self) -> Queue:
        """Subscribes an SSE connection queue."""
        q = Queue(maxsize=50)
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: Queue):
        """Removes an SSE connection queue."""
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


default_companion_state = CompanionStateManager()
