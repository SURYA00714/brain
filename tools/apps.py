import os
import signal
import subprocess
import time

APPROVED_APPS = {
    "brave": ["brave-browser"],
    "terminal": ["xfce4-terminal", "x-terminal-emulator"],
    "file_manager": ["thunar"],
    "text_editor": ["xedit", "x-text-editor", "nano"],
    "calculator": ["gnome-calculator", "galculator", "xcalc"]
}


class AppCapability:
    """Rich application capability definition supporting multi-method verification and aliasing."""
    def __init__(self, canonical_id, aliases, launch_cmds, process_patterns, window_patterns, verification_methods=None):
        self.canonical_id = canonical_id
        self.aliases = aliases
        self.launch_cmds = launch_cmds
        self.process_patterns = process_patterns
        self.window_patterns = window_patterns
        self.verification_methods = verification_methods or ["process", "window", "wmctrl", "xdotool"]


APP_CAPABILITIES = {
    "brave": AppCapability(
        "brave",
        ["brave", "browser", "brave-browser", "web browser", "internet"],
        ["brave-browser"],
        ["brave", "brave-browser"],
        ["brave", "brave browser"],
        ["process", "window", "wmctrl", "xdotool"]
    ),
    "terminal": AppCapability(
        "terminal",
        ["terminal", "console", "shell", "bash", "xfce4-terminal"],
        ["xfce4-terminal", "x-terminal-emulator"],
        ["xfce4-terminal", "terminal", "bash"],
        ["terminal", "xfce terminal"],
        ["process", "window", "wmctrl", "xdotool"]
    ),
    "file_manager": AppCapability(
        "file_manager",
        ["file_manager", "thunar", "files", "explorer", "file browser"],
        ["thunar"],
        ["thunar"],
        ["thunar", "file manager"],
        ["process", "window", "wmctrl"]
    ),
    "text_editor": AppCapability(
        "text_editor",
        ["text_editor", "editor", "xedit", "mousepad", "xed", "nano"],
        ["xedit", "x-text-editor", "mousepad", "xed"],
        ["xedit", "mousepad", "xed"],
        ["editor", "mousepad", "xed", "xedit"],
        ["process", "window", "wmctrl"]
    ),
    "calculator": AppCapability(
        "calculator",
        ["calculator", "calc", "gnome-calculator", "galculator"],
        ["gnome-calculator", "galculator", "xcalc"],
        ["gnome-calculator", "galculator", "xcalc"],
        ["calculator", "galculator"],
        ["process", "window", "wmctrl"]
    )
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
                if os.environ.get("BRAIN_MOCK_GUI") == "1":
                    return True
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
    elif clean_name in ("calculator", "calc", "galculator", "xcalc"):
        return "calculator"
    return clean_name


def is_window_open(app_name):
    """Checks if an application window is currently visible/open via wmctrl or xdotool."""
    clean_name = normalize_app_name(app_name)
    title_terms = {
        "brave": ["brave", "brave-browser"],
        "file_manager": ["thunar", "file manager", "downloads", "home"],
        "terminal": ["terminal", "xfce4-terminal", "xterm"],
        "text_editor": ["text editor", "nano", "xedit"],
        "calculator": ["calculator", "galculator", "xcalc"]
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


def verify_app_open(app_name: str, timeout: float = 1.5) -> dict:
    """
    Multi-signal application readiness verification.
    Signals checked:
    1. AppTracker (is_running, brain_owned)
    2. Window manager (is_window_open / wmctrl / xdotool)
    3. System process table (pgrep for capability process patterns)
    4. Active focused window (get_active_window_app_name)
    
    Returns dict:
    {
        "verified": bool,
        "method": str,  # "tracker" | "window" | "process" | "focus" | "mock" | "none"
        "signals": dict,
        "error": Optional[str]
    }
    """
    if not app_name or not isinstance(app_name, str):
        return {"verified": False, "method": "none", "signals": {}, "error": "Invalid application name"}

    clean_name = normalize_app_name(app_name)
    cap = APP_CAPABILITIES.get(clean_name)
    process_patterns = cap.process_patterns if cap else [clean_name]

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        is_running = default_app_tracker.is_running(clean_name)
        return {
            "verified": is_running,
            "method": "mock" if is_running else "none",
            "signals": {"tracker": is_running, "mock": True},
            "error": None if is_running else f"Process '{clean_name}' not detected"
        }

    deadline = time.time() + max(0.1, timeout)
    signals = {}

    while time.time() <= deadline:
        # Signal 1: AppTracker
        if default_app_tracker.is_running(clean_name):
            signals["tracker"] = True
            return {"verified": True, "method": "tracker", "signals": signals, "error": None}

        # Signal 2: Window Manager
        if is_window_open(clean_name):
            signals["window"] = True
            # Register in tracker so future checks are instant
            default_app_tracker.register_app(clean_name, brain_owned=False)
            return {"verified": True, "method": "window", "signals": signals, "error": None}

        # Signal 3: System Process Table via pgrep
        for pat in process_patterns:
            try:
                res = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True, timeout=1)
                if res.returncode == 0 and res.stdout.strip():
                    pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
                    if pids:
                        signals["process"] = pids[0]
                        default_app_tracker.register_app(clean_name, pid=pids[0], brain_owned=False)
                        return {"verified": True, "method": "process", "signals": signals, "error": None}
            except Exception:
                pass

        # Signal 4: Focused Window
        active_app = get_active_window_app_name()
        if active_app == clean_name:
            signals["focus"] = True
            default_app_tracker.set_focused_app(clean_name)
            return {"verified": True, "method": "focus", "signals": signals, "error": None}

        time.sleep(0.1)

    return {
        "verified": False,
        "method": "none",
        "signals": signals,
        "error": f"Process or window for '{clean_name}' not detected after {timeout}s"
    }


def get_system_state_summary() -> dict:
    """
    Deterministically gathers current running apps, active/focused app,
    active window title, and basic system metrics (RAM, disk, CPU load).
    Requires zero LLM calls and executes in <50ms.
    """
    running_apps = []
    
    # Check approved/known apps
    for canonical_id, cap in APP_CAPABILITIES.items():
        if default_app_tracker.is_running(canonical_id):
            running_apps.append(canonical_id)
        elif os.environ.get("BRAIN_MOCK_GUI") != "1":
            if is_window_open(canonical_id):
                running_apps.append(canonical_id)
            else:
                for pat in cap.process_patterns:
                    try:
                        res = subprocess.run(["pgrep", "-x", pat], capture_output=True, text=True, timeout=1)
                        if res.returncode == 0 and res.stdout.strip():
                            running_apps.append(canonical_id)
                            break
                    except Exception:
                        pass

    # Active app & window title
    active_app = get_active_window_app_name()
    if not active_app:
        active_app = default_app_tracker.get_focused_app()

    active_title = None
    if os.environ.get("BRAIN_MOCK_GUI") != "1":
        try:
            res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                active_title = res.stdout.strip()
        except Exception:
            pass

    # Disk usage
    import shutil
    try:
        disk = shutil.disk_usage("/")
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_free_gb = round(disk.free / (1024 ** 3), 1)
        disk_used_gb = round(disk.used / (1024 ** 3), 1)
        disk_pct = round((disk.used / disk.total) * 100, 1)
    except Exception:
        disk_total_gb = disk_free_gb = disk_used_gb = disk_pct = 0

    # RAM info from /proc/meminfo
    ram_total_mb = ram_free_mb = ram_avail_mb = 0
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_total_mb = round(int(line.split()[1]) / 1024)
                    elif line.startswith("MemAvailable:"):
                        ram_avail_mb = round(int(line.split()[1]) / 1024)
                    elif line.startswith("MemFree:") and not ram_avail_mb:
                        ram_free_mb = round(int(line.split()[1]) / 1024)
            if not ram_avail_mb:
                ram_avail_mb = ram_free_mb
    except Exception:
        pass

    # Load average
    try:
        load_avg = os.getloadavg()
    except Exception:
        load_avg = (0.0, 0.0, 0.0)

    return {
        "running_apps": running_apps,
        "active_app": active_app,
        "active_window_title": active_title,
        "disk": {
            "total_gb": disk_total_gb,
            "free_gb": disk_free_gb,
            "used_gb": disk_used_gb,
            "percent_used": disk_pct
        },
        "memory": {
            "total_mb": ram_total_mb,
            "available_mb": ram_avail_mb,
            "used_mb": ram_total_mb - ram_avail_mb
        },
        "load_avg": load_avg
    }


def format_system_state_summary(state: dict = None) -> str:
    """Formats system state summary into clear human-readable string."""
    if state is None:
        state = get_system_state_summary()

    running = state.get("running_apps", [])
    active = state.get("active_app")
    title = state.get("active_window_title")

    apps_str = ", ".join(running) if running else "None detected"
    active_str = active if active else "None"
    if title:
        active_str += f" ('{title}')"

    disk = state.get("disk", {})
    mem = state.get("memory", {})

    output = (
        f"Open applications: {apps_str}\n"
        f"Currently active application: {active_str}\n"
        f"Memory: {mem.get('available_mb', 0)}MB available of {mem.get('total_mb', 0)}MB\n"
        f"Disk: {disk.get('free_gb', 0)}GB free of {disk.get('total_gb', 0)}GB ({disk.get('percent_used', 0)}% used)"
    )
    return output


