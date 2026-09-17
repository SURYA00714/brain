"""
Brain Proactive Awareness & Bounded Autonomy Engine (Phase 7).
Enables event-driven environment awareness and bounded, state-governed autonomous execution
under strict safety, timeout, step-limit, and cancellation constraints.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Tuple

from tools.apps import default_app_tracker, get_active_window_app_name
from core.event_bus import default_event_bus
from core.world_state import default_world_state


class ProactiveAwarenessEngine:
    """
    Monitors high-level system events (app focus changes, staleness, task timeouts).
    Generates internal events on the EventBus.
    NOTE: Proactive Event != Unchecked Automatic Action. Safety gate is always enforced.
    """
    def __init__(self, check_interval_seconds: float = 2.0):
        self.check_interval = check_interval_seconds
        self._last_check_time: float = 0.0
        self._last_focused_app: Optional[str] = None

    def inspect_environment(self) -> List[Dict[str, Any]]:
        """Inspects environment and emits proactive events when meaningful changes occur."""
        events = []
        now = time.time()
        if now - self._last_check_time < self.check_interval:
            return events

        self._last_check_time = now
        current_app = default_app_tracker.get_focused_app() or get_active_window_app_name()

        # 1. Active App Change
        if self._last_focused_app is not None and current_app and current_app != self._last_focused_app:
            evt_data = {"previous_app": self._last_focused_app, "current_app": current_app}
            events.append(evt_data)
            default_event_bus.publish("ACTIVE_WINDOW_CHANGED", evt_data)

        self._last_focused_app = current_app

        # 2. Staleness check
        if default_world_state.check_staleness() == "STALE":
            evt_data = {"reason": "World state observation window lapsed"}
            events.append(evt_data)
            default_event_bus.publish("PROACTIVE_AWARENESS", evt_data)

        return events


@dataclass
class AutonomyLimits:
    max_actions: int = 5
    max_duration_seconds: float = 30.0
    max_retries: int = 2


class BoundedAutonomyController:
    """
    Governs controlled autonomous execution loops.
    States: PASSIVE, READY, ACTIVE, WAITING, PAUSED, CANCELLED.
    Enforces maximum actions, duration, and retries.
    """
    def __init__(self, limits: Optional[AutonomyLimits] = None):
        self.limits = limits or AutonomyLimits()
        self.state = "PASSIVE"  # PASSIVE, READY, ACTIVE, WAITING, PAUSED, CANCELLED
        self.current_action_count = 0
        self.current_retry_count = 0
        self.start_time: float = 0.0

    def start_autonomy(self, task_name: str) -> bool:
        """Starts a bounded autonomous task loop."""
        self.state = "ACTIVE"
        self.current_action_count = 0
        self.current_retry_count = 0
        self.start_time = time.time()
        default_event_bus.publish("TASK_STARTED", {"task_name": task_name, "limits": asdict(self.limits)})
        return True

    def can_continue(self) -> Tuple[bool, Optional[str]]:

        """Evaluates whether autonomy loop may perform another step."""
        if self.state in ("PAUSED", "CANCELLED"):
            return False, f"Autonomy is currently {self.state}."

        if self.current_action_count >= self.limits.max_actions:
            self.state = "PAUSED"
            return False, f"Halting: Reached maximum action step limit ({self.limits.max_actions})."

        elapsed = time.time() - self.start_time
        if elapsed > self.limits.max_duration_seconds:
            self.state = "PAUSED"
            return False, f"Halting: Reached maximum execution duration limit ({self.limits.max_duration_seconds:.1f}s)."

        if self.current_retry_count > self.limits.max_retries:
            self.state = "PAUSED"
            return False, f"Halting: Reached maximum retry limit ({self.limits.max_retries})."

        return True, None

    def record_step(self, success: bool) -> None:
        self.current_action_count += 1
        if not success:
            self.current_retry_count += 1

    def cancel(self, reason: str = "user_request") -> None:
        self.state = "CANCELLED"
        default_event_bus.publish("TASK_CANCELLED", {"reason": reason})

    def complete(self) -> None:
        self.state = "PASSIVE"
        default_event_bus.publish("TASK_COMPLETED", {"action_count": self.current_action_count})


default_proactive_awareness = ProactiveAwarenessEngine()
default_autonomy_controller = BoundedAutonomyController()
