import os
import re
from pathlib import Path
from typing import Tuple, Optional, Any, Dict, List

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except (ImportError, SystemExit):
    pyautogui = None
    HAS_PYAUTOGUI = False

try:
    from pynput.mouse import Controller as MouseController, Button
    from pynput.keyboard import Controller as KeyboardController, Key
    HAS_PYNPUT = True
    mouse_ctrl = MouseController()
    key_ctrl = KeyboardController()
except (ImportError, Exception):
    pynput = None
    HAS_PYNPUT = False
    mouse_ctrl = None
    key_ctrl = None


# Allowed key names allowlist
VALID_KEYS = {
    "enter", "return", "tab", "space", "backspace", "escape", "esc",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown", "delete",
    "ctrl", "ctrlleft", "ctrlright", "alt", "altleft", "altright", "shift", "shiftleft", "shiftright",
    "super", "win", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"
}

# Mapping string key names to pynput Key objects
PYNPUT_KEY_MAP = {
    "enter": Key.enter if HAS_PYNPUT else "enter",
    "return": Key.enter if HAS_PYNPUT else "return",
    "tab": Key.tab if HAS_PYNPUT else "tab",
    "space": Key.space if HAS_PYNPUT else "space",
    "backspace": Key.backspace if HAS_PYNPUT else "backspace",
    "escape": Key.esc if HAS_PYNPUT else "escape",
    "esc": Key.esc if HAS_PYNPUT else "esc",
    "up": Key.up if HAS_PYNPUT else "up",
    "down": Key.down if HAS_PYNPUT else "down",
    "left": Key.left if HAS_PYNPUT else "left",
    "right": Key.right if HAS_PYNPUT else "right",
    "home": Key.home if HAS_PYNPUT else "home",
    "end": Key.end if HAS_PYNPUT else "end",
    "pageup": Key.page_up if HAS_PYNPUT else "pageup",
    "pagedown": Key.page_down if HAS_PYNPUT else "pagedown",
    "delete": Key.delete if HAS_PYNPUT else "delete",
    "ctrl": Key.ctrl if HAS_PYNPUT else "ctrl",
    "alt": Key.alt if HAS_PYNPUT else "alt",
    "shift": Key.shift if HAS_PYNPUT else "shift",
    "super": Key.cmd if HAS_PYNPUT else "super",
    "win": Key.cmd if HAS_PYNPUT else "win",
}

MAX_TEXT_LENGTH = 2000
MAX_SCROLL_AMOUNT = 1000


def get_screen_dimensions():
    """Returns (width, height) of the desktop screen. Defaults to (1920, 1080) if display is unavailable."""
    if HAS_PYAUTOGUI and pyautogui is not None:
        try:
            w, h = pyautogui.size()
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return 1920, 1080


def validate_coordinates(x, y):
    """
    Validates screen coordinates against desktop dimensions.
    Enforces 0 <= x < width and 0 <= y < height.
    """
    try:
        x_val = int(x)
        y_val = int(y)
    except (TypeError, ValueError):
        return None, None, "Error: Coordinates must be valid integers."

    w, h = get_screen_dimensions()
    if not (0 <= x_val < w and 0 <= y_val < h):
        return None, None, f"Error: Coordinates ({x_val}, {y_val}) are outside screen bounds ({w}x{h})."

    return x_val, y_val, None


class ActionChainTracker:
    """
    Stateful Action-Chain & Context Safety Tracker.
    Maintains bounded buffer of recent executed actions and tracks active application context.
    """
    def __init__(self, max_history=10):
        self.max_history = max_history
        self.history = []
        self.active_app_context = None

    def record_action(self, tool_name, args, result):
        """Records executed action and updates active application context."""
        t_name = str(tool_name).upper()
        if t_name == "OPEN_APP":
            app = str(args.get("app_name") or args.get("app") or "").lower()
            self.active_app_context = app

        entry = {
            "tool": t_name,
            "args": args if isinstance(args, dict) else {},
            "result": result,
            "app_context": self.active_app_context
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_last_action(self):
        return self.history[-1] if self.history else None

    def get_last_typed_text(self):
        for entry in reversed(self.history):
            if entry["tool"] in ("TYPE_TEXT", "TYPE_IN_ELEMENT"):
                return entry["args"].get("text", "")
        return None

    def clear(self):
        self.history = []
        self.active_app_context = None


default_chain_tracker = ActionChainTracker()


def validate_gui_action_safety(tool_name, args):
    """
    Gates dangerous GUI actions (e.g. typing terminal commands or administrative commands).
    Uses order-agnostic token parsing, regex matching, and Action-Chain context tracking.
    Returns (is_safe, error_message).
    """
    tool_upper = str(tool_name).upper()

    if tool_upper == "TYPE_TEXT":
        text = str(args.get("text", "")).strip()
        if not text:
            return True, None

        # Normalize whitespace (spaces, tabs, newlines) into single spaces for robust token matching
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        words = normalized.split()

        # 1. Order-Agnostic 'rm' Token Analysis (REDTEAM-001 fix)
        is_rm = any(w in ("rm", "/bin/rm", "/usr/bin/rm") or w.endswith("/rm") for w in words)
        if is_rm:
            has_recursive = any(w in ("--recursive", "-r", "-R") or re.search(r"^-[a-z]*r[a-z]*$", w) for w in words)
            has_force = any(w in ("--force", "-f") or re.search(r"^-[a-z]*f[a-z]*$", w) for w in words)
            has_root_path = any(w in ("/", "/*", "/etc", "/root", "/boot", "/dev", "..") or (len(w) > 1 and w.startswith("/")) for w in words[1:])

            if (has_recursive and has_force) or (has_recursive and has_root_path) or (has_force and has_root_path):
                return False, "Safety Block: Autonomous typing of dangerous command ('rm' with recursive/force/root options) requires explicit user confirmation."

        # 2. General Dangerous Command & Interpreter Patterns
        dangerous_patterns = [
            r"\bsudo\b", r"\bsu\b",
            r"\b/bin/rm\b", r"\b/usr/bin/rm\b",
            r"\bchmod\s+([0-7]{3,4}|\+x|a\+rwx)",
            r"\bchown\b",
            r"\bdd\b\s+if=", r"\bmkfs\b",
            r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b", r"\binit\s+[06]\b",
            r"\bformat\b",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
            r"\bpython[23]?\s+-c\b",
            r"\b(bash|sh|zsh)\s+-c\b",
            r"\b(eval|exec)\b\s*\(",
            r"\bperl\s+-e\b", r"\bruby\s+-e\b"
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, normalized):
                return False, f"Safety Block: Autonomous typing of dangerous command (matching pattern '{pattern}') requires explicit user confirmation."

        # 3. Terminal Context Safety
        if default_chain_tracker.active_app_context == "terminal":
            # Any executable-looking command in terminal context requires safety gating
            if any(char in text for char in (";", "&&", "||", "|", "`", "$(")) or (words and words[0] in ("rm", "sudo", "chmod", "chown", "dd", "mkfs")):
                return False, "Safety Block: Autonomous typing of command in active terminal context requires explicit user confirmation."

    # 4. Action-Chain Evaluation for Submit Keys (REDTEAM-002 fix)
    if tool_upper in ("PRESS_KEY", "HOTKEY"):
        key_name = str(args.get("key", "")).strip().lower() if tool_upper == "PRESS_KEY" else ""
        if tool_upper == "HOTKEY":
            keys = args.get("keys", [])
            key_name = "-".join([str(k).lower() for k in keys])

        if key_name in ("enter", "return", "ctrl-m") or "enter" in key_name:
            last_typed = default_chain_tracker.get_last_typed_text()
            app_ctx = default_chain_tracker.active_app_context

            if last_typed:
                norm_last = re.sub(r"\s+", " ", last_typed).strip().lower()
                # If submitting text typed in terminal or containing explicit command keywords -> Fail closed
                if app_ctx == "terminal" or any(kw in norm_last for kw in ("rm ", "sudo ", "chmod ", "dd ", "python -c", "python3 -c", "bash -c", "sh -c")):
                    return False, "Safety Block: Action-chain submitting text execution in terminal context requires explicit user confirmation."

    return True, None


def screen_prompt_safety(user_request: str) -> Tuple[bool, Optional[str]]:
    """
    Zero-Latency Immediate Safety Screen (<1ms).
    Evaluates incoming raw user request before invoking any LLM, planner, or tool.
    Detects explicitly destructive system actions and returns (is_safe, error_message).
    """
    if not user_request or not isinstance(user_request, str):
        return True, None

    normalized = re.sub(r"\s+", " ", user_request).strip().lower()

    # Guard harmless educational/informational queries (e.g. "how does rm -rf work?", "explain disk formatting")
    if any(normalized.startswith(q) for q in ["how does ", "explain ", "what is ", "why is ", "tell me about ", "describe "]):
        return True, None

    # 1. Destructive File System & Intent Categories
    destructive_intents = [
        "delete all my files", "delete all files", "delete my files", "delete system files",
        "delete all system files", "destroy system", "destroy system files", "wipe all files",
        "wipe the disk", "wipe disk", "format my drive", "format the drive", "format drive", "format all",
        "erase my entire home directory", "erase home directory", "erase my home directory",
        "remove everything from my computer", "remove everything from computer"
    ]
    if any(intent in normalized for intent in destructive_intents):
        return False, "Brain Safety Block: Destructive mass file deletion or system wipe is prohibited by safety policy."

    words = normalized.split()
    is_rm = any(w in ("rm", "/bin/rm", "/usr/bin/rm") or w.endswith("/rm") for w in words)
    if is_rm:
        has_recursive = any(w in ("--recursive", "-r", "-R") or re.search(r"^-[a-z]*r[a-z]*$", w) for w in words)
        has_force = any(w in ("--force", "-f") or re.search(r"^-[a-z]*f[a-z]*$", w) for w in words)
        has_root_path = any(w in ("/", "/*", "/etc", "/root", "/boot", "/dev", "/usr", "..") or (len(w) > 1 and w.startswith("/")) for w in words[1:])
        if (has_recursive and has_force) or (has_recursive and has_root_path) or (has_force and has_root_path):
            return False, "Brain Safety Block: Destructive recursive file deletion is prohibited by safety policy."

    # 2. Disk and Hardware Destruction
    destructive_patterns = [
        r"\bdd\b\s+if=",
        r"\bmkfs\b",
        r"\bformat\s+(?:disk|partition|drive|[a-z]:)",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
        r"\b(?:shutdown|reboot|poweroff)\b",
        r"\binit\s+[06]\b"
    ]
    for pattern in destructive_patterns:
        if re.search(pattern, normalized):
            return False, f"Brain Safety Block: Destructive administrative command (matching '{pattern}') is prohibited."

    return True, None





def move_mouse(x, y):
    """Moves the mouse pointer to (x, y)."""
    cx, cy, err = validate_coordinates(x, y)
    if err:
        return err

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.moveTo(cx, cy)
        elif HAS_PYNPUT and mouse_ctrl:
            mouse_ctrl.position = (cx, cy)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"x": cx, "y": cy}
    except Exception as e:
        return f"Error moving mouse: {str(e)}"


def click_mouse(x, y, button="left"):
    """Clicks the mouse at (x, y)."""
    cx, cy, err = validate_coordinates(x, y)
    if err:
        return err

    clean_btn = str(button).strip().lower()
    if clean_btn not in ("left", "right", "middle"):
        return "Error: Invalid mouse button specified (must be 'left', 'right', or 'middle')."

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.click(cx, cy, button=clean_btn)
        elif HAS_PYNPUT and mouse_ctrl:
            mouse_ctrl.position = (cx, cy)
            p_btn = Button.left if clean_btn == "left" else (Button.right if clean_btn == "right" else Button.middle)
            mouse_ctrl.click(p_btn)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"x": cx, "y": cy, "button": clean_btn}
    except Exception as e:
        return f"Error clicking mouse: {str(e)}"


def double_click(x, y):
    """Double-clicks the mouse at (x, y)."""
    cx, cy, err = validate_coordinates(x, y)
    if err:
        return err

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.doubleClick(cx, cy)
        elif HAS_PYNPUT and mouse_ctrl:
            mouse_ctrl.position = (cx, cy)
            mouse_ctrl.click(Button.left, 2)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"x": cx, "y": cy, "action": "double_click"}
    except Exception as e:
        return f"Error double-clicking mouse: {str(e)}"


def scroll(amount):
    """Scrolls the desktop window up (positive) or down (negative)."""
    try:
        val = int(amount)
    except (TypeError, ValueError):
        return "Error: Scroll amount must be a valid integer."

    bounded_val = max(-MAX_SCROLL_AMOUNT, min(MAX_SCROLL_AMOUNT, val))

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.scroll(bounded_val)
        elif HAS_PYNPUT and mouse_ctrl:
            mouse_ctrl.scroll(0, bounded_val)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"amount": bounded_val}
    except Exception as e:
        return f"Error scrolling: {str(e)}"


def type_text(text):
    """Types text into the currently focused window. Enforces 2,000 character limit."""
    if not text or not isinstance(text, str):
        return "Error: Text parameter cannot be empty."

    if len(text) > MAX_TEXT_LENGTH:
        return f"Error: Text length ({len(text)} chars) exceeds maximum limit of {MAX_TEXT_LENGTH} characters."

    safe, err = validate_gui_action_safety("TYPE_TEXT", {"text": text})
    if not safe:
        return err

    if os.getenv("BRAIN_MOCK_GUI") == "1":
        return {"typed_chars": len(text)}

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.typewrite(text)
        elif HAS_PYNPUT and key_ctrl:
            key_ctrl.type(text)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"typed_chars": len(text)}
    except Exception as e:
        return f"Error typing text: {str(e)}"


def requires_confirmation(action, context=None):
    """
    Evaluates whether an action requires explicit user confirmation based on safety rules and context risk level.
    Risk Levels: LOW (allowed), MEDIUM (validation required), HIGH (requires user confirmation), UNKNOWN (fail closed).
    Returns dict: {"allowed": bool, "requires_confirmation": bool, "risk_level": str, "reason": str or None}
    """
    action_type = str(action).upper()
    ctx_str = str(context).strip() if context else ""
    norm_ctx = re.sub(r"\s+", " ", ctx_str).lower() if ctx_str else ""

    high_risk_patterns = [
        r"\bsudo\b", r"\bsu\b", r"\brm\b", r"\bchmod\b", r"\bchown\b",
        r"\bdd\b", r"\bmkfs\b", r"\bshutdown\b", r"\breboot\b", r"\bformat\b",
        r"\bcredential\b", r"\bpassword\b", r"\bdelete\b"
    ]

    for pattern in high_risk_patterns:
        if re.search(pattern, norm_ctx):
            return {
                "allowed": False,
                "requires_confirmation": True,
                "risk_level": "HIGH",
                "reason": f"Safety Gating: Action '{action_type}' with high-risk context matching '{pattern}' requires explicit user confirmation."
            }

    return {
        "allowed": True,
        "requires_confirmation": False,
        "risk_level": "LOW",
        "reason": None
    }



def click_element(element_id, button="left"):
    """
    Looks up element in active screen observation and clicks its center coordinates.
    Enforces observation freshness and ambiguity resolution.
    """
    from tools.vision import default_vision

    if not default_vision.is_observation_fresh():
        return "Error: Screen observation is stale or missing. Please run ANALYZE_SCREEN first."

    elem = default_vision.find_element(element_id)
    if not elem:
        return f"Error: Element '{element_id}' not found in current screen observation."

    if isinstance(elem, dict) and elem.get("ambiguous"):
        matches = elem.get("matches", [])
        return f"Error: Ambiguous target. Multiple elements ({len(matches)}) match '{element_id}'. Please specify exact element ID."

    cx = elem.get("center_x") if isinstance(elem, dict) else getattr(elem, "center_x", None)
    cy = elem.get("center_y") if isinstance(elem, dict) else getattr(elem, "center_y", None)

    if cx is None or cy is None:
        return f"Error: Invalid or missing coordinates for element '{element_id}'."

    return click_mouse(cx, cy, button=button)


def type_in_element(element_id, text):
    """
    Clicks the element to focus, then types text into it.
    Blocks typing into sensitive/credential fields.
    """
    from tools.vision import default_vision

    if not default_vision.is_observation_fresh():
        return "Error: Screen observation is stale or missing. Please run ANALYZE_SCREEN first."

    elem = default_vision.find_element(element_id)
    if isinstance(elem, dict):
        if elem.get("ambiguous"):
            matches = elem.get("matches", [])
            return f"Error: Ambiguous target. Multiple elements ({len(matches)}) match '{element_id}'. Please specify exact element ID."

        if elem.get("is_sensitive"):
            return "Safety Block: Autonomous typing into sensitive credential/password fields is blocked. Human interaction required."

    lower_id = str(element_id).lower()
    sensitive_kws = {"password", "passcode", "pin", "secret", "cvv", "ssn", "otp", "api_key", "apikey", "token"}
    if any(kw in lower_id for kw in sensitive_kws):
        return "Safety Block: Autonomous typing into sensitive credential/password fields is blocked. Human interaction required."

    click_res = click_element(element_id)
    if isinstance(click_res, str) and click_res.startswith("Error:"):
        return click_res

    return type_text(text)



def press_key(key):
    """Presses a single key."""
    if not key or not isinstance(key, str):
        return "Error: Key parameter cannot be empty."

    clean_key = key.strip().lower()
    if clean_key not in VALID_KEYS:
        return f"Error: Key '{key}' is not in the validated key allowlist."

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.press(clean_key)
        elif HAS_PYNPUT and key_ctrl:
            k_obj = PYNPUT_KEY_MAP.get(clean_key, clean_key)
            key_ctrl.tap(k_obj)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"key": clean_key}
    except Exception as e:
        return f"Error pressing key '{clean_key}': {str(e)}"


def hotkey(keys):
    """Presses a key combination (e.g. ['ctrl', 'c'])."""
    if not keys or not isinstance(keys, (list, tuple)):
        return "Error: Keys parameter must be a list of valid key names."

    clean_keys = [str(k).strip().lower() for k in keys]
    for k in clean_keys:
        if k not in VALID_KEYS:
            return f"Error: Key '{k}' in hotkey combination is not in the validated key allowlist."

    try:
        if HAS_PYAUTOGUI and pyautogui is not None:
            pyautogui.hotkey(*clean_keys)
        elif HAS_PYNPUT and key_ctrl:
            k_objs = [PYNPUT_KEY_MAP.get(k, k) for k in clean_keys]
            for k in k_objs:
                key_ctrl.press(k)
            for k in reversed(k_objs):
                key_ctrl.release(k)
        else:
            return "Error: Desktop input library (pyautogui/pynput) is not available."
        return {"hotkey": clean_keys}
    except Exception as e:
        return f"Error executing hotkey {clean_keys}: {str(e)}"


# ----------------------------------------------------------------------
# Stage 8F Safe Semantic Action Wrappers
# ----------------------------------------------------------------------

def click_semantic_element(role=None, label=None, text=None, element_id=None):
    """
    Stage 8F — Safe semantic element click wrapper.
    Resolves target via TargetResolver against fused perception before clicking.
    """
    if element_id and not role and not label and not text:
        return click_element(element_id)

    from core.perception import default_perception_router
    from core.target_resolver import default_target_resolver
    perc = default_perception_router.perceive()
    status, elem, reason = default_target_resolver.resolve(
        elements=perc.ui_elements,
        role=role,
        label=label,
        text=text,
        observation_timestamp=perc.timestamp
    )

    if status != "RESOLVED" or not elem:
        return f"Error: Target resolution failed ({status}): {reason}"

    center = elem.center_coordinates()
    return click_mouse(center["x"], center["y"])


def type_into_semantic_element(text, role=None, label=None, element_id=None):
    """
    Stage 8F — Safe semantic element text typing wrapper.
    Resolves target, clicks to focus, then types text.
    """
    if element_id and not role and not label:
        return type_in_element(element_id, text)

    from core.perception import default_perception_router
    from core.target_resolver import default_target_resolver
    perc = default_perception_router.perceive()
    status, elem, reason = default_target_resolver.resolve(
        elements=perc.ui_elements,
        role=role or "textbox",
        label=label,
        observation_timestamp=perc.timestamp
    )

    if status != "RESOLVED" or not elem:
        return f"Error: Target resolution failed ({status}): {reason}"

    center = elem.center_coordinates()
    click_res = click_mouse(center["x"], center["y"])
    if isinstance(click_res, str) and "Error" in click_res:
        return click_res
    return type_text(text)


def focus_semantic_element(role=None, label=None, element_id=None):
    """Focuses a target UI element by clicking its center bounds."""
    return click_semantic_element(role=role, label=label, element_id=element_id)


def select_semantic_element(option, role="dropdown", label=None):
    """Selects an option from a dropdown UI element."""
    c_res = click_semantic_element(role=role, label=label)
    if isinstance(c_res, str) and "Error" in c_res:
        return c_res
    return type_text(option)


