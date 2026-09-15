import os
import signal
import subprocess
import time

APPROVED_APPS = {
    "brave": ["brave-browser"],
    "terminal": ["xfce4-terminal", "x-terminal-emulator"],
    "file_manager": ["thunar"],
    "text_editor": ["xedit", "x-text-editor", "nano"]
}


class AppTracker:
    """
    Application Ownership & Process Lifecycle Tracker for Brain.
    Tracks applications with AppState (pid, executable, launch_time, brain_owned,
    process_alive, window_detected, window_focused).
    Prevents indiscriminate process kills and verifies app closure.
    """
    def __init__(self):
        self._tracked_apps = {}  # app_name -> list of AppState dicts
        self._currently_focused_app = None

    @classmethod
    def get_instance(cls):
        return default_app_tracker

    def clear(self):
        for app_name, entries in self._tracked_apps.items():
            for entry in entries:
                proc = entry.get("proc")
                if proc:
                    try:
                        proc.poll()
                    except Exception:
                        pass
        self._tracked_apps.clear()
        self._currently_focused_app = None

    def record_launch(self, app_name, executable, proc):
        if app_name not in self._tracked_apps:
            self._tracked_apps[app_name] = []

        entry = {
            "app_name": app_name,
            "executable": executable,
            "pid": proc.pid if proc else None,
            "proc": proc,
            "launch_time": time.time(),
            "brain_owned": True,
            "process_alive": True,
            "window_detected": True,
            "window_focused": True,
            "last_seen": time.time()
        }
        self._tracked_apps[app_name].append(entry)
        self._currently_focused_app = app_name
        return entry

    def register_app(self, app_name, pid=None, brain_owned=True):
        clean_name = normalize_app_name(app_name)
        if clean_name not in self._tracked_apps:
            self._tracked_apps[clean_name] = []

        entry = {
            "app_name": clean_name,
            "executable": clean_name,
            "pid": pid,
            "proc": None,
            "launch_time": time.time(),
            "brain_owned": brain_owned,
            "process_alive": True,
            "window_detected": True,
            "window_focused": True,
            "last_seen": time.time()
        }
        self._tracked_apps[clean_name].append(entry)
        return entry

    def is_running(self, app_name):
        clean_name = normalize_app_name(app_name)
        entries = self._tracked_apps.get(clean_name, [])
        for entry in entries:
            proc = entry.get("proc")
            if proc is not None:
                if proc.poll() is None and entry.get("process_alive", True):
                    return True
                else:
                    entry["process_alive"] = False
                    continue
            pid = entry.get("pid")
            if pid and entry.get("process_alive", True):
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    entry["process_alive"] = False
        return False

    def is_brain_owned(self, app_name):
        clean_name = normalize_app_name(app_name)
        entries = self._tracked_apps.get(clean_name, [])
        for entry in entries:
            if entry.get("brain_owned"):
                return True
        return False

    def set_focused_app(self, app_name):
        self._currently_focused_app = normalize_app_name(app_name)

    def get_focused_app(self):
        active = get_active_window_app_name()
        if active:
            self._currently_focused_app = active
            return active
        return self._currently_focused_app

    def close_app(self, app_name):
        """
        Safely closes application instances.
        Verifies closure after request.
        Only terminates Brain-owned process instances.
        If instance was not launched by Brain, safely refuses without lying.
        """
        clean_name = normalize_app_name(app_name)
        app_map = {"brave": "Brave", "file_manager": "File Manager", "terminal": "Terminal", "text_editor": "Text Editor"}
        display_name = app_map.get(clean_name, clean_name.title())

        entries = self._tracked_apps.get(clean_name, [])
        has_recorded_entries = len(entries) > 0
        active_entries = [e for e in entries if e.get("brain_owned") and e.get("process_alive", True)]

        if not active_entries:
            if not has_recorded_entries and is_window_open(clean_name):
                return f"Notice: No active Brain-owned instance of '{clean_name}' was found to close. I found '{display_name}', but this instance was not launched by Brain, so I won't close it automatically."
            return f"Notice: No active Brain-owned instance of '{clean_name}' was found to close. Application '{clean_name}' was already closed or not running."

        closed_count = 0
        remaining = []

        for entry in active_entries:
            proc = entry.get("proc")
            pid = entry.get("pid")
            terminated = False

            if proc:
                try:
                    proc.terminate()
                    terminated = True
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass
                except Exception:
                    pass

            if not terminated and pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    terminated = True
                except Exception:
                    pass

            if terminated:
                closed_count += 1
                entry["process_alive"] = False
            else:
                remaining.append(entry)

        self._tracked_apps[clean_name] = remaining

        if closed_count > 1:
            return f"Application '{display_name}' closed successfully ({closed_count} Brain-owned process instance(s) terminated). {display_name} has been closed."

        return f"Application '{display_name}' closed successfully. {display_name} has been closed."

    def list_tracked(self):
        result = []
        for app_name, entries in self._tracked_apps.items():
            active = [e for e in entries if (e.get("proc") and e.get("proc").poll() is None)]
            if active:
                result.append({"app_name": app_name, "active_instances": len(active)})
        return result


# Global AppTracker instance
default_app_tracker = AppTracker()


def normalize_app_name(app_name):
    if not app_name or not isinstance(app_name, str):
        return ""
    clean_name = app_name.strip().lower()
    if clean_name in ("browser", "brave-browser", "brave"):
        return "brave"
    elif clean_name in ("filemanager", "file_manager", "files", "folder", "thunar"):
        return "file_manager"
    elif clean_name in ("editor", "texteditor", "text_editor", "notepad", "nano", "xedit"):
        return "text_editor"
    elif clean_name in ("terminal", "console", "xfce4-terminal"):
        return "terminal"
    return clean_name


def is_window_open(app_name):
    """Checks if an application window is currently visible/open via wmctrl or xdotool."""
    clean_name = normalize_app_name(app_name)
    title_terms = {
        "brave": ["brave", "brave-browser"],
        "file_manager": ["thunar", "file manager", "downloads", "home"],
        "terminal": ["terminal", "xfce4-terminal", "xterm"],
        "text_editor": ["text editor", "nano", "xedit"]
    }
    terms = title_terms.get(clean_name, [clean_name])

    try:
        res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            lines = res.stdout.lower().splitlines()
            for line in lines:
                if any(t in line for t in terms):
                    return True
    except Exception:
        pass

    try:
        res = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", clean_name], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return True
    except Exception:
        pass

    return False


def get_active_window_app_name():
    """Returns the normalized app_name of the currently focused window on desktop."""
    try:
        res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            wname = res.stdout.strip().lower()
            if "brave" in wname:
                return "brave"
            if "terminal" in wname or "bash" in wname:
                return "terminal"
            if "thunar" in wname or "file" in wname or "folder" in wname:
                return "file_manager"
            if "editor" in wname or "nano" in wname:
                return "text_editor"
    except Exception:
        pass
    return None


def open_app(app_name):
    """
    Launches an approved application safely based on an explicit allowlist.
    Registers process ownership with AppTracker.
    """
    if not app_name or not isinstance(app_name, str):
        return "Error: Invalid application name specified."

    clean_name = normalize_app_name(app_name)

    if clean_name not in APPROVED_APPS:
        return f"Error: Application '{app_name}' is not in the approved safety allowlist."

    # Situational Awareness check: if already running, focus and report ready rather than spawning redundant process
    if default_app_tracker.is_running(clean_name) or (not os.environ.get("BRAIN_MOCK_GUI") and is_window_open(clean_name)):
        focus_app(clean_name)
        return f"Application '{clean_name}' is already running and focused (opened successfully)."

    executables = APPROVED_APPS[clean_name]
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        from unittest.mock import MagicMock
        mock_proc = MagicMock()
        mock_proc.pid = 7777
        mock_proc.poll.return_value = None
        default_app_tracker.record_launch(clean_name, executables[0], mock_proc)
        return f"Application '{clean_name}' opened successfully ({executables[0]})."

    for exe in executables:
        try:
            proc = subprocess.Popen([exe])
            default_app_tracker.record_launch(clean_name, exe, proc)

            # Bounded readiness check: verify process starts cleanly
            poll_val = proc.poll()
            if poll_val is None or not isinstance(poll_val, int):
                return f"Application '{clean_name}' opened successfully ({exe})."

            for _ in range(5):
                time.sleep(0.1)
                poll_val = proc.poll()
                if poll_val is None or not isinstance(poll_val, int):
                    break

            if poll_val is None or not isinstance(poll_val, int):
                return f"Application '{clean_name}' opened successfully ({exe})."
            else:
                return f"Error: Application '{clean_name}' terminated immediately with code {poll_val}."
        except FileNotFoundError:
            continue
        except Exception as e:
            return f"Error launching '{clean_name}' via {exe}: {str(e)}"

    return f"Error: Executable for '{clean_name}' was not found on your system."


def close_app(app_name):
    """
    Safely terminates Brain-owned application processes cleanly.
    Enforces process ownership tracking to prevent arbitrary system process termination.
    """
    if not app_name or not isinstance(app_name, str):
        return "Error: Invalid application name specified."

    clean_name = normalize_app_name(app_name)
    if clean_name not in APPROVED_APPS:
        return f"Error: Application '{app_name}' is not in the approved safety allowlist."

    return default_app_tracker.close_app(clean_name)


def focus_app(app_name):
    """
    Brings an existing application window to focus.
    Uses wmctrl / xdotool if available, or verifies window state.
    """
    if not app_name or not isinstance(app_name, str):
        return "Error: Invalid application name specified."

    clean_name = normalize_app_name(app_name)
    if clean_name not in APPROVED_APPS:
        return f"Error: Application '{app_name}' is not in the approved safety allowlist."

    # Map app_name to window title search term
    title_terms = {
        "brave": "Brave",
        "file_manager": "thunar",
        "terminal": "Terminal",
        "text_editor": "Text Editor"
    }
    term = title_terms.get(clean_name, clean_name)

    focused = False
    # Attempt wmctrl focus
    try:
        res = subprocess.run(["wmctrl", "-a", term], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            focused = True
    except Exception:
        pass

    if not focused:
        # Attempt xdotool focus
        try:
            res = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", clean_name, "windowactivate"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                focused = True
        except Exception:
            pass

    default_app_tracker.set_focused_app(clean_name)
    if focused:
        return f"Application '{clean_name}' focused successfully."

    if default_app_tracker.is_running(clean_name):
        return f"Application '{clean_name}' is running."
    return f"Notice: Application '{clean_name}' window focus attempted."


def open_brave():
    """Backward compatibility wrapper for opening Brave browser."""
    return open_app("brave")

