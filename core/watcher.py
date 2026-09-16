"""
Brain Low-Cost Continuous Event Watcher (Phase 19 Companion Evolution).
Maintains ambient computer awareness with zero continuous LLM inference.
Uses lightweight OS polling (process changes, window focus, storage thresholds)
and wakes Brain only when actionable events occur.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from tools.apps import get_system_state_summary, default_app_tracker
from core.world_state import default_world_state


class AmbientWatcher:
    """Non-blocking, minimal-CPU ambient event monitor."""

    def __init__(self, poll_interval_sec: float = 3.0):
        self.poll_interval = poll_interval_sec
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._last_active_app: Optional[str] = None
        self._last_running_apps: List[str] = []
        self._event_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def add_callback(self, cb: Callable[[Dict[str, Any]], None]):
        self._event_callbacks.append(cb)

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def poll_once(self) -> List[Dict[str, Any]]:
        """Single cheap state evaluation (0 LLM calls, <10ms)."""
        events = []
        summary = get_system_state_summary()
        current_active = summary.get("active_app")
        current_running = summary.get("running_apps", [])

        # 1. Detect active window switch
        if current_active != self._last_active_app and self._last_active_app is not None:
            events.append({
                "type": "WINDOW_FOCUS_CHANGED",
                "previous_app": self._last_active_app,
                "current_app": current_active,
                "title": summary.get("active_window_title")
            })
        self._last_active_app = current_active

        # 2. Detect app launches / exits
        launched = set(current_running) - set(self._last_running_apps)
        exited = set(self._last_running_apps) - set(current_running)

        for app in launched:
            events.append({"type": "APP_LAUNCHED", "app_name": app})
        for app in exited:
            events.append({"type": "APP_EXITED", "app_name": app})

        self._last_running_apps = current_running

        # 3. Check memory & disk pressure thresholds
        mem = summary.get("memory", {})
        avail_mb = mem.get("available_mb", 9999)
        if avail_mb < 300:
            events.append({"type": "RESOURCE_WARNING", "resource": "RAM", "available_mb": avail_mb})

        disk = summary.get("disk", {})
        pct_used = disk.get("percent_used", 0)
        if pct_used > 95:
            events.append({"type": "RESOURCE_WARNING", "resource": "DISK", "percent_used": pct_used})

        return events

    def _watch_loop(self):
        while self.is_running:
            try:
                events = self.poll_once()
                for ev in events:
                    # Update WorldState without LLM
                    if ev["type"] == "WINDOW_FOCUS_CHANGED":
                        default_world_state.active_app = ev.get("current_app")
                    for cb in self._event_callbacks:
                        try:
                            cb(ev)
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(self.poll_interval)


default_watcher = AmbientWatcher()
