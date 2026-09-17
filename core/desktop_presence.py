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
                ["ps", "-eo", "pid=,state=,comm=,args="],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.strip().split(None, 3)
                    if len(parts) == 4:
                        state, comm, args = parts[1], parts[2], parts[3]
                        if "python" in comm or "grep" in comm or "python" in args:
                            continue
                        if state.startswith("Z"):
                            continue
                        if "DesktopMate.exe" in comm or "DesktopMate.exe" in args:
                            return True
            return False
        except Exception as e:
            logger.warning(f"Error checking DesktopMate process: {e}")
            return False

    def get_window_id(self) -> Optional[str]:
        """Locate X11 window ID for Desktop Mate."""
        if not self.is_process_running():
            return None
        try:
            res = subprocess.run(
                ["xwininfo", "-root", "-tree"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if '"DesktopMate"' in line or '("DesktopMate' in line or 'steam_app_3301060' in line:
                        parts = line.strip().split()
                        if parts and parts[0].startswith("0x"):
                            candidate = parts[0]
                            # Verify candidate window is live and valid in X11
                            check = subprocess.run(
                                ["xwininfo", "-id", candidate],
                                capture_output=True,
                                text=True,
                                timeout=2,
                            )
                            if (
                                check.returncode == 0
                                and "X Error" not in check.stderr
                                and "error:" not in check.stderr.lower()
                                and "(has no name)" not in check.stdout
                                and ("DesktopMate" in check.stdout or "steam_app" in check.stdout)
                            ):
                                return candidate
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
        env["STEAM_COMPAT_APP_ID"] = STEAM_APP_ID
        env["SteamAppId"] = STEAM_APP_ID
        env["SteamGameId"] = STEAM_APP_ID
        env["WINEDLLOVERRIDES"] = "winhttp=n,b"
        env["WINEDEBUG"] = "-all"

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

        # Attempt true transparency using xprop (will only work if Unity compositor supports it)
        # We also implement tight window sizing as the reliable fallback
        try:
            # 1. Window hints
            res = subprocess.run(
                ["wmctrl", "-i", "-r", win_id, "-b", "add,above,sticky,skip_taskbar,skip_pager"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            
            # 2. Borderless
            subprocess.run(
                ["xprop", "-id", win_id, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "0x2, 0x0, 0x0, 0x0, 0x0"],
                capture_output=True,
                timeout=3,
            )

            # 3. Try to get primary screen resolution for smart positioning
            screen_w, screen_h = 1920, 1080
            xrandr_res = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=2)
            if xrandr_res.returncode == 0:
                for line in xrandr_res.stdout.splitlines():
                    if "*" in line or ("connected primary" in line):
                        parts = line.strip().split()
                        for p in parts:
                            if "x" in p and p[0].isdigit():
                                dims = p.split("+")[0].split("x")
                                if len(dims) == 2 and dims[0].isdigit() and dims[1].isdigit():
                                    screen_w = int(dims[0])
                                    screen_h = int(dims[1])
                                    break
                        if screen_w != 1920:
                            break

            # 4. COMPACT mode sizing
            # Tight fit around the character. Now that background is transparent,
            # this acts as the interaction bounding box in the bottom right corner.
            win_w = 400
            win_h = 550
            
            # Smart positioning: Bottom right, safe margin
            pos_x = max(0, screen_w - win_w - 40)
            pos_y = max(0, screen_h - win_h - 60)

            # 5. Apply geometry
            subprocess.run(
                ["wmctrl", "-i", "-r", win_id, "-e", f"0,{pos_x},{pos_y},{win_w},{win_h}"],
                capture_output=True,
                timeout=3,
            )

            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Failed to set window properties: {e}")
            return False

    def get_memory_usage_mb(self) -> float:
        """Get total RSS memory usage of DesktopMate process(es) in megabytes."""
        try:
            res = subprocess.run(
                ["ps", "-eo", "rss=,comm=,args="],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout.strip():
                total_kb = 0
                for line in res.stdout.splitlines():
                    parts = line.strip().split(None, 2)
                    if len(parts) == 3:
                        rss_str, comm, args = parts[0], parts[1], parts[2]
                        if "python" in comm or "grep" in comm or "python" in args:
                            continue
                        if ("DesktopMate.exe" in comm or "DesktopMate.exe" in args) and rss_str.isdigit():
                            total_kb += int(rss_str)
                return round(total_kb / 1024.0, 2)
        except Exception as e:
            logger.debug(f"Error reading DesktopMate memory usage: {e}")
        return 0.0

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

    def get_detailed_status(self, bridge_connected: bool = False, runtime_ready: bool = False, character_ready: bool = False) -> Dict[str, Any]:
        """
        Return structured multi-state presence status.
        Explicitly distinguishes process_running, window_present, bridge_connected,
        runtime_ready, and character_ready.
        """
        proc_running = self.is_process_running()
        win_id = self.get_window_id() if proc_running else None
        win_present = win_id is not None
        mem_mb = self.get_memory_usage_mb() if proc_running else 0.0

        is_runtime_ready = proc_running and win_present and runtime_ready
        is_char_ready = is_runtime_ready and character_ready

        return {
            "process_running": proc_running,
            "window_present": win_present,
            "bridge_connected": bridge_connected,
            "runtime_ready": is_runtime_ready,
            "character_ready": is_char_ready,
            "window_id": win_id,
            "rss_memory_mb": mem_mb,
        }

