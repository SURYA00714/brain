"""
Brain Look-At Controller.

Manages companion gaze direction: MOUSE, SCREEN, ACTIVE_WINDOW, NONE.

Rules:
- Updates throttled to at most once per 5 seconds
- Only dispatched when bridge is connected
- NONE sends look_at("none") to reset gaze
- Uses existing bridge.look_at() method
- Does NOT use webcam or keylogging
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("Brain.LookAt")

VALID_TARGETS = {"mouse", "screen", "active_window", "none"}
UPDATE_INTERVAL = 5.0  # seconds


class LookAtController:
    """
    Sends throttled look-at commands to the Desktop Mate character.
    """

    def __init__(self, bridge, mode_controller):
        self._bridge = bridge
        self._mode = mode_controller
        self._current_target: str = "none"
        self._last_update: float = 0.0
        self._lock = threading.Lock()

    def set_target(self, target: str) -> dict:
        """
        Request a new look-at target.
        Returns a status dict.
        """
        t = target.lower().strip()
        if t not in VALID_TARGETS:
            return {
                "success": False,
                "error": f"Invalid look-at target '{target}'. Valid: {sorted(VALID_TARGETS)}",
            }

        if not self._mode.should_react(priority=0):
            return {"success": False, "status": "mode_suppressed"}

        if not self._bridge.connected:
            return {"success": False, "status": "not_connected"}

        with self._lock:
            now = time.time()
            # Throttle: skip if same target and within interval
            if t == self._current_target and (now - self._last_update) < UPDATE_INTERVAL:
                return {"success": True, "status": "throttled", "target": t}

            # If different target, still enforce minimum interval
            if (now - self._last_update) < UPDATE_INTERVAL:
                return {"success": True, "status": "throttled", "target": t}

            self._current_target = t
            self._last_update = now

        result = self._bridge.look_at(t)
        logger.debug(f"look_at('{t}'): {result.get('status')}")
        return {"success": True, "status": result.get("status", "executed_unverified"), "target": t}

    def get_target(self) -> str:
        with self._lock:
            return self._current_target

    def reset(self) -> dict:
        """Reset gaze to none."""
        return self.set_target("none")
