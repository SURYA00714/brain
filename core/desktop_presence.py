"""
Desktop Presence Manager for Desktop Mate under Linux / Proton 9.0 (X11).

Responsibilities:
- Detect whether Desktop Mate process is running.
- Locate Desktop Mate X11 window using xwininfo / wmctrl.
- Ensure Desktop Mate is launched using the verified Proton runtime (prevents duplicate launches).
- Apply X11 window hints (_NET_WM_STATE_ABOVE, _NET_WM_STATE_STICKY) so the companion stays on screen.
- Monitor lifecycle and perform bounded recovery (max 3 retries).
- Zero focus stealing during normal companion operations.
"""

import os
import subprocess
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("Brain.DesktopPresence")

DESKTOPMATE_DIR = "/home/jai/Downloads/Brain/desktopmate/Desktop Mate"
DESKTOPMATE_EXE = os.path.join(DESKTOPMATE_DIR, "DesktopMate.exe")
PROTON_BIN = "/home/jai/.local/share/Steam/steamapps/common/Proton 9.0 (Beta)/proton"
COMPAT_DATA_PATH = "/home/jai/.local/share/Steam/steamapps/compatdata/3301060"
STEAM_CLIENT_PATH = "/home/jai/.local/share/Steam"
STEAM_APP_ID = "3301060"


class DesktopPresenceManager:
    """
    Manages process detection, launching, X11 window presence,
    and bounded recovery for Desktop Mate.
    """

    def __init__(self, max_recovery_attempts: int = 3):
        self.max_recovery_attempts = max_recovery_attempts
        self.recovery_count = 0
        self._last_launch_time = 0.0

    def is_process_running(self) -> bool:
        """Check if DesktopMate.exe process is currently active."""
        try:
            res = subprocess.run(
                ["pgrep", "-f", "DesktopMate.exe"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception as e:
            logger.warning(f"Error checking DesktopMate process: {e}")
            return False

    def get_window_id(self) -> Optional[str]:
        """Locate X11 window ID for Desktop Mate."""
        try:
            res = subprocess.run(
                ["xwininfo", "-root", "-tree"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "DesktopMate" in line or "steam_app_3301060" in line:
                        parts = line.strip().split()
                        if parts and parts[0].startswith("0x"):
                            return parts[0]
        except Exception as e:
            logger.debug(f"Error finding Desktop Mate window ID: {e}")
        return None

    def ensure_running(self) -> Dict[str, Any]:
        """
        Ensure Desktop Mate is running.
        Launches Desktop Mate via Proton only if not already running.
        Prevents duplicate process creation.
        """
        if self.is_process_running():
            win_id = self.get_window_id()
            return {
                "success": True,
                "status": "already_running",
                "running": True,
                "window_id": win_id,
            }

        if not os.path.isfile(DESKTOPMATE_EXE):
            return {
                "success": False,
                "status": "missing_executable",
                "error": f"DesktopMate.exe not found at {DESKTOPMATE_EXE}",
            }

        if not os.path.isfile(PROTON_BIN):
            return {
                "success": False,
                "status": "missing_proton",
                "error": f"Proton binary not found at {PROTON_BIN}",
            }

        # Prevent rapid re-launching (at least 5s between launches)
        now = time.time()
        if now - self._last_launch_time < 5.0:
            return {
                "success": False,
                "status": "cooldown",
                "error": "Launch cooldown active to prevent process thrashing",
            }

        self._last_launch_time = now
        env = os.environ.copy()
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = STEAM_CLIENT_PATH
        env["STEAM_COMPAT_DATA_PATH"] = COMPAT_DATA_PATH
        env["SteamAppId"] = STEAM_APP_ID
        env["WINEDLLOVERRIDES"] = "winhttp=n,b"

        logger.info("Launching Desktop Mate under Proton 9.0...")
        try:
            subprocess.Popen(
                [PROTON_BIN, "run", DESKTOPMATE_EXE],
                cwd=DESKTOPMATE_DIR,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            return {
                "success": False,
                "status": "launch_failed",
                "error": f"Failed to spawn Proton process: {e}",
            }

        # Wait up to 12 seconds for startup
        for _ in range(12):
            time.sleep(1.0)
            if self.is_process_running():
                win_id = self.get_window_id()
                self.apply_desktop_presence(win_id)
                return {
                    "success": True,
                    "status": "launched",
                    "running": True,
                    "window_id": win_id,
                }

        return {
            "success": False,
            "status": "launch_timeout",
            "error": "Desktop Mate process started but did not become ready within timeout",
        }

    def apply_desktop_presence(self, window_id: Optional[str] = None) -> bool:
        """
        Apply X11 window hints (always-on-top, sticky across all workspaces)
        using wmctrl without stealing keyboard focus.
        """
        win_id = window_id or self.get_window_id()
        if not win_id:
            logger.debug("No window ID available for apply_desktop_presence")
            return False

        try:
            # Set window hints: above (always-on-top) and sticky (all desktops)
            res = subprocess.run(
                ["wmctrl", "-i", "-r", win_id, "-b", "add,above,sticky"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"wmctrl failed to set window properties: {e}")
            return False

    def recover(self) -> Dict[str, Any]:
        """
        Bounded recovery when Desktop Mate disappears.
        Max max_recovery_attempts allowed.
        """
        if self.recovery_count >= self.max_recovery_attempts:
            logger.error(
                f"Maximum recovery attempts ({self.max_recovery_attempts}) reached. Stopping recovery."
            )
            return {
                "success": False,
                "status": "recovery_exhausted",
                "error": f"Exceeded maximum recovery attempts ({self.max_recovery_attempts})",
            }

        self.recovery_count += 1
        logger.info(
            f"Attempting Desktop Mate recovery ({self.recovery_count}/{self.max_recovery_attempts})..."
        )
        res = self.ensure_running()
        if res.get("success"):
            self.recovery_count = 0  # Reset counter on successful recovery
        return res
