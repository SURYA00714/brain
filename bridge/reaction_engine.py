"""
Brain Reaction Engine — Deterministic, cooldown-gated state→animation/expression mapper.

Maps Brain CompanionState events to Desktop Mate actions through the bridge.

RULES:
- Cooldown: min 2s between any reaction, 5s between same-type reactions.
- Priority: ERROR > SUCCESS > WORKING > THINKING > IDLE.
- Only uses VRM 1.0 verified expressions.
- Never causes constant motion.
- Event-driven only — no polling.
- Respects CompanionMode (ACTIVE/PASSIVE/SLEEPING/DISABLED).
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
    "ACTION_FAILED": 5,
    "ACTION_VERIFIED": 3,
    "ACTION_STARTED": 2,
    "WORKING": 2,
    "SEARCHING": 2,
    "THINKING": 2,
    "SPEAKING": 2,
    "SPEECH_STARTED": 2,
    "SPEECH_STOPPED": 1,
    "OBSERVING": 1,
    "USER_MESSAGE": 1,
    "USER_INTERRUPTED": 4,
    "LISTENING": 1,
    "IDLE": 0,
    "SLEEPING": 0,
    "WAITING": 0,
}

# State/event → (expression, animation_hint, look_at)
STATE_REACTIONS: Dict[str, Dict[str, Optional[str]]] = {
    "THINKING":        {"expression": "relaxed",   "animation": None,       "look_at": "screen"},
    "SEARCHING":       {"expression": "surprised", "animation": None,       "look_at": "screen"},
    "OBSERVING":       {"expression": "surprised", "animation": None,       "look_at": "screen"},
    "WORKING":         {"expression": "happy",     "animation": "tuttuki",  "look_at": "screen"},
    "ACTION_STARTED":  {"expression": "relaxed",   "animation": None,       "look_at": "screen"},
    "ACTION_VERIFIED": {"expression": "happy",     "animation": "nadenade", "look_at": "screen"},
    "ACTION_FAILED":   {"expression": "sad",       "animation": None,       "look_at": "none"},
    "SUCCESS":         {"expression": "happy",     "animation": "nadenade", "look_at": "mouse"},
    "ERROR":           {"expression": "sad",       "animation": None,       "look_at": "none"},
    "CONFUSED":        {"expression": "surprised", "animation": None,       "look_at": "none"},
    "WARNING":         {"expression": "angry",     "animation": None,       "look_at": "screen"},
    "USER_MESSAGE":    {"expression": "happy",     "animation": None,       "look_at": "mouse"},
    "USER_INTERRUPTED":{"expression": "surprised", "animation": None,       "look_at": "screen"},
    "SPEAKING":        {"expression": "happy",     "animation": None,       "look_at": "mouse"},
    "SPEECH_STARTED":  {"expression": "happy",     "animation": None,       "look_at": "mouse"},
    "SPEECH_STOPPED":  {"expression": "neutral",   "animation": None,       "look_at": "none"},
    "LISTENING":       {"expression": "neutral",   "animation": None,       "look_at": "screen"},
    "IDLE":            {"expression": "neutral",   "animation": "idle",     "look_at": "none"},
    "SLEEPING":        {"expression": "relaxed",   "animation": None,       "look_at": "none"},
    "WAITING":         {"expression": "relaxed",   "animation": None,       "look_at": "none"},
}


class ReactionEngine:
    """
    Deterministic reaction mapper with cooldown, priority, and mode gating.
    Receives CompanionEvents and translates them to bridge commands.
    """

    # Cooldown constants
    MIN_REACTION_INTERVAL = 2.0     # seconds between any reaction
    SAME_TYPE_INTERVAL = 5.0        # seconds between same-type reactions

    def __init__(self, bridge, mode_controller=None):
        """
        Args:
            bridge: DesktopMateBridge instance.
            mode_controller: Optional CompanionModeController.
        """
        self._bridge = bridge
        self._mode = mode_controller
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
        elif event.event_type in ("BRAIN_EVENT", "COMPANION_EVENT"):
            return self._handle_brain_event(event.data)
        return False

    def _check_mode(self, priority: int) -> bool:
        """Returns True if mode allows reacting at this priority."""
        if self._mode is None:
            return True
        return self._mode.should_react(priority)

    def _handle_state_change(self, data: Dict[str, Any]) -> bool:
        """React to Brain state changes with cooldown gating."""
        if not isinstance(data, dict):
            return False

        activity = data.get("activity", "IDLE")
        priority = PRIORITY.get(activity, 0)

        # Mode check
        if not self._check_mode(priority):
            return False

        # Skip if same as last activity
        if activity == self._last_activity:
            return False

        reaction = STATE_REACTIONS.get(activity)
        if not reaction:
            return False

        return self._dispatch_reaction(activity, priority, reaction)

    def _handle_brain_event(self, data: Dict[str, Any]) -> bool:
        """React to explicit Brain events (ACTION_STARTED, ACTION_VERIFIED, etc.)."""
        if not isinstance(data, dict):
            return False

        event_name = data.get("event", "")
        priority = PRIORITY.get(event_name, 0)

        if not self._check_mode(priority):
            return False

        reaction = STATE_REACTIONS.get(event_name)
        if not reaction:
            return False

        return self._dispatch_reaction(event_name, priority, reaction)

    def _dispatch_reaction(self, key: str, priority: int, reaction: Dict[str, Optional[str]]) -> bool:
        """Apply cooldown checks then dispatch expression+animation."""
        now = time.time()

        # High priority (ERROR, WARNING, USER_INTERRUPTED, ACTION_FAILED) bypasses general cooldown
        if priority < 4:
            if now - self._last_reaction_time < self.MIN_REACTION_INTERVAL:
                return False

        # Same-type cooldown
        last_same = self._last_reaction_type_time.get(key, 0.0)
        if now - last_same < self.SAME_TYPE_INTERVAL:
            return False

        expression = reaction.get("expression")
        animation = reaction.get("animation")
        look_at = reaction.get("look_at")
        dispatched = False

        if expression:
            result = self._bridge.set_emotion(expression)
            if result.get("status") != "not_connected":
                dispatched = True

        if animation:
            # Small delay for natural transition (state -> emotion -> animation)
            time.sleep(0.1)
            result = self._bridge.play_animation(animation)
            if result.get("status") != "not_connected":
                dispatched = True

        if look_at:
            result = self._bridge.look_at_target(look_at)
            if result.get("status") != "not_connected":
                dispatched = True

        if dispatched:
            self._last_reaction_time = now
            self._last_activity = key
            self._last_reaction_type_time[key] = now
            logger.debug(f"Reaction: {key} → expression={expression}, animation={animation}, look_at={look_at}")

        return dispatched

    def _handle_os_event(self, data: Dict[str, Any]) -> bool:
        """React to OS events (app launch, resource warning)."""
        if not isinstance(data, dict):
            return False

        event_type = data.get("type")
        now = time.time()
        priority = 2  # default OS event priority

        if not self._check_mode(priority):
            return False

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
