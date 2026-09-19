import os
import re
import shutil
import subprocess
from typing import Dict, Any, List, Optional

def _run_cmd_safe(args: list) -> Optional[str]:
    """Runs a controlled command without shell=True and returns stdout or None."""
    if not args or not isinstance(args, list):
        return None
    binary = args[0]
    if not shutil.which(binary):
        return None
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def list_windows() -> Dict[str, Any]:
    """Lists currently open GUI windows using X11 utilities (wmctrl/xdotool)."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        mock_windows = [
            {"id": "0x02000003", "desktop": 0, "class": "brave-browser.Brave-browser", "title": "New Tab - Brave"},
            {"id": "0x03400002", "desktop": 0, "class": "xfce4-terminal.Xfce4-terminal", "title": "Terminal - jai@linux"},
            {"id": "0x01800004", "desktop": 0, "class": "thunar.Thunar", "title": "Downloads - File Manager"},
            {"id": "0x04100001", "desktop": 0, "class": "galculator.Galculator", "title": "Calculator"}
        ]
        return {"success": True, "tool": "LIST_WINDOWS", "data": mock_windows, "count": len(mock_windows)}

    windows = []
    raw = _run_cmd_safe(["wmctrl", "-l", "-x"])
    if raw:
        for line in raw.splitlines():
            parts = line.split(maxsplit=4)
            if len(parts) >= 5:
                w_id = parts[0]
                d_num = parts[1]
                w_class = parts[2]
                w_title = parts[4]
                windows.append({
                    "id": w_id,
                    "desktop": int(d_num) if d_num.lstrip("-").isdigit() else 0,
                    "class": w_class,
                    "title": w_title
                })
        return {"success": True, "tool": "LIST_WINDOWS", "data": windows, "count": len(windows)}

    return {"success": False, "tool": "LIST_WINDOWS", "error": "Unable to list windows (wmctrl utility not available)."}


def _resolve_window_id(target: str) -> Optional[Dict[str, Any]]:
    """Resolves a window by hex ID, application name, or window title."""
    if not target or not isinstance(target, str):
        return None

    target_clean = target.strip().lower()

    # List windows
    res = list_windows()
    if not res.get("success"):
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            return {"id": "0x02000003", "title": target, "class": target}
        return None

    windows = res.get("data", [])

    # Match by exact ID
    for w in windows:
        if w["id"].lower() == target_clean:
            return w

    # Match by exact class or title
    for w in windows:
        if target_clean in w["class"].lower() or target_clean in w["title"].lower():
            return w

    # Match partial title / class
    for w in windows:
        if any(term in w["title"].lower() or term in w["class"].lower() for term in target_clean.split()):
            return w

    return None


def focus_window(target: str) -> Dict[str, Any]:
    """Focuses / brings a target window to foreground."""
    if not target:
        return {"success": False, "tool": "FOCUS_WINDOW", "error": "Target window specifier is required."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "FOCUS_WINDOW", "data": f"Window '{target}' focused."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "FOCUS_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    if _run_cmd_safe(["wmctrl", "-i", "-a", win_id]) is not None:
        return {"success": True, "tool": "FOCUS_WINDOW", "data": f"Focused window '{win['title']}' ({win_id})."}

    if _run_cmd_safe(["xdotool", "windowactivate", win_id]) is not None:
        return {"success": True, "tool": "FOCUS_WINDOW", "data": f"Focused window '{win['title']}' ({win_id}) via xdotool."}

    return {"success": False, "tool": "FOCUS_WINDOW", "error": f"Failed to focus window '{win['title']}'."}


def minimize_window(target: str) -> Dict[str, Any]:
    """Minimizes a target window."""
    if not target:
        return {"success": False, "tool": "MINIMIZE_WINDOW", "error": "Target window specifier is required."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "MINIMIZE_WINDOW", "data": f"Window '{target}' minimized."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "MINIMIZE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    if _run_cmd_safe(["xdotool", "windowminimize", win_id]) is not None:
        return {"success": True, "tool": "MINIMIZE_WINDOW", "data": f"Minimized window '{win['title']}' ({win_id})."}

    return {"success": False, "tool": "MINIMIZE_WINDOW", "error": f"Failed to minimize window '{win['title']}'."}


def maximize_window(target: str) -> Dict[str, Any]:
    """Maximizes a target window."""
    if not target:
        return {"success": False, "tool": "MAXIMIZE_WINDOW", "error": "Target window specifier is required."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "MAXIMIZE_WINDOW", "data": f"Window '{target}' maximized."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "MAXIMIZE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    if _run_cmd_safe(["wmctrl", "-i", "-r", win_id, "-b", "add,maximized_vert,maximized_horz"]) is not None:
        return {"success": True, "tool": "MAXIMIZE_WINDOW", "data": f"Maximized window '{win['title']}' ({win_id})."}

    return {"success": False, "tool": "MAXIMIZE_WINDOW", "error": f"Failed to maximize window '{win['title']}'."}


def restore_window(target: str) -> Dict[str, Any]:
    """Restores (un-maximizes) a target window."""
    if not target:
        return {"success": False, "tool": "RESTORE_WINDOW", "error": "Target window specifier is required."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "RESTORE_WINDOW", "data": f"Window '{target}' restored."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "RESTORE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    if _run_cmd_safe(["wmctrl", "-i", "-r", win_id, "-b", "remove,maximized_vert,maximized_horz"]) is not None:
        return {"success": True, "tool": "RESTORE_WINDOW", "data": f"Restored window '{win['title']}' ({win_id})."}

    return {"success": False, "tool": "RESTORE_WINDOW", "error": f"Failed to restore window '{win['title']}'."}


def close_window(target: str, confirmed: bool = False) -> Dict[str, Any]:
    """Closes a target window (Confirmation Gated)."""
    if not target:
        return {"success": False, "tool": "CLOSE_WINDOW", "error": "Target window specifier is required."}

    if not confirmed and os.environ.get("BRAIN_MOCK_GUI") != "1":
        from core.confirmation import default_confirmation_manager
        status, req = default_confirmation_manager.evaluate_action("CLOSE_WINDOW", {"target": target})
        if status == "REQUIRED":
            return {
                "success": False,
                "tool": "CLOSE_WINDOW",
                "confirmation_required": True,
                "error": f"Confirmation Required: Closing window '{target}' requires explicit user confirmation."
            }

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "CLOSE_WINDOW", "data": f"Window '{target}' closed."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "CLOSE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    if _run_cmd_safe(["wmctrl", "-i", "-c", win_id]) is not None:
        return {"success": True, "tool": "CLOSE_WINDOW", "data": f"Closed window '{win['title']}' ({win_id})."}

    if _run_cmd_safe(["xdotool", "windowclose", win_id]) is not None:
        return {"success": True, "tool": "CLOSE_WINDOW", "data": f"Closed window '{win['title']}' ({win_id}) via xdotool."}

    return {"success": False, "tool": "CLOSE_WINDOW", "error": f"Failed to close window '{win['title']}'."}


def move_window(target: str, x: int, y: int) -> Dict[str, Any]:
    """Moves a window to specified screen coordinates (0..7680, 0..4320)."""
    if not target:
        return {"success": False, "tool": "MOVE_WINDOW", "error": "Target window specifier is required."}

    if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x <= 7680) or not (0 <= y <= 4320):
        return {"success": False, "tool": "MOVE_WINDOW", "error": f"Invalid coordinates ({x}, {y}). Coordinates must be non-negative integers within screen bounds."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "MOVE_WINDOW", "data": f"Window '{target}' moved to ({x}, {y})."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "MOVE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    geo_arg = f"0,{x},{y},-1,-1"
    if _run_cmd_safe(["wmctrl", "-i", "-r", win_id, "-e", geo_arg]) is not None:
        return {"success": True, "tool": "MOVE_WINDOW", "data": f"Moved window '{win['title']}' ({win_id}) to ({x}, {y})."}

    return {"success": False, "tool": "MOVE_WINDOW", "error": f"Failed to move window '{win['title']}'."}


def resize_window(target: str, width: int, height: int) -> Dict[str, Any]:
    """Resizes a window to specified dimensions (100..7680, 100..4320)."""
    if not target:
        return {"success": False, "tool": "RESIZE_WINDOW", "error": "Target window specifier is required."}

    if not isinstance(width, int) or not isinstance(height, int) or not (100 <= width <= 7680) or not (100 <= height <= 4320):
        return {"success": False, "tool": "RESIZE_WINDOW", "error": f"Invalid dimensions ({width}x{height}). Dimensions must be integers between 100 and 7680/4320."}

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "RESIZE_WINDOW", "data": f"Window '{target}' resized to {width}x{height}."}

    win = _resolve_window_id(target)
    if not win:
        return {"success": False, "tool": "RESIZE_WINDOW", "error": f"No open window matching '{target}' found."}

    win_id = win["id"]
    geo_arg = f"0,-1,-1,{width},{height}"
    if _run_cmd_safe(["wmctrl", "-i", "-r", win_id, "-e", geo_arg]) is not None:
        return {"success": True, "tool": "RESIZE_WINDOW", "data": f"Resized window '{win['title']}' ({win_id}) to {width}x{height}."}

    return {"success": False, "tool": "RESIZE_WINDOW", "error": f"Failed to resize window '{win['title']}'."}
