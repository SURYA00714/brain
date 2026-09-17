"""
Brain Companion Mode Controller.

Manages the four companion operating modes:
  ACTIVE   - full Brain reactions, all events dispatched
  PASSIVE  - minimal reactions, only high-priority events
  SLEEPING - companion quiet, minimal CPU usage
  DISABLED - Desktop Mate integration off, Brain still runs

Mode transitions are deterministic. No magic behavior.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger("Brain.CompanionMode")


class CompanionMode:
    ACTIVE = "ACTIVE"
    PASSIVE = "PASSIVE"
    SLEEPING = "SLEEPING"
    DISABLED = "DISABLED"

    _VALID = {ACTIVE, PASSIVE, SLEEPING, DISABLED}


class CompanionModeController:
    """Thread-safe companion mode manager."""

    def __init__(self, initial_mode: str = CompanionMode.ACTIVE):
        self._mode = initial_mode if initial_mode in CompanionMode._VALID else CompanionMode.ACTIVE
        self._lock = threading.Lock()

    def get_mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> dict:
        if mode not in CompanionMode._VALID:
            return {"success": False, "error": f"Invalid mode '{mode}'. Valid: {sorted(CompanionMode._VALID)}"}
        with self._lock:
            old = self._mode
            self._mode = mode
        logger.info(f"Companion mode: {old} → {mode}")
        return {"success": True, "previous": old, "mode": mode}

    def is_active(self) -> bool:
        return self.get_mode() == CompanionMode.ACTIVE

    def is_passive(self) -> bool:
        return self.get_mode() == CompanionMode.PASSIVE

    def is_sleeping(self) -> bool:
        return self.get_mode() == CompanionMode.SLEEPING

    def is_disabled(self) -> bool:
        return self.get_mode() == CompanionMode.DISABLED

    def should_react(self, priority: int = 0) -> bool:
        """
        Returns True if the current mode allows reacting.
        priority: 0=low, 3=medium, 5=high (ERROR/WARNING always react in ACTIVE/PASSIVE)
        """
        mode = self.get_mode()
        if mode == CompanionMode.DISABLED:
            return False
        if mode == CompanionMode.SLEEPING:
            return False
        if mode == CompanionMode.PASSIVE:
            return priority >= 3  # Only react to SUCCESS, ERROR, WARNING
        return True  # ACTIVE: react to everything

    def to_dict(self) -> dict:
        return {"mode": self.get_mode()}


# Global singleton
default_companion_mode = CompanionModeController()
