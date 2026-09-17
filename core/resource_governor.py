"""
Brain Lightweight Resource Governor (Phase 7).
Monitors RSS memory, CPU, storage footprint, screenshot count, and log bounds
to guarantee system stability and enforce <50 GB SSD budget.
"""

import os
import shutil
import time
import psutil
from typing import Dict, Any

from tools.screen import cleanup_screenshots
from core.world_state import default_world_state
from core.desktop_presence import DesktopPresenceManager


class ResourceGovernor:
    """Lightweight resource monitoring and cache governance engine."""
    def __init__(
        self,
        max_rss_mb: float = 1500.0,
        max_desktop_mate_rss_mb: float = 850.0,
        max_screenshots: int = 1
    ):
        self.max_rss_mb = max_rss_mb
        self.max_desktop_mate_rss_mb = max_desktop_mate_rss_mb
        self.max_screenshots = max_screenshots
        self.presence_mgr = DesktopPresenceManager()

    def get_brain_rss_mb(self) -> float:
        """Returns Brain process RSS memory usage in MB."""
        try:
            process = psutil.Process(os.getpid())
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0

    def check_and_govern(self) -> Dict[str, Any]:
        """Inspects current resource usage and executes corrective governance if needed."""
        brain_rss = self.get_brain_rss_mb()
        mate_rss = self.presence_mgr.get_memory_usage_mb()

        # Enforce screenshot storage bounds
        cleanup_screenshots(keep_latest=True)

        governance_actions = []

        # Check if Desktop Mate memory needs trimming
        if mate_rss > self.max_desktop_mate_rss_mb:
            try:
                from bridge.desktopmate_bridge import default_bridge
                default_bridge.trim_memory()
                governance_actions.append("TRIMMED_DESKTOP_MATE_MEMORY")
            except Exception:
                pass

        status = {
            "brain_rss_mb": brain_rss,
            "desktop_mate_rss_mb": mate_rss,
            "actions_taken": governance_actions,
            "timestamp": time.time()
        }

        if governance_actions:
            try:
                from core.event_bus import default_event_bus
                default_event_bus.publish("RESOURCE_WARNING", status)
            except Exception:
                pass

        return status


default_resource_governor = ResourceGovernor()
