import os
import re
import subprocess
from typing import Dict, Any, Optional


class WindowStateProvider:
    """
    Active Window State Perception Provider for Brain.
    Gathers structured metadata for active/focused desktop windows via X11 utilities (xdotool, xwininfo, wmctrl).
    Strictly passive and privacy-preserving (no keylogging, no password capture, no clipboard reading).
    """

    def __init__(self):
        self._last_metadata: Optional[Dict[str, Any]] = None

    def get_active_window_metadata(self) -> Dict[str, Any]:
        """
        Retrieves current active window ID, title, class, geometry, focus, and visibility.
        Returns standardized dictionary:
        {
          "window": {
            "id": str,
            "title": str,
            "class": str,
            "x": int,
            "y": int,
            "width": int,
            "height": int,
            "focused": bool,
            "visible": bool
          }
        }
        """
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            from tools.apps import default_app_tracker
            focused_app = default_app_tracker.get_focused_app() or "terminal"
            meta = {
                "window": {
                    "id": "0x1234567",
                    "title": f"Mock Window - {focused_app}",
                    "class": focused_app,
                    "x": 100,
                    "y": 50,
                    "width": 1200,
                    "height": 800,
                    "focused": True,
                    "visible": True
                }
            }
            self._last_metadata = meta
            return meta

        win_id = None
        win_title = "Unknown"
        win_class = "Unknown"
        x, y, width, height = 0, 0, 1920, 1080
        focused = True
        visible = True

        # 1. Obtain Active Window ID & Title via xdotool
        try:
            res_id = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=1)
            if res_id.returncode == 0 and res_id.stdout.strip():
                win_id_dec = res_id.stdout.strip()
                try:
                    win_id = hex(int(win_id_dec))
                except ValueError:
                    win_id = win_id_dec

            res_title = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=1)
            if res_title.returncode == 0 and res_title.stdout.strip():
                win_title = res_title.stdout.strip()

            res_class = subprocess.run(["xdotool", "getactivewindow", "getwindowclassname"], capture_output=True, text=True, timeout=1)
            if res_class.returncode == 0 and res_class.stdout.strip():
                win_class = res_class.stdout.strip()
        except Exception:
            pass

        # 2. Geometry via xwininfo if active window ID is present
        if win_id:
            try:
                res_info = subprocess.run(["xwininfo", "-id", str(win_id)], capture_output=True, text=True, timeout=1)
                if res_info.returncode == 0:
                    out = res_info.stdout
                    m_x = re.search(r"Absolute upper-left X:\s+(-?\d+)", out)
                    m_y = re.search(r"Absolute upper-left Y:\s+(-?\d+)", out)
                    m_w = re.search(r"Width:\s+(\d+)", out)
                    m_h = re.search(r"Height:\s+(\d+)", out)

                    if m_x:
                        x = int(m_x.group(1))
                    if m_y:
                        y = int(m_y.group(1))
                    if m_w:
                        width = int(m_w.group(1))
                    if m_h:
                        height = int(m_h.group(1))
            except Exception:
                pass

        # 3. Fallback to wmctrl if title or class is unknown
        if win_title == "Unknown" or win_class == "Unknown":
            try:
                res_wm = subprocess.run(["wmctrl", "-l", "-x"], capture_output=True, text=True, timeout=1)
                if res_wm.returncode == 0:
                    for line in res_wm.stdout.splitlines():
                        if win_id and win_id.lower() in line.lower():
                            parts = line.split(maxsplit=4)
                            if len(parts) >= 5:
                                win_class = parts[2]
                                win_title = parts[4]
                            break
            except Exception:
                pass

        # Fallback application resolution from title if class is still unknown
        if win_class == "Unknown" and win_title != "Unknown":
            from tools.apps import get_active_window_app_name
            app_norm = get_active_window_app_name()
            if app_norm:
                win_class = app_norm

        meta = {
            "window": {
                "id": win_id or "0x0",
                "title": win_title,
                "class": win_class,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "focused": focused,
                "visible": visible
            }
        }
        self._last_metadata = meta
        return meta

    def get_last_metadata(self) -> Optional[Dict[str, Any]]:
        return self._last_metadata


default_window_provider = WindowStateProvider()
