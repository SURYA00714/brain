"""
Brain Typed Event Bus (Phase 7).
Lightweight, bounded, event-driven architecture connecting Mind, Body, Perception, Voice, and Safety.
"""

import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Callable, Optional


EVENT_TYPES = {
    "USER_MESSAGE",
    "TASK_STARTED",
    "TASK_UPDATED",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "TASK_CANCELLED",
    "ACTIVE_WINDOW_CHANGED",
    "OBSERVATION_UPDATED",
    "SAFETY_BLOCK",
    "CONFIRMATION_REQUIRED",
    "COMPANION_STATE_CHANGED",
    "VOICE_STARTED",
    "VOICE_STOPPED",
    "DESKTOP_MATE_CONNECTED",
    "DESKTOP_MATE_DISCONNECTED",
    "PROACTIVE_AWARENESS",
    "RESOURCE_WARNING"
}


@dataclass
class BrainEvent:
    """Typed event unit."""
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventBus:
    """Thread-safe event bus with bounded sliding archive."""
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: List[BrainEvent] = []
        self._subscribers: Dict[str, List[Callable[[BrainEvent], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable[[BrainEvent], None]) -> None:
        """Subscribe a callback to a specific event type or '*' for all events."""
        with self._lock:
            evt_key = str(event_type).upper()
            if evt_key not in self._subscribers:
                self._subscribers[evt_key] = []
            if callback not in self._subscribers[evt_key]:
                self._subscribers[evt_key].append(callback)

    def publish(self, event_type_or_event: Any, data: Optional[Dict[str, Any]] = None) -> BrainEvent:
        """Publishes a typed event to subscribers and records in bounded archive."""
        if isinstance(event_type_or_event, BrainEvent):
            event = event_type_or_event
        else:
            evt_name = str(event_type_or_event).upper()
            event = BrainEvent(event_type=evt_name, data=data or {})

        with self._lock:
            self._history.append(event)
            if len(self._history) > self.max_history:
                self._history.pop(0)

            target_subs = self._subscribers.get(event.event_type, []) + self._subscribers.get("*", [])

        # Dispatch callbacks safely outside lock
        for cb in target_subs:
            try:
                cb(event)
            except Exception:
                pass

        return event

    def get_recent_events(self, limit: int = 10, event_type: Optional[str] = None) -> List[BrainEvent]:
        with self._lock:
            filtered = self._history
            if event_type:
                evt_upper = str(event_type).upper()
                filtered = [e for e in self._history if e.event_type == evt_upper]
            return filtered[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


default_event_bus = EventBus()
