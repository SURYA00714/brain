"""
Brain Idle Behavior Controller.

Prevents the companion from appearing frozen during idle periods.
Schedules controlled idle animations at safe intervals.

Rules:
- Min 30s between idle animation triggers
- Max 3 idle animations per hour (cooling via token bucket)
- Never called if companion mode is SLEEPING or DISABLED
- Never runs during active Brain tasks
- Animations: only 'idle' (safe, known-available)
- Optional random look variation
"""

import logging
import random
import threading
import time
from typing import Optional

logger = logging.getLogger("Brain.IdleBehavior")


class IdleBehaviorController:
    """
    Drives subtle idle animations to prevent a frozen-looking companion.
    Runs on a background daemon thread.
    """

    MIN_IDLE_INTERVAL = 1800.0    # Minimum seconds between any idle action (30 mins)
    MAX_ACTIONS_PER_HOUR = 1      # Token bucket limit
    TOKEN_REFILL_INTERVAL = 3600  # seconds (1 hour per token)

    def __init__(self, bridge, mode_controller, state_manager):
        self._bridge = bridge
        self._mode = mode_controller
        self._state = state_manager
        self._last_idle_time: float = 0.0
        self._tokens: int = self.MAX_ACTIONS_PER_HOUR
        self._last_refill: float = time.time()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Look-at targets for idle variation
        self._look_targets = ["screen", "mouse", "none"]

    def start(self):
        """Start the idle behavior background thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._idle_loop, daemon=True, name="IdleBehavior"
        )
        self._thread.start()
        logger.info("IdleBehaviorController started")

    def stop(self):
        """Stop the idle behavior thread."""
        self._running = False
        self._stop_event.set()

    def _refill_tokens(self):
        """Refill one token per TOKEN_REFILL_INTERVAL seconds."""
        now = time.time()
        elapsed = now - self._last_refill
        refills = int(elapsed / self.TOKEN_REFILL_INTERVAL)
        if refills > 0:
            self._tokens = min(self.MAX_ACTIONS_PER_HOUR, self._tokens + refills)
            self._last_refill = now

    def _can_trigger(self) -> bool:
        """Check cooldown and token budget."""
        now = time.time()
        if now - self._last_idle_time < self.MIN_IDLE_INTERVAL:
            return False
        self._refill_tokens()
        return self._tokens > 0

    def _consume_token(self):
        self._tokens = max(0, self._tokens - 1)
        self._last_idle_time = time.time()

    def _get_companion_activity(self) -> str:
        """Read current companion activity without importing circular deps."""
        try:
            state = self._state.get_state()
            return state.get("activity", "IDLE")
        except Exception:
            return "IDLE"

    def _idle_loop(self):
        """Main idle behavior loop — checks every 10s, acts on criteria."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=10.0)
            if self._stop_event.is_set():
                break

            try:
                self._try_idle_action()
            except Exception as e:
                logger.debug(f"IdleBehavior loop error: {e}")

    def _try_idle_action(self):
        """Attempt a single idle action if conditions are met."""
        # Mode check
        if not self._mode.should_react(priority=0):
            return

        # Only act when companion is truly idle
        activity = self._get_companion_activity()
        if activity not in ("IDLE", "WAITING", "SLEEPING"):
            return

        # Cooldown + token check
        if not self._can_trigger():
            return

        # Bridge must be connected
        if not self._bridge.connected:
            return

        # Pick a random idle action
        choice = random.choice(["idle_anim", "look_change", "look_change"])
        self._consume_token()

        if choice == "idle_anim":
            result = self._bridge.play_animation("idle")
            logger.debug(f"Idle animation triggered: {result.get('status')}")
        else:
            # Change look-at target
            target = random.choice(self._look_targets)
            result = self._bridge.look_at(target)
            logger.debug(f"Idle look-at '{target}': {result.get('status')}")
