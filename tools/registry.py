from tools.apps import open_app, close_app, focus_app, APPROVED_APPS
from tools.app_launcher import launch_app, list_apps
from tools.system_control import (
    volume_up, volume_down, volume_mute,
    brightness_up, brightness_down, lock_screen,
    wifi_status, wifi_on, wifi_off,
    bluetooth_status, bluetooth_on, bluetooth_off,
    get_system_info, memory_status, disk_status, cpu_status,
    shutdown, restart, suspend, logout
)
from tools.window_manager import (
    list_windows, focus_window, minimize_window, maximize_window,
    restore_window, close_window, move_window, resize_window
)
from tools.search import perform_web_search
from tools.files import (
    list_files, find_files, read_text_file, create_folder,
    create_file, copy_file, move_file, rename_file, file_info, delete_file
)
from tools.screen import capture_screen, analyze_captured_screen, ocr_screen, capture_screen_region
from tools.vision import default_vision
from tools.browser import (
    browser_search, browser_navigate, browser_search_foreground, click_first_search_result,
    browser_new_tab, browser_download, browser_open, browser_back, browser_forward,
    browser_reload, browser_title, browser_url, browser_find_text, browser_extract_text,
    browser_click, browser_fill, browser_press, browser_select, browser_scroll_page,
    browser_wait, browser_close_tab, browser_switch_tab, browser_list_tabs
)
from tools.time_tool import get_current_time
from tools.input import (
    move_mouse, click_mouse, double_click, scroll,
    type_text, press_key, hotkey, click_element, type_in_element,
    right_click, get_screen_size, get_active_window,
    default_chain_tracker
)




class Tool:
    """Represents a registered tool with metadata, safety parameters, and execution logic."""
    def __init__(self, name, description, parameters, risk_level, func):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.risk_level = risk_level  # "LOW" or "MEDIUM"
        self.func = func

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "risk_level": self.risk_level
        }


class ToolRegistry:
    """Centralized tool registry acting as single source of truth for available actions."""
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name.upper()] = tool

    def get(self, name):
        if not name or not isinstance(name, str):
            return None
        return self._tools.get(name.upper())

    def has_tool(self, name):
        if not name or not isinstance(name, str):
            return False
        return name.upper() in self._tools

    def list_tools(self):
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, tool_name, arguments):
        """
        Executes a registered tool with safety validation and action verification contract (Stage 6E/6O).
        Returns structured result dict:
          {"success": bool, "status": str, "tool": str, "data": ..., "error": ..., "observation_id": ...}
        """
        tool = self.get(tool_name)
        if not tool:
            return {
                "success": False,
                "status": "failed",
                "tool": tool_name,
                "data": None,
                "error": f"Tool '{tool_name}' is not registered in the tool registry."
            }

        if not isinstance(arguments, dict):
            return {
                "success": False,
                "status": "failed",
                "tool": tool_name,
                "data": None,
                "error": f"Invalid arguments format for tool '{tool_name}'. Expected dictionary."
            }

        # Stage 6O: Stale observation protection check
        expected_obs_id = arguments.get("expected_observation_id")
        if expected_obs_id:
            current_obs = default_vision.get_current_observation()
            if current_obs:
                cur_obs_id = current_obs.get("observation_id")
                obs_time = current_obs.get("timestamp", 0)
                import time
                if (cur_obs_id and cur_obs_id != expected_obs_id) or (time.time() - obs_time > 15.0):
                    from tools.screen import analyze_captured_screen
                    analyze_captured_screen(force_refresh=True)

        from tools.input import validate_gui_action_safety
        is_safe, safety_err = validate_gui_action_safety(tool.name, arguments)
        if not is_safe:
            return {
                "success": False,
                "status": "blocked",
                "tool": tool.name,
                "data": None,
                "error": safety_err
            }

        try:
            # Map parameters based on tool function signature
            if tool.name == "OPEN_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "LIST_APPS":
                result = tool.func()
            elif tool.name == "CLOSE_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "FOCUS_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "LIST_WINDOWS":
                result = tool.func()
            elif tool.name == "FOCUS_WINDOW":
                target = arguments.get("target") or arguments.get("window") or arguments.get("name") or ""
                result = tool.func(target)
            elif tool.name == "MINIMIZE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or arguments.get("name") or ""
                result = tool.func(target)
            elif tool.name == "MAXIMIZE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or arguments.get("name") or ""
                result = tool.func(target)
            elif tool.name == "RESTORE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or arguments.get("name") or ""
                result = tool.func(target)
            elif tool.name == "CLOSE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or arguments.get("name") or ""
                conf = arguments.get("confirmed", False)
                result = tool.func(target, confirmed=conf)
            elif tool.name == "MOVE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or ""
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = tool.func(target, x, y)
            elif tool.name == "RESIZE_WINDOW":
                target = arguments.get("target") or arguments.get("window") or ""
                w = arguments.get("width", 800)
                h = arguments.get("height", 600)
                result = tool.func(target, w, h)
            elif tool.name == "BROWSER_SEARCH":
                query = arguments.get("query") or arguments.get("keywords") or ""
                mode = arguments.get("mode", "AUTO")
                result = tool.func(query, mode=mode)
            elif tool.name == "BROWSER_NAVIGATE":
                url = arguments.get("url") or arguments.get("link") or ""
                mode = arguments.get("mode", "AUTO")
                result = tool.func(url, mode=mode)
            elif tool.name == "BROWSER_OPEN":
                url = arguments.get("url") or ""
                result = tool.func(url=url)
            elif tool.name == "BROWSER_BACK":
                result = tool.func()
            elif tool.name == "BROWSER_FORWARD":
                result = tool.func()
            elif tool.name == "BROWSER_RELOAD":
                result = tool.func()
            elif tool.name == "BROWSER_TITLE":
                result = tool.func()
            elif tool.name == "BROWSER_URL":
                result = tool.func()
            elif tool.name == "BROWSER_FIND_TEXT":
                text = arguments.get("text") or arguments.get("query") or ""
                result = tool.func(text)
            elif tool.name == "BROWSER_EXTRACT_TEXT":
                sel = arguments.get("selector", "body")
                result = tool.func(selector=sel)
            elif tool.name == "BROWSER_CLICK":
                sel = arguments.get("selector") or arguments.get("target") or ""
                result = tool.func(sel)
            elif tool.name == "BROWSER_FILL":
                sel = arguments.get("selector") or arguments.get("target") or ""
                text = arguments.get("text") or ""
                result = tool.func(sel, text)
            elif tool.name == "BROWSER_PRESS":
                key = arguments.get("key") or ""
                result = tool.func(key)
            elif tool.name == "BROWSER_SELECT":
                sel = arguments.get("selector") or ""
                opt = arguments.get("option") or ""
                result = tool.func(sel, opt)
            elif tool.name == "BROWSER_SCROLL":
                dir_str = arguments.get("direction", "down")
                amt = arguments.get("amount", 500)
                result = tool.func(direction=dir_str, amount=amt)
            elif tool.name == "BROWSER_WAIT":
                sec = arguments.get("seconds", 1.0)
                result = tool.func(seconds=sec)
            elif tool.name == "BROWSER_CLOSE_TAB":
                result = tool.func()
            elif tool.name == "BROWSER_SWITCH_TAB":
                idx = arguments.get("tab_index", 1)
                result = tool.func(tab_index=idx)
            elif tool.name == "BROWSER_LIST_TABS":
                result = tool.func()
            elif tool.name == "WEB_SEARCH":
                query = arguments.get("query") or arguments.get("keywords") or ""
                result = tool.func(query)
            elif tool.name in ("LIST_FILES", "LIST_DIRECTORY"):
                path = arguments.get("target_path") or arguments.get("path") or arguments.get("location") or "Brain"
                result = tool.func(path)
            elif tool.name in ("FIND_FILES", "SEARCH_FILES"):
                pattern = arguments.get("pattern") or arguments.get("query") or "*.py"
                root = arguments.get("search_root") or arguments.get("location") or "Brain"
                result = tool.func(pattern, root)
            elif tool.name == "READ_TEXT_FILE":
                filepath = arguments.get("filepath") or arguments.get("path") or arguments.get("file") or ""
                result = tool.func(filepath)
            elif tool.name == "CREATE_FOLDER":
                folder_name = arguments.get("folder_name") or arguments.get("name") or ""
                parent_root = arguments.get("parent_root") or arguments.get("parent") or arguments.get("location") or "Downloads"
                result = tool.func(folder_name, parent_root)
            elif tool.name == "CREATE_FILE":
                file_name = arguments.get("file_name") or arguments.get("name") or ""
                parent_root = arguments.get("parent_root") or arguments.get("location") or "Downloads"
                result = tool.func(file_name, parent_root=parent_root)
            elif tool.name == "COPY_FILE":
                src = arguments.get("source") or arguments.get("src") or ""
                dst = arguments.get("destination") or arguments.get("dst") or ""
                conf = arguments.get("confirmed", False)
                result = tool.func(src, dst, confirmed=conf)
            elif tool.name == "MOVE_FILE":
                src = arguments.get("source") or arguments.get("src") or ""
                dst = arguments.get("destination") or arguments.get("dst") or ""
                conf = arguments.get("confirmed", False)
                result = tool.func(src, dst, confirmed=conf)
            elif tool.name == "RENAME_FILE":
                src = arguments.get("source") or arguments.get("src") or ""
                new_name = arguments.get("new_name") or arguments.get("name") or ""
                conf = arguments.get("confirmed", False)
                result = tool.func(src, new_name, confirmed=conf)
            elif tool.name == "FILE_INFO":
                tpath = arguments.get("target_path") or arguments.get("path") or ""
                result = tool.func(tpath)
            elif tool.name == "DELETE_FILE":
                tpath = arguments.get("target_path") or arguments.get("path") or ""
                conf = arguments.get("confirmed", False)
                result = tool.func(tpath, confirmed=conf)
            elif tool.name == "SCREENSHOT":
                result = tool.func()
            elif tool.name == "TIME":
                result = tool.func()
            elif tool.name == "MOVE_MOUSE":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = tool.func(x, y)
            elif tool.name == "CLICK":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                btn = arguments.get("button", "left")
                result = tool.func(x, y, btn)
            elif tool.name == "RIGHT_CLICK":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = tool.func(x, y)
            elif tool.name == "DOUBLE_CLICK":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = tool.func(x, y)
            elif tool.name == "SCREEN_SIZE":
                result = tool.func()
            elif tool.name == "ACTIVE_WINDOW":
                result = tool.func()
            elif tool.name == "OCR_SCREEN":
                result = tool.func()
            elif tool.name == "SCREEN_REGION":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                w = arguments.get("width", 100)
                h = arguments.get("height", 100)
                result = tool.func(x, y, w, h)
            elif tool.name == "SCROLL":
                amount = arguments.get("amount", 0)
                result = tool.func(amount)
            elif tool.name == "TYPE_TEXT":
                text = arguments.get("text", "")
                result = tool.func(text)
            elif tool.name == "PRESS_KEY":
                key = arguments.get("key") or arguments.get("keys") or ""
                if isinstance(key, list):
                    result = hotkey(key)
                else:
                    result = tool.func(key)
            elif tool.name == "HOTKEY":
                keys = arguments.get("keys") or arguments.get("key") or []
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split("+")]
                result = tool.func(keys)
            elif tool.name == "ANALYZE_SCREEN":
                img_path = arguments.get("image_path") or arguments.get("path")
                result = tool.func(img_path)
            elif tool.name == "CLICK_ELEMENT":
                elem_id = arguments.get("element_id") or arguments.get("id") or ""
                btn = arguments.get("button", "left")
                result = tool.func(elem_id, button=btn)
            elif tool.name == "TYPE_IN_ELEMENT":
                elem_id = arguments.get("element_id") or arguments.get("id") or ""
                text = arguments.get("text", "")
                result = tool.func(elem_id, text)
            elif tool.name == "REMEMBER":
                m_type = arguments.get("memory_type") or arguments.get("type") or "FACT"
                sub = arguments.get("subject") or "user"
                k = arguments.get("key") or arguments.get("name") or ""
                v = arguments.get("value") or arguments.get("content") or ""
                result = tool.func(m_type, sub, k, v)
            elif tool.name == "CHECK_DISK_SPACE":
                target_path = arguments.get("target_path") or "/"
                result = tool.func(target_path)
            elif tool.name == "NEW_TAB":
                result = tool.func()
            else:
                result = tool.func(**arguments)

            # Record action in ActionChainTracker
            default_chain_tracker.record_action(tool.name, arguments, result)

            # Determine success and status based on tool return content (Stage 6E contract)
            if isinstance(result, dict):
                is_success = result.get("success", True)
                explicit_status = result.get("status")
                if not is_success:
                    status_str = explicit_status or "failed"
                    err_msg = result.get("error", "Tool execution reported failure.")
                else:
                    status_str = explicit_status or "executed_unverified"
                    err_msg = None

                res_dict = {
                    "success": is_success,
                    "status": status_str,
                    "tool": tool.name,
                    "data": result.get("data", result),
                    "error": err_msg
                }
                if isinstance(result, dict) and "matches" in result:
                    res_dict["matches"] = result["matches"]
                return res_dict

            if isinstance(result, str) and (result.startswith("Error:") or result.startswith("Access Denied:") or result.startswith("Safety Block:") or result.startswith("Brain Error:") or result.startswith("Memory Error:")):
                return {
                    "success": False,
                    "status": "failed" if not result.startswith("Safety Block:") else "blocked",
                    "tool": tool.name,
                    "data": None,
                    "error": result
                }

            return {
                "success": True,
                "status": "executed_unverified",
                "tool": tool.name,
                "data": result,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "tool": tool.name,
                "data": None,
                "error": f"Unexpected execution error in tool '{tool.name}': {str(e)}"
            }



# Default global tool registry instance
default_registry = ToolRegistry()

# Register Phase 1-3 Tools
default_registry.register(Tool(
    name="OPEN_APP",
    description="Launches an installed GUI application by name (e.g. Firefox, Brave, Calculator).",
    parameters={"name": "string"},
    risk_level="MEDIUM",
    func=launch_app
))

default_registry.register(Tool(
    name="LIST_APPS",
    description="Lists installed GUI applications on the system.",
    parameters={},
    risk_level="LOW",
    func=list_apps
))

# Register System Control Tools
default_registry.register(Tool("VOLUME_UP", "Increases master audio volume.", {"step_percent": "integer (default: 5)"}, "LOW", volume_up))
default_registry.register(Tool("VOLUME_DOWN", "Decreases master audio volume.", {"step_percent": "integer (default: 5)"}, "LOW", volume_down))
default_registry.register(Tool("VOLUME_MUTE", "Toggles master audio mute.", {}, "LOW", volume_mute))
default_registry.register(Tool("BRIGHTNESS_UP", "Increases display brightness.", {"step_percent": "integer (default: 10)"}, "LOW", brightness_up))
default_registry.register(Tool("BRIGHTNESS_DOWN", "Decreases display brightness.", {"step_percent": "integer (default: 10)"}, "LOW", brightness_down))
default_registry.register(Tool("LOCK_SCREEN", "Locks the desktop screen.", {}, "LOW", lock_screen))
default_registry.register(Tool("WIFI_STATUS", "Returns Wi-Fi radio status.", {}, "LOW", wifi_status))
default_registry.register(Tool("WIFI_ON", "Enables Wi-Fi adapter.", {}, "MEDIUM", wifi_on))
default_registry.register(Tool("WIFI_OFF", "Disables Wi-Fi adapter.", {}, "MEDIUM", wifi_off))
default_registry.register(Tool("BLUETOOTH_STATUS", "Returns Bluetooth radio status.", {}, "LOW", bluetooth_status))
default_registry.register(Tool("BLUETOOTH_ON", "Enables Bluetooth adapter.", {}, "MEDIUM", bluetooth_on))
default_registry.register(Tool("BLUETOOTH_OFF", "Disables Bluetooth adapter.", {}, "MEDIUM", bluetooth_off))
default_registry.register(Tool("SYSTEM_INFO", "Returns OS distro, kernel, and machine architecture info.", {}, "LOW", get_system_info))
default_registry.register(Tool("MEMORY_STATUS", "Returns RAM usage metrics.", {}, "LOW", memory_status))
default_registry.register(Tool("DISK_STATUS", "Returns filesystem disk space metrics.", {"target_path": "string (default: /)"}, "LOW", disk_status))
default_registry.register(Tool("CPU_STATUS", "Returns CPU core count and utilization percentage.", {}, "LOW", cpu_status))
default_registry.register(Tool("SHUTDOWN", "Triggers system power off (Confirmation Gated).", {"confirmed": "boolean"}, "HIGH", shutdown))
default_registry.register(Tool("RESTART", "Triggers system reboot (Confirmation Gated).", {"confirmed": "boolean"}, "HIGH", restart))
default_registry.register(Tool("SUSPEND", "Triggers system suspend/sleep (Confirmation Gated).", {"confirmed": "boolean"}, "HIGH", suspend))
default_registry.register(Tool("LOGOUT", "Triggers desktop session logout (Confirmation Gated).", {"confirmed": "boolean"}, "HIGH", logout))

# Register Phase 2 Window Management Tools
default_registry.register(Tool("LIST_WINDOWS", "Lists open desktop application windows.", {}, "LOW", list_windows))
default_registry.register(Tool("FOCUS_WINDOW", "Focuses an open window by ID or title.", {"target": "string"}, "LOW", focus_window))
default_registry.register(Tool("MINIMIZE_WINDOW", "Minimizes a window by ID or title.", {"target": "string"}, "LOW", minimize_window))
default_registry.register(Tool("MAXIMIZE_WINDOW", "Maximizes a window by ID or title.", {"target": "string"}, "LOW", maximize_window))
default_registry.register(Tool("RESTORE_WINDOW", "Restores a window to unmaximized state by ID or title.", {"target": "string"}, "LOW", restore_window))
default_registry.register(Tool("CLOSE_WINDOW", "Closes a window by ID or title (Confirmation Gated).", {"target": "string", "confirmed": "boolean"}, "MEDIUM", close_window))
default_registry.register(Tool("MOVE_WINDOW", "Moves a window to (x, y) screen coordinates.", {"target": "string", "x": "integer", "y": "integer"}, "LOW", move_window))
default_registry.register(Tool("RESIZE_WINDOW", "Resizes a window to width x height dimensions.", {"target": "string", "width": "integer", "height": "integer"}, "LOW", resize_window))

default_registry.register(Tool(
    name="WEB_SEARCH",
    description="Searches the web for keywords using DuckDuckGo HTML endpoint.",
    parameters={"query": "string"},
    risk_level="LOW",
    func=perform_web_search
))

default_registry.register(Tool(
    name="LIST_FILES",
    description="Lists files and subdirectories in a directory path or alias (e.g. Brain, Downloads). MANDATORY choice for general requests to list, view, or show directory contents (e.g. 'List files in my Brain project').",
    parameters={"target_path": "string (default: Brain)"},
    risk_level="LOW",
    func=list_files
))

default_registry.register(Tool(
    name="FIND_FILES",
    description="Searches for specific files matching an explicit wildcard or extension pattern (e.g. *.py, *.pdf, *.json). NEVER use for general directory listing requests without a search pattern.",
    parameters={"pattern": "string", "search_root": "string (default: Brain)"},
    risk_level="LOW",
    func=find_files
))

default_registry.register(Tool(
    name="READ_TEXT_FILE",
    description="Reads content from an allowed text file (.txt, .md, .py, .json, .yaml, .csv, etc.) under 1 MB.",
    parameters={"filepath": "string"},
    risk_level="LOW",
    func=read_text_file
))

default_registry.register(Tool(
    name="CREATE_FOLDER",
    description="Creates a new folder inside an approved safe directory.",
    parameters={"folder_name": "string", "parent_root": "string (default: Downloads)"},
    risk_level="MEDIUM",
    func=create_folder
))

default_registry.register(Tool(
    name="LIST_DIRECTORY",
    description="Lists files and subdirectories in a directory path inside safe directories.",
    parameters={"target_path": "string"},
    risk_level="LOW",
    func=list_files
))

default_registry.register(Tool(
    name="CREATE_FILE",
    description="Creates a new empty file inside safe directories.",
    parameters={"file_name": "string", "parent_root": "string (default: Downloads)"},
    risk_level="MEDIUM",
    func=create_file
))

default_registry.register(Tool(
    name="COPY_FILE",
    description="Copies a file or directory from source to destination inside safe directories.",
    parameters={"source": "string", "destination": "string"},
    risk_level="MEDIUM",
    func=copy_file
))

default_registry.register(Tool(
    name="MOVE_FILE",
    description="Moves a file or directory from source to destination inside safe directories.",
    parameters={"source": "string", "destination": "string"},
    risk_level="MEDIUM",
    func=move_file
))

default_registry.register(Tool(
    name="RENAME_FILE",
    description="Renames a file or directory inside safe directories.",
    parameters={"source": "string", "new_name": "string"},
    risk_level="MEDIUM",
    func=rename_file
))

default_registry.register(Tool(
    name="SEARCH_FILES",
    description="Searches for files matching a pattern inside safe root directories.",
    parameters={"pattern": "string", "search_root": "string"},
    risk_level="LOW",
    func=find_files
))

default_registry.register(Tool(
    name="FILE_INFO",
    description="Inspects file metadata (size, modification time, permissions).",
    parameters={"target_path": "string"},
    risk_level="LOW",
    func=file_info
))

default_registry.register(Tool(
    name="DELETE_FILE",
    description="Deletes a file or directory inside safe directories (Confirmation Gated).",
    parameters={"target_path": "string", "confirmed": "boolean"},
    risk_level="HIGH",
    func=delete_file
))

# Register Phase 5 Desktop Interaction Tools
default_registry.register(Tool(
    name="SCREENSHOT",
    description="Captures the desktop screen and stores a temporary image.",
    parameters={},
    risk_level="LOW",
    func=capture_screen
))

default_registry.register(Tool(
    name="MOVE_MOUSE",
    description="Moves the mouse cursor to (x, y) coordinates.",
    parameters={"x": "integer", "y": "integer"},
    risk_level="MEDIUM",
    func=move_mouse
))

default_registry.register(Tool(
    name="CLICK",
    description="Clicks the mouse at (x, y) coordinates.",
    parameters={"x": "integer", "y": "integer", "button": "string (default: left)"},
    risk_level="MEDIUM",
    func=click_mouse
))

default_registry.register(Tool(
    name="DOUBLE_CLICK",
    description="Double-clicks the mouse at (x, y) coordinates.",
    parameters={"x": "integer", "y": "integer"},
    risk_level="MEDIUM",
    func=double_click
))

default_registry.register(Tool(
    name="SCROLL",
    description="Scrolls the desktop window up (positive) or down (negative).",
    parameters={"amount": "integer (-1000 to 1000)"},
    risk_level="MEDIUM",
    func=scroll
))

default_registry.register(Tool(
    name="TYPE_TEXT",
    description="Types text into the active window (max 2,000 chars). Does not execute terminal commands.",
    parameters={"text": "string"},
    risk_level="MEDIUM",
    func=type_text
))

default_registry.register(Tool(
    name="PRESS_KEY",
    description="Presses a single key (e.g. enter, tab, space, escape, backspace).",
    parameters={"key": "string"},
    risk_level="MEDIUM",
    func=press_key
))

default_registry.register(Tool(
    name="HOTKEY",
    description="Presses a key combination (e.g. ['ctrl', 'c']).",
    parameters={"keys": "list of strings"},
    risk_level="MEDIUM",
    func=hotkey
))

# Phase 5 Desktop Control & Observation Tools
default_registry.register(Tool("RIGHT_CLICK", "Right-clicks the mouse at (x, y) coordinates.", {"x": "integer", "y": "integer"}, "MEDIUM", right_click))
default_registry.register(Tool("SCREEN_SIZE", "Returns desktop screen width and height.", {}, "LOW", get_screen_size))
default_registry.register(Tool("ACTIVE_WINDOW", "Returns active window title, class, and geometry.", {}, "LOW", get_active_window))
default_registry.register(Tool("OCR_SCREEN", "Runs on-demand OCR text extraction on desktop screen.", {}, "LOW", ocr_screen))
default_registry.register(Tool("SCREEN_REGION", "Captures a rectangular region of the screen.", {"x": "integer", "y": "integer", "width": "integer", "height": "integer"}, "LOW", capture_screen_region))

# Register Phase 6 Vision & Element Interaction Tools
default_registry.register(Tool(
    name="ANALYZE_SCREEN",
    description="Captures the desktop screen and analyzes visible elements. Use ONLY when visual screen information is required for a GUI task or requested by user. Do NOT call for general conversation.",
    parameters={"image_path": "string (optional)"},
    risk_level="LOW",
    func=analyze_captured_screen
))


default_registry.register(Tool(
    name="CLICK_ELEMENT",
    description="Clicks a detected UI element by its ID or text label from the current screen observation.",
    parameters={"element_id": "string", "button": "string (default: left)"},
    risk_level="MEDIUM",
    func=click_element
))

default_registry.register(Tool(
    name="TYPE_IN_ELEMENT",
    description="Clicks a detected UI element to focus it, then types the specified text.",
    parameters={"element_id": "string", "text": "string"},
    risk_level="MEDIUM",
    func=type_in_element
))

# Phase 9 Adaptive Capability Tools
default_registry.register(Tool(
    name="CLOSE_APP",
    description="Safely closes Brain-owned instances of an application (brave, terminal, file_manager, text_editor). Operates only on tracked Brain processes.",
    parameters={"app_name": "string (brave | terminal | file_manager | text_editor)"},
    risk_level="MEDIUM",
    func=close_app
))

default_registry.register(Tool(
    name="FOCUS_APP",
    description="Brings an open desktop application window to focus.",
    parameters={"app_name": "string (brave | terminal | file_manager | text_editor)"},
    risk_level="LOW",
    func=focus_app
))

default_registry.register(Tool(
    name="BROWSER_SEARCH",
    description="Capability tool to execute a web search query. Uses structured interaction by default (AUTO/BACKGROUND) or direct browser GUI controls (FOREGROUND).",
    parameters={"query": "string"},
    risk_level="LOW",
    func=browser_search
))

default_registry.register(Tool(
    name="BROWSER_SEARCH_FOREGROUND",
    description="Capability tool to execute a web search directly inside foreground Brave browser via address bar.",
    parameters={"query": "string"},
    risk_level="LOW",
    func=browser_search_foreground
))

default_registry.register(Tool(
    name="BROWSER_NAVIGATE",
    description="Capability tool to navigate to a URL.",
    parameters={"url": "string"},
    risk_level="LOW",
    func=browser_navigate
))

# Phase 4 Deterministic Browser Control Tools
default_registry.register(Tool("BROWSER_OPEN", "Opens browser to a URL or default start page.", {"url": "string"}, "LOW", browser_open))
default_registry.register(Tool("BROWSER_BACK", "Navigates back one page in browser history.", {}, "LOW", browser_back))
default_registry.register(Tool("BROWSER_FORWARD", "Navigates forward one page in browser history.", {}, "LOW", browser_forward))
default_registry.register(Tool("BROWSER_RELOAD", "Reloads current browser page.", {}, "LOW", browser_reload))
default_registry.register(Tool("BROWSER_TITLE", "Gets current browser page title.", {}, "LOW", browser_title))
default_registry.register(Tool("BROWSER_URL", "Gets current browser page URL.", {}, "LOW", browser_url))
default_registry.register(Tool("BROWSER_FIND_TEXT", "Finds text on active browser page.", {"text": "string"}, "LOW", browser_find_text))
default_registry.register(Tool("BROWSER_EXTRACT_TEXT", "Extracts structured text from browser DOM or element.", {"selector": "string"}, "LOW", browser_extract_text))
default_registry.register(Tool("BROWSER_CLICK", "Clicks a DOM element or button by selector.", {"selector": "string"}, "MEDIUM", browser_click))
default_registry.register(Tool("BROWSER_FILL", "Fills text into a DOM input element by selector.", {"selector": "string", "text": "string"}, "MEDIUM", browser_fill))
default_registry.register(Tool("BROWSER_PRESS", "Presses a key in active browser.", {"key": "string"}, "MEDIUM", browser_press))
default_registry.register(Tool("BROWSER_SELECT", "Selects an option from a dropdown element.", {"selector": "string", "option": "string"}, "LOW", browser_select))
default_registry.register(Tool("BROWSER_SCROLL", "Scrolls active browser page up or down.", {"direction": "string", "amount": "integer"}, "LOW", browser_scroll_page))
default_registry.register(Tool("BROWSER_WAIT", "Waits for page load or element readiness (0.1 to 10s).", {"seconds": "number"}, "LOW", browser_wait))
default_registry.register(Tool("BROWSER_CLOSE_TAB", "Closes active browser tab.", {}, "LOW", browser_close_tab))
default_registry.register(Tool("BROWSER_SWITCH_TAB", "Switches to browser tab by index (1..9).", {"tab_index": "integer"}, "LOW", browser_switch_tab))
default_registry.register(Tool("BROWSER_LIST_TABS", "Lists open browser tabs.", {}, "LOW", browser_list_tabs))

from tools.browser import browser_download
default_registry.register(Tool(
    name="BROWSER_DOWNLOAD",
    description="Capability tool for controlled browser downloads via Playwright.",
    parameters={"url": "string", "destination": "string (optional)"},
    risk_level="LOW",
    func=browser_download
))

default_registry.register(Tool(
    name="TIME",
    description="Returns the current local system time.",
    parameters={},
    risk_level="LOW",
    func=get_current_time
))


def remember_memory(memory_type="FACT", subject="user", key="", value=""):
    from core.memory import default_memory
    success, err = default_memory.add_memory(memory_type=memory_type, subject=subject, key=key, value=value)
    if not success:
        return f"Memory Error: {err}"
    return f"Remembered {memory_type.lower()}: {key} = {value}"


default_registry.register(Tool(
    name="REMEMBER",
    description="Stores a persistent user preference, fact, or decision into Brain's memory store.",
    parameters={"memory_type": "string (FACT | PREFERENCE | DECISION)", "key": "string", "value": "string", "subject": "string (default: user)"},
    risk_level="LOW",
    func=remember_memory
))


def check_disk_space(target_path="/"):
    import shutil
    try:
        total, used, free = shutil.disk_usage(target_path)
        total_gb = total / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        used_pct = (used / total) * 100
        return f"Disk space for '{target_path}': {free_gb:.1f} GB free of {total_gb:.1f} GB ({used_pct:.1f}% used)."
    except Exception as e:
        return f"Error reading disk usage: {e}"


default_registry.register(Tool(
    name="CHECK_DISK_SPACE",
    description="Inspects storage filesystem and returns total, used, and free disk space.",
    parameters={"target_path": "string (default: /)"},
    risk_level="LOW",
    func=check_disk_space
))

default_registry.register(Tool(
    name="CLICK_FIRST_RESULT",
    description="Clicks or navigates to the first search result on the screen or web browser.",
    parameters={"query": "string"},
    risk_level="LOW",
    func=click_first_search_result
))

default_registry.register(Tool(
    name="NEW_TAB",
    description="Opens a new tab in the active or default browser window.",
    parameters={},
    risk_level="LOW",
    func=browser_new_tab
))

# Register Phase 19 Structured DOM Computer-Use Tools
from tools.computer_use import dom_click, dom_type, dom_extract_content, dom_select_result, dom_get_page_state

default_registry.register(Tool(
    name="DOM_CLICK",
    description="Clicks a target DOM element on the active browser page by selector.",
    parameters={"selector": "string", "timeout": "number (default: 5.0)"},
    risk_level="MEDIUM",
    func=dom_click
))

default_registry.register(Tool(
    name="DOM_TYPE",
    description="Types text into a DOM input element by selector.",
    parameters={"selector": "string", "text": "string", "clear": "boolean (default: true)"},
    risk_level="MEDIUM",
    func=dom_type
))

default_registry.register(Tool(
    name="DOM_EXTRACT_CONTENT",
    description="Extracts structured text from a DOM element without OCR overhead.",
    parameters={"selector": "string (default: body)", "max_length": "integer (default: 2000)"},
    risk_level="LOW",
    func=dom_extract_content
))

default_registry.register(Tool(
    name="DOM_SELECT_RESULT",
    description="Selects and navigates to the best matching search result link on the active page.",
    parameters={"criteria": "string", "index": "integer (default: 0)"},
    risk_level="MEDIUM",
    func=dom_select_result
))

default_registry.register(Tool(
    name="DOM_PAGE_STATE",
    description="Inspects active browser DOM state: URL, title, readyState, and text length.",
    parameters={},
    risk_level="LOW",
    func=dom_get_page_state
))

# Register Stage 8F Safe Semantic Action Tools
from tools.input import click_semantic_element, type_into_semantic_element, focus_semantic_element, select_semantic_element

default_registry.register(Tool(
    name="CLICK_ELEMENT",
    description="Clicks a semantic UI element by role, label, text, or element_id.",
    parameters={"role": "string", "label": "string", "text": "string", "element_id": "string"},
    risk_level="LOW",
    func=click_semantic_element
))

default_registry.register(Tool(
    name="TYPE_INTO_ELEMENT",
    description="Types text into a semantic UI element by role, label, or element_id.",
    parameters={"text": "string", "role": "string (default: textbox)", "label": "string", "element_id": "string"},
    risk_level="MEDIUM",
    func=type_into_semantic_element
))

default_registry.register(Tool(
    name="FOCUS_ELEMENT",
    description="Focuses a target semantic UI element.",
    parameters={"role": "string", "label": "string", "element_id": "string"},
    risk_level="LOW",
    func=focus_semantic_element
))

default_registry.register(Tool(
    name="SELECT_ELEMENT",
    description="Selects an option from a dropdown UI element.",
    parameters={"option": "string", "role": "string (default: dropdown)", "label": "string"},
    risk_level="LOW",
    func=select_semantic_element
))


# ---------------------------------------------------------------------------
# Companion Control Tools (registered through safety registry)
# ---------------------------------------------------------------------------

def _companion_show(*args, **kwargs):
    """Ensure Desktop Mate window is visible and presence is applied."""
    try:
        from core.desktop_presence import DesktopPresenceManager
        mgr = DesktopPresenceManager()
        result = mgr.ensure_running()
        if result.get("success"):
            win_id = result.get("window_id")
            if win_id:
                mgr.apply_desktop_presence(win_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_hide(*args, **kwargs):
    """Minimize Desktop Mate companion window (does not kill process)."""
    try:
        import subprocess
        from core.desktop_presence import DesktopPresenceManager
        mgr = DesktopPresenceManager()
        win_id = mgr.get_window_id()
        if win_id:
            subprocess.run(["xdotool", "windowminimize", win_id], capture_output=True, timeout=3)
            return {"success": True, "status": "minimized", "window_id": win_id}
        return {"success": False, "error": "No Desktop Mate window found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_status(*args, **kwargs):
    """Return full companion status (process, window, bridge, mode, memory)."""
    try:
        from core.desktop_presence import DesktopPresenceManager
        from bridge.companion_mode import default_companion_mode
        mgr = DesktopPresenceManager()
        proc = mgr.is_process_running()
        win = mgr.get_window_id() if proc else None
        rss = mgr.get_memory_usage_mb() if proc else 0.0
        return {
            "success": True,
            "process_running": proc,
            "window_id": win,
            "rss_memory_mb": rss,
            "companion_mode": default_companion_mode.get_mode(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_mode_set(mode: str = "ACTIVE", **kwargs):
    """Set companion operating mode: ACTIVE, PASSIVE, SLEEPING, DISABLED."""
    try:
        from bridge.companion_mode import default_companion_mode
        return default_companion_mode.set_mode(mode.upper())
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_reset_position(*args, **kwargs):
    """Re-apply X11 window presence hints (always-on-top, sticky)."""
    try:
        from core.desktop_presence import DesktopPresenceManager
        mgr = DesktopPresenceManager()
        win_id = mgr.get_window_id()
        if win_id:
            ok = mgr.apply_desktop_presence(win_id)
            return {"success": ok, "window_id": win_id}
        return {"success": False, "error": "No Desktop Mate window found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_idle(*args, **kwargs):
    """Force companion back to neutral/idle state."""
    try:
        from bridge.desktopmate_bridge import DesktopMateBridge
        from core.companion_state import default_companion_state
        default_companion_state.set_state(activity="IDLE", status_text="Standing by")
        return {"success": True, "status": "idle_requested"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_happy(*args, **kwargs):
    """Set companion to happy expression."""
    try:
        from core.companion_state import default_companion_state
        default_companion_state.set_state(activity="SUCCESS", status_text="Happy!")
        return {"success": True, "status": "happy_requested"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_sleepy(*args, **kwargs):
    """Set companion to sleepy/relaxed state."""
    try:
        from core.companion_state import default_companion_state
        default_companion_mode_m = None
        try:
            from bridge.companion_mode import default_companion_mode
            default_companion_mode_m = default_companion_mode
        except Exception:
            pass
        default_companion_state.set_state(activity="SLEEPING", status_text="Sleeping...")
        if default_companion_mode_m:
            default_companion_mode_m.set_mode("SLEEPING")
        return {"success": True, "status": "sleepy_requested"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_look_at(target: str = "screen", **kwargs):
    """Set companion look-at target: mouse, screen, active_window, none."""
    try:
        from bridge.look_at import LookAtController, VALID_TARGETS
        from bridge.companion_mode import default_companion_mode
        t = str(target).lower().strip()
        if t not in VALID_TARGETS:
            return {"success": False, "error": f"Invalid target '{target}'. Valid: {sorted(VALID_TARGETS)}"}
        # We can't easily get bridge here without circular deps, so broadcast event
        from core.companion_state import default_companion_state
        default_companion_state.broadcast("COMPANION_EVENT", {"event": "LOOK_AT", "target": t})
        return {"success": True, "status": "look_at_requested", "target": t}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _companion_stop_speech(*args, **kwargs):
    """Stop active TTS speech immediately."""
    try:
        from core.voice import default_voice
        default_voice.interrupt()
        from core.companion_state import default_companion_state
        default_companion_state.set_state(activity="IDLE", status_text="Speech stopped", speaking=False)
        return {"success": True, "status": "speech_stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}


default_registry.register(Tool(
    name="COMPANION_SHOW",
    description="Show/ensure Desktop Mate companion is visible.",
    parameters={},
    risk_level="LOW",
    func=_companion_show
))

default_registry.register(Tool(
    name="COMPANION_HIDE",
    description="Minimize the Desktop Mate companion window (does not kill it).",
    parameters={},
    risk_level="LOW",
    func=_companion_hide
))

default_registry.register(Tool(
    name="COMPANION_STATUS",
    description="Get full status of Desktop Mate companion (process, window, bridge, mode, memory).",
    parameters={},
    risk_level="LOW",
    func=_companion_status
))

default_registry.register(Tool(
    name="COMPANION_MODE",
    description="Set companion operating mode. mode: ACTIVE, PASSIVE, SLEEPING, DISABLED.",
    parameters={"mode": "string (ACTIVE|PASSIVE|SLEEPING|DISABLED)"},
    risk_level="LOW",
    func=_companion_mode_set
))

default_registry.register(Tool(
    name="COMPANION_RESET_POSITION",
    description="Re-apply always-on-top and sticky X11 window hints for Desktop Mate.",
    parameters={},
    risk_level="LOW",
    func=_companion_reset_position
))

default_registry.register(Tool(
    name="COMPANION_IDLE",
    description="Return companion to idle/neutral state.",
    parameters={},
    risk_level="LOW",
    func=_companion_idle
))

default_registry.register(Tool(
    name="COMPANION_HAPPY",
    description="Set companion to happy expression.",
    parameters={},
    risk_level="LOW",
    func=_companion_happy
))

default_registry.register(Tool(
    name="COMPANION_SLEEPY",
    description="Set companion to sleepy mode.",
    parameters={},
    risk_level="LOW",
    func=_companion_sleepy
))

default_registry.register(Tool(
    name="COMPANION_LOOK_AT",
    description="Set companion look-at target. target: mouse, screen, active_window, none.",
    parameters={"target": "string (mouse|screen|active_window|none)"},
    risk_level="LOW",
    func=_companion_look_at
))

default_registry.register(Tool(
    name="COMPANION_STOP_SPEECH",
    description="Stop active TTS speech immediately.",
    parameters={},
    risk_level="LOW",
    func=_companion_stop_speech
))
