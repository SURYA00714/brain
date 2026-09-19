import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, Any, Optional

try:
    import psutil
except ImportError:
    psutil = None


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


# -------------------------------------------------------------------
# Audio & Display Controls
# -------------------------------------------------------------------

def volume_up(step_percent: int = 5) -> Dict[str, Any]:
    """Increases master audio volume."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "VOLUME_UP", "data": f"Volume increased by {step_percent}%."}

    # Attempt 1: pactl
    if _run_cmd_safe(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step_percent}%"]) is not None:
        return {"success": True, "tool": "VOLUME_UP", "data": f"Volume increased by {step_percent}% via pactl."}

    # Attempt 2: amixer
    if _run_cmd_safe(["amixer", "-q", "set", "Master", f"{step_percent}%+"]) is not None:
        return {"success": True, "tool": "VOLUME_UP", "data": f"Volume increased by {step_percent}% via amixer."}

    return {"success": False, "tool": "VOLUME_UP", "error": "No supported audio control utility found (pactl/amixer)."}


def volume_down(step_percent: int = 5) -> Dict[str, Any]:
    """Decreases master audio volume."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "VOLUME_DOWN", "data": f"Volume decreased by {step_percent}%."}

    if _run_cmd_safe(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step_percent}%"]) is not None:
        return {"success": True, "tool": "VOLUME_DOWN", "data": f"Volume decreased by {step_percent}% via pactl."}

    if _run_cmd_safe(["amixer", "-q", "set", "Master", f"{step_percent}%-"]) is not None:
        return {"success": True, "tool": "VOLUME_DOWN", "data": f"Volume decreased by {step_percent}% via amixer."}

    return {"success": False, "tool": "VOLUME_DOWN", "error": "No supported audio control utility found (pactl/amixer)."}


def volume_mute() -> Dict[str, Any]:
    """Toggles master audio mute state."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "VOLUME_MUTE", "data": "Volume mute state toggled."}

    if _run_cmd_safe(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]) is not None:
        return {"success": True, "tool": "VOLUME_MUTE", "data": "Volume mute toggled via pactl."}

    if _run_cmd_safe(["amixer", "-q", "set", "Master", "toggle"]) is not None:
        return {"success": True, "tool": "VOLUME_MUTE", "data": "Volume mute toggled via amixer."}

    return {"success": False, "tool": "VOLUME_MUTE", "error": "No supported audio control utility found (pactl/amixer)."}


def brightness_up(step_percent: int = 10) -> Dict[str, Any]:
    """Increases display brightness."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BRIGHTNESS_UP", "data": f"Brightness increased by {step_percent}%."}

    if _run_cmd_safe(["brightnessctl", "set", f"+{step_percent}%"]) is not None:
        return {"success": True, "tool": "BRIGHTNESS_UP", "data": f"Brightness increased by {step_percent}% via brightnessctl."}

    if _run_cmd_safe(["xbacklight", "-inc", str(step_percent)]) is not None:
        return {"success": True, "tool": "BRIGHTNESS_UP", "data": f"Brightness increased by {step_percent}% via xbacklight."}

    return {"success": False, "tool": "BRIGHTNESS_UP", "error": "No supported brightness control utility found (brightnessctl/xbacklight)."}


def brightness_down(step_percent: int = 10) -> Dict[str, Any]:
    """Decreases display brightness."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BRIGHTNESS_DOWN", "data": f"Brightness decreased by {step_percent}%."}

    if _run_cmd_safe(["brightnessctl", "set", f"{step_percent}%-"]) is not None:
        return {"success": True, "tool": "BRIGHTNESS_DOWN", "data": f"Brightness decreased by {step_percent}% via brightnessctl."}

    if _run_cmd_safe(["xbacklight", "-dec", str(step_percent)]) is not None:
        return {"success": True, "tool": "BRIGHTNESS_DOWN", "data": f"Brightness decreased by {step_percent}% via xbacklight."}

    return {"success": False, "tool": "BRIGHTNESS_DOWN", "error": "No supported brightness control utility found (brightnessctl/xbacklight)."}


def lock_screen() -> Dict[str, Any]:
    """Locks desktop screen."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "LOCK_SCREEN", "data": "Screen locked."}

    lock_cmds = [
        ["xflock4"],
        ["xdg-screensaver", "lock"],
        ["cinnamon-screensaver-command", "-l"],
        ["gnome-screensaver-command", "-l"],
        ["slock"]
    ]
    for cmd in lock_cmds:
        if _run_cmd_safe(cmd) is not None:
            return {"success": True, "tool": "LOCK_SCREEN", "data": f"Screen locked via {cmd[0]}."}

    return {"success": False, "tool": "LOCK_SCREEN", "error": "No supported screen locker utility found."}


# -------------------------------------------------------------------
# Network Controls (Wi-Fi / Bluetooth)
# -------------------------------------------------------------------

def wifi_status() -> Dict[str, Any]:
    """Returns Wi-Fi radio status."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "WIFI_STATUS", "data": "Wi-Fi is currently enabled."}

    out = _run_cmd_safe(["nmcli", "radio", "wifi"])
    if out:
        return {"success": True, "tool": "WIFI_STATUS", "data": f"Wi-Fi status: {out}."}

    out_rf = _run_cmd_safe(["rfkill", "list", "wlan"])
    if out_rf:
        blocked = "soft: yes" in out_rf.lower() or "hard: yes" in out_rf.lower()
        stat = "disabled" if blocked else "enabled"
        return {"success": True, "tool": "WIFI_STATUS", "data": f"Wi-Fi status: {stat}."}

    return {"success": False, "tool": "WIFI_STATUS", "error": "Unable to query Wi-Fi status."}


def wifi_on() -> Dict[str, Any]:
    """Enables Wi-Fi adapter."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "WIFI_ON", "data": "Wi-Fi turned on."}

    if _run_cmd_safe(["nmcli", "radio", "wifi", "on"]) is not None:
        return {"success": True, "tool": "WIFI_ON", "data": "Wi-Fi turned on via nmcli."}

    if _run_cmd_safe(["rfkill", "unblock", "wlan"]) is not None:
        return {"success": True, "tool": "WIFI_ON", "data": "Wi-Fi unblocked via rfkill."}

    return {"success": False, "tool": "WIFI_ON", "error": "Failed to enable Wi-Fi."}


def wifi_off() -> Dict[str, Any]:
    """Disables Wi-Fi adapter."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "WIFI_OFF", "data": "Wi-Fi turned off."}

    if _run_cmd_safe(["nmcli", "radio", "wifi", "off"]) is not None:
        return {"success": True, "tool": "WIFI_OFF", "data": "Wi-Fi turned off via nmcli."}

    if _run_cmd_safe(["rfkill", "block", "wlan"]) is not None:
        return {"success": True, "tool": "WIFI_OFF", "data": "Wi-Fi blocked via rfkill."}

    return {"success": False, "tool": "WIFI_OFF", "error": "Failed to disable Wi-Fi."}


def bluetooth_status() -> Dict[str, Any]:
    """Returns Bluetooth status."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BLUETOOTH_STATUS", "data": "Bluetooth is currently enabled."}

    out = _run_cmd_safe(["rfkill", "list", "bluetooth"])
    if out:
        blocked = "soft: yes" in out.lower() or "hard: yes" in out.lower()
        stat = "disabled" if blocked else "enabled"
        return {"success": True, "tool": "BLUETOOTH_STATUS", "data": f"Bluetooth status: {stat}."}

    out_bt = _run_cmd_safe(["bluetoothctl", "show"])
    if out_bt:
        powered = "powered: yes" in out_bt.lower()
        stat = "enabled" if powered else "disabled"
        return {"success": True, "tool": "BLUETOOTH_STATUS", "data": f"Bluetooth status: {stat}."}

    return {"success": False, "tool": "BLUETOOTH_STATUS", "error": "Unable to query Bluetooth status."}


def bluetooth_on() -> Dict[str, Any]:
    """Enables Bluetooth adapter."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BLUETOOTH_ON", "data": "Bluetooth turned on."}

    if _run_cmd_safe(["rfkill", "unblock", "bluetooth"]) is not None:
        return {"success": True, "tool": "BLUETOOTH_ON", "data": "Bluetooth unblocked via rfkill."}

    if _run_cmd_safe(["bluetoothctl", "power", "on"]) is not None:
        return {"success": True, "tool": "BLUETOOTH_ON", "data": "Bluetooth powered on via bluetoothctl."}

    return {"success": False, "tool": "BLUETOOTH_ON", "error": "Failed to enable Bluetooth."}


def bluetooth_off() -> Dict[str, Any]:
    """Disables Bluetooth adapter."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        return {"success": True, "tool": "BLUETOOTH_OFF", "data": "Bluetooth turned off."}

    if _run_cmd_safe(["rfkill", "block", "bluetooth"]) is not None:
        return {"success": True, "tool": "BLUETOOTH_OFF", "data": "Bluetooth blocked via rfkill."}

    if _run_cmd_safe(["bluetoothctl", "power", "off"]) is not None:
        return {"success": True, "tool": "BLUETOOTH_OFF", "data": "Bluetooth powered off via bluetoothctl."}

    return {"success": False, "tool": "BLUETOOTH_OFF", "error": "Failed to disable Bluetooth."}


# -------------------------------------------------------------------
# System Metrics & Diagnostics
# -------------------------------------------------------------------

def get_system_info() -> Dict[str, Any]:
    """Returns OS distribution, architecture, and system information."""
    info = {
        "os": "Linux",
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0]
    }
    # Check lsb_release if available
    lsb = _run_cmd_safe(["lsb_release", "-ds"])
    if lsb:
        info["distro"] = lsb.strip('"')

    formatted = f"Operating System: {info.get('distro', 'Linux')} (Kernel {info['release']}, {info['machine']})"
    return {"success": True, "tool": "SYSTEM_INFO", "data": formatted, "info": info}


def memory_status() -> Dict[str, Any]:
    """Returns total, available, used memory metrics."""
    if psutil:
        mem = psutil.virtual_memory()
        total_mb = int(mem.total / (1024 * 1024))
        avail_mb = int(mem.available / (1024 * 1024))
        used_mb = total_mb - avail_mb
        pct = mem.percent
        formatted = f"Memory Usage: {avail_mb}MB available out of {total_mb}MB ({pct}% used)."
        return {
            "success": True,
            "tool": "MEMORY_STATUS",
            "data": formatted,
            "metrics": {"total_mb": total_mb, "available_mb": avail_mb, "used_mb": used_mb, "percent": pct}
        }

    # Fallback to /proc/meminfo
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem_info = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                k = parts[0].strip()
                v = parts[1].strip().split()[0]
                if v.isdigit():
                    mem_info[k] = int(v)
        total_mb = int(mem_info.get("MemTotal", 0) / 1024)
        free_mb = int(mem_info.get("MemAvailable", mem_info.get("MemFree", 0)) / 1024)
        pct = round(((total_mb - free_mb) / total_mb) * 100, 1) if total_mb else 0
        formatted = f"Memory Usage: {free_mb}MB available out of {total_mb}MB ({pct}% used)."
        return {
            "success": True,
            "tool": "MEMORY_STATUS",
            "data": formatted,
            "metrics": {"total_mb": total_mb, "available_mb": free_mb, "percent": pct}
        }
    except Exception as e:
        return {"success": False, "tool": "MEMORY_STATUS", "error": f"Failed to retrieve memory stats: {str(e)}"}


def disk_status(target_path: str = "/") -> Dict[str, Any]:
    """Returns storage metrics for the target filesystem path."""
    try:
        total, used, free = shutil.disk_usage(target_path)
        total_gb = round(total / (1024 ** 3), 2)
        free_gb = round(free / (1024 ** 3), 2)
        used_gb = round(used / (1024 ** 3), 2)
        pct = round((used / total) * 100, 1) if total else 0
        formatted = f"Disk Space ({target_path}): {free_gb}GB free out of {total_gb}GB ({pct}% used)."
        return {
            "success": True,
            "tool": "DISK_STATUS",
            "data": formatted,
            "metrics": {"total_gb": total_gb, "free_gb": free_gb, "used_gb": used_gb, "percent": pct}
        }
    except Exception as e:
        return {"success": False, "tool": "DISK_STATUS", "error": f"Failed to retrieve disk stats: {str(e)}"}


def cpu_status() -> Dict[str, Any]:
    """Returns CPU core count and utilization metrics."""
    cores = os.cpu_count() or 1
    pct = 0.0
    if psutil:
        pct = psutil.cpu_percent(interval=0.1)

    formatted = f"CPU Status: {cores} cores detected ({pct}% current utilization)."
    return {
        "success": True,
        "tool": "CPU_STATUS",
        "data": formatted,
        "metrics": {"cores": cores, "percent": pct}
    }


# -------------------------------------------------------------------
# Confirmation-Gated Disruptive Power Operations & Exceptions
# -------------------------------------------------------------------

class PowerOperationError(Exception):
    """Base exception for power operations (shutdown, reboot, suspend, logout)."""
    pass


class ConfirmationRequiredError(PowerOperationError):
    """Raised when a power operation requires explicit user confirmation."""
    pass


def _is_testing_or_mock_env() -> bool:
    """Strictly checks if running inside automated unit tests or mock mode to prevent live power actions."""
    if os.environ.get("BRAIN_MOCK_GUI") == "1" or os.environ.get("BRAIN_NO_POWER_OPS") == "1":
        return True
    import sys
    if "unittest" in sys.modules or "pytest" in sys.modules:
        return True
    return False


def shutdown(confirmed: bool = False, raise_on_confirmation: bool = False) -> Dict[str, Any]:
    """Triggers system shutdown (Confirmation Gated & Hardware Protected in tests)."""
    if not confirmed:
        if raise_on_confirmation:
            raise ConfirmationRequiredError("Confirmation Required: System shutdown requires explicit user confirmation.")
        if not _is_testing_or_mock_env():
            from core.confirmation import default_confirmation_manager
            status, req = default_confirmation_manager.evaluate_action("SHUTDOWN", {})
            if status == "REQUIRED":
                return {
                    "success": False,
                    "tool": "SHUTDOWN",
                    "confirmation_required": True,
                    "error": "Confirmation Required: System shutdown requires explicit user confirmation."
                }

    if _is_testing_or_mock_env():
        return {"success": True, "tool": "SHUTDOWN", "data": "System shutdown initiated (mocked / dry-run safety)."}

    try:
        res = _run_cmd_safe(["systemctl", "poweroff"])
        if res is None:
            raise PowerOperationError("Failed to execute systemctl poweroff.")
        return {"success": True, "tool": "SHUTDOWN", "data": "System shutdown initiated."}
    except Exception as e:
        if isinstance(e, PowerOperationError):
            raise
        raise PowerOperationError(f"Shutdown operation encountered exception: {str(e)}") from e


def restart(confirmed: bool = False, raise_on_confirmation: bool = False) -> Dict[str, Any]:
    """Triggers system reboot (Confirmation Gated & Hardware Protected in tests)."""
    if not confirmed:
        if raise_on_confirmation:
            raise ConfirmationRequiredError("Confirmation Required: System restart requires explicit user confirmation.")
        if not _is_testing_or_mock_env():
            from core.confirmation import default_confirmation_manager
            status, req = default_confirmation_manager.evaluate_action("RESTART", {})
            if status == "REQUIRED":
                return {
                    "success": False,
                    "tool": "RESTART",
                    "confirmation_required": True,
                    "error": "Confirmation Required: System restart requires explicit user confirmation."
                }

    if _is_testing_or_mock_env():
        return {"success": True, "tool": "RESTART", "data": "System restart initiated (mocked / dry-run safety)."}

    try:
        res = _run_cmd_safe(["systemctl", "reboot"])
        if res is None:
            raise PowerOperationError("Failed to execute systemctl reboot.")
        return {"success": True, "tool": "RESTART", "data": "System restart initiated."}
    except Exception as e:
        if isinstance(e, PowerOperationError):
            raise
        raise PowerOperationError(f"Restart operation encountered exception: {str(e)}") from e


def suspend(confirmed: bool = False, raise_on_confirmation: bool = False) -> Dict[str, Any]:
    """Triggers system suspend/sleep (Confirmation Gated & Hardware Protected in tests)."""
    if not confirmed:
        if raise_on_confirmation:
            raise ConfirmationRequiredError("Confirmation Required: System suspend requires explicit user confirmation.")
        if not _is_testing_or_mock_env():
            from core.confirmation import default_confirmation_manager
            status, req = default_confirmation_manager.evaluate_action("SUSPEND", {})
            if status == "REQUIRED":
                return {
                    "success": False,
                    "tool": "SUSPEND",
                    "confirmation_required": True,
                    "error": "Confirmation Required: System suspend requires explicit user confirmation."
                }

    if _is_testing_or_mock_env():
        return {"success": True, "tool": "SUSPEND", "data": "System suspend initiated (mocked / dry-run safety)."}

    try:
        res = _run_cmd_safe(["systemctl", "suspend"])
        if res is None:
            raise PowerOperationError("Failed to execute systemctl suspend.")
        return {"success": True, "tool": "SUSPEND", "data": "System suspend initiated."}
    except Exception as e:
        if isinstance(e, PowerOperationError):
            raise
        raise PowerOperationError(f"Suspend operation encountered exception: {str(e)}") from e


def logout(confirmed: bool = False, raise_on_confirmation: bool = False) -> Dict[str, Any]:
    """Triggers desktop user logout (Confirmation Gated & Hardware Protected in tests)."""
    if not confirmed:
        if raise_on_confirmation:
            raise ConfirmationRequiredError("Confirmation Required: Desktop logout requires explicit user confirmation.")
        if not _is_testing_or_mock_env():
            from core.confirmation import default_confirmation_manager
            status, req = default_confirmation_manager.evaluate_action("LOGOUT", {})
            if status == "REQUIRED":
                return {
                    "success": False,
                    "tool": "LOGOUT",
                    "confirmation_required": True,
                    "error": "Confirmation Required: Desktop logout requires explicit user confirmation."
                }

    if _is_testing_or_mock_env():
        return {"success": True, "tool": "LOGOUT", "data": "User logout initiated (mocked / dry-run safety)."}

    try:
        logout_cmds = [
            ["xfce4-session-logout", "--logout"],
            ["gnome-session-quit", "--logout", "--no-prompt"],
            ["cinnamon-session-quit", "--logout", "--no-prompt"]
        ]
        for cmd in logout_cmds:
            if _run_cmd_safe(cmd) is not None:
                return {"success": True, "tool": "LOGOUT", "data": f"Logout initiated via {cmd[0]}."}

        raise PowerOperationError("Unable to trigger session logout: no supported session logout utility succeeded.")
    except Exception as e:
        if isinstance(e, PowerOperationError):
            raise
        raise PowerOperationError(f"Logout operation encountered exception: {str(e)}") from e
