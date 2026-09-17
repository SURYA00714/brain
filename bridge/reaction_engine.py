"""
Brain Reaction Engine — Deterministic, cooldown-gated state→animation/expression mapper.

Maps Brain CompanionState events to Desktop Mate actions through the bridge.

RULES:
- Cooldown: min 2s between any reaction, 5s between same-type reactions.
- Priority: ERROR > SUCCESS > WORKING > THINKING > IDLE.
- Only uses VRM 1.0 verified expressions.
- Never causes constant motion.
- Event-driven only — no polling.
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("Brain.ReactionEngine")

# Priority levels (higher = more important, overrides cooldown)
PRIORITY = {
    "ERROR": 5,
    "WARNING": 4,
    "SUCCESS": 3,
    "CONFUSED": 3,
    "WORKING": 2,
    "SEARCHING": 2,
    "THINKING": 2,
    "SPEAKING": 2,
    "LISTENING": 1,
    "IDLE": 0,
    "SLEEPING": 0,
    "WAITING": 0,
}

# State → (expression, animation_hint)
# expression: VRM 1.0 verified preset name
# animation_hint: sent to plugin, but actual availability depends on runtime
STATE_REACTIONS: Dict[str, Dict[str, Optional[str]]] = {
    "THINKING":  {"expression": "relaxed",   "animation": None},
    "SEARCHING": {"expression": "surprised", "animation": None},
    "WORKING":   {"expression": "happy",     "animation": "tuttuki"},
    "SUCCESS":   {"expression": "happy",     "animation": "nadenade"},
    "ERROR":     {"expression": "sad",       "animation": None},
    "CONFUSED":  {"expression": "surprised", "animation": None},
    "WARNING":   {"expression": "angry",     "animation": None},
    "SPEAKING":  {"expression": "happy",     "animation": None},
    "LISTENING": {"expression": "neutral",   "animation": None},
    "IDLE":      {"expression": "neutral",   "animation": "idle"},
    "SLEEPING":  {"expression": "relaxed",   "animation": None},
    "WAITING":   {"expression": "relaxed",   "animation": None},
}


class ReactionEngine:
    """
    Deterministic reaction mapper with cooldown and priority gating.
    Receives CompanionEvents and translates them to bridge commands.
    """

    # Cooldown constants
    MIN_REACTION_INTERVAL = 2.0     # seconds between any reaction
    SAME_TYPE_INTERVAL = 5.0        # seconds between same-type reactions

    def __init__(self, bridge):
        """
        Args:
            bridge: DesktopMateBridge instance (or any object with
                    set_emotion(str) and play_animation(str) methods).
        """
        self._bridge = bridge
        self._last_reaction_time: float = 0.0
        self._last_reaction_type: Optional[str] = None
        self._last_reaction_type_time: Dict[str, float] = {}
        self._last_activity: Optional[str] = None

    def handle_event(self, event) -> bool:
        """
        Process a CompanionEvent. Returns True if a reaction was dispatched.
        """
        if event.event_type == "STATE_CHANGE":
            return self._handle_state_change(event.data)
        elif event.event_type == "OS_EVENT":
            return self._handle_os_event(event.data)
        # Other event types (speech, etc.) — no reaction needed
        return False

    def _handle_state_change(self, data: Dict[str, Any]) -> bool:
        """React to Brain state changes with cooldown gating."""
        if not isinstance(data, dict):
            return False

        activity = data.get("activity", "IDLE")

        # Skip if same as last activity (avoid redundant reactions)
        if activity == self._last_activity:
            return False

        reaction = STATE_REACTIONS.get(activity)
        if not reaction:
            return False

        # Check cooldowns
        now = time.time()
        priority = PRIORITY.get(activity, 0)

        # High priority (ERROR, WARNING) bypasses general cooldown
        if priority < 4:
            if now - self._last_reaction_time < self.MIN_REACTION_INTERVAL:
                return False

        # Same-type cooldown
        last_same = self._last_reaction_type_time.get(activity, 0.0)
        if now - last_same < self.SAME_TYPE_INTERVAL:
            return False

        # Dispatch reaction
        expression = reaction.get("expression")
        animation = reaction.get("animation")

        dispatched = False

        if expression:
            result = self._bridge.set_emotion(expression)
            if result.get("status") != "not_connected":
                dispatched = True

        if animation:
            result = self._bridge.play_animation(animation)
            if result.get("status") != "not_connected":
                dispatched = True

        if dispatched:
            self._last_reaction_time = now
            self._last_activity = activity
            self._last_reaction_type_time[activity] = now
            logger.debug(f"Reaction: {activity} → expression={expression}, animation={animation}")

        return dispatched

    def _handle_os_event(self, data: Dict[str, Any]) -> bool:
        """React to OS events (app launch, resource warning)."""
        if not isinstance(data, dict):
            return False

        event_type = data.get("type")
        now = time.time()

        # General cooldown check
        if now - self._last_reaction_time < self.MIN_REACTION_INTERVAL:
            return False

        if event_type == "APP_LAUNCHED":
            self._bridge.set_emotion("surprised")
            self._last_reaction_time = now
            return True
        elif event_type == "RESOURCE_WARNING":
            self._bridge.set_emotion("angry")
            self._last_reaction_time = now
            return True
        elif event_type == "VOICE_READY":
            audio_file = data.get("file")
            if audio_file:
                self._bridge.play_voice(audio_file)
                self._last_reaction_time = now
                return True

        return False
