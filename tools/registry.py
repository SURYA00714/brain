from tools.apps import open_app, close_app, focus_app, APPROVED_APPS
from tools.search import perform_web_search
from tools.files import list_files, find_files, read_text_file, create_folder
from tools.screen import capture_screen, analyze_captured_screen
from tools.vision import default_vision
from tools.browser import browser_search, browser_navigate
from tools.time_tool import get_current_time
from tools.input import (
    move_mouse, click_mouse, double_click, scroll,
    type_text, press_key, hotkey, click_element, type_in_element,
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

    def list_tools(self):
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, tool_name, arguments):
        """
        Executes a registered tool with safety validation.
        Returns structured result dict: {"success": bool, "tool": str, "data": ..., "error": ...}
        """
        tool = self.get(tool_name)
        if not tool:
            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error": f"Tool '{tool_name}' is not registered in the tool registry."
            }

        if not isinstance(arguments, dict):
            return {
                "success": False,
                "tool": tool_name,
                "data": None,
                "error": f"Invalid arguments format for tool '{tool_name}'. Expected dictionary."
            }

        try:
            # Map parameters based on tool function signature
            if tool.name == "OPEN_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "CLOSE_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "FOCUS_APP":
                app_name = arguments.get("app_name") or arguments.get("app") or arguments.get("name") or ""
                result = tool.func(app_name)
            elif tool.name == "BROWSER_SEARCH":
                query = arguments.get("query") or arguments.get("keywords") or ""
                mode = arguments.get("mode", "AUTO")
                result = tool.func(query, mode=mode)
            elif tool.name == "BROWSER_NAVIGATE":
                url = arguments.get("url") or arguments.get("link") or ""
                mode = arguments.get("mode", "AUTO")
                result = tool.func(url, mode=mode)
            elif tool.name == "WEB_SEARCH":
                query = arguments.get("query") or arguments.get("keywords") or ""
                result = tool.func(query)
            elif tool.name == "LIST_FILES":
                path = arguments.get("target_path") or arguments.get("path") or arguments.get("location") or "Brain"
                result = tool.func(path)
            elif tool.name == "FIND_FILES":
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
            elif tool.name == "DOUBLE_CLICK":
                x = arguments.get("x", 0)
                y = arguments.get("y", 0)
                result = tool.func(x, y)
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
            else:
                result = tool.func(**arguments)


            # Record action in ActionChainTracker
            default_chain_tracker.record_action(tool.name, arguments, result)

            # Determine success based on tool return content
            if isinstance(result, dict) and not result.get("success", True):
                return {
                    "success": False,
                    "tool": tool.name,
                    "data": result.get("data"),
                    "error": result.get("error", "Tool execution reported failure.")
                }

            if isinstance(result, str) and (result.startswith("Error:") or result.startswith("Access Denied:") or result.startswith("Safety Block:") or result.startswith("Brain Error:")):
                return {
                    "success": False,
                    "tool": tool.name,
                    "data": None,
                    "error": result
                }

            return {
                "success": True,
                "tool": tool.name,
                "data": result,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "tool": tool.name,
                "data": None,
                "error": f"Unexpected execution error in tool '{tool.name}': {str(e)}"
            }


# Default global tool registry instance
default_registry = ToolRegistry()

# Register Phase 1-3 Tools
default_registry.register(Tool(
    name="OPEN_APP",
    description="Launches an approved desktop application (brave, terminal, file_manager, text_editor).",
    parameters={"app_name": "string (brave | terminal | file_manager | text_editor)"},
    risk_level="MEDIUM",
    func=open_app
))

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
    name="BROWSER_NAVIGATE",
    description="Capability tool to navigate to a URL.",
    parameters={"url": "string"},
    risk_level="LOW",
    func=browser_navigate
))

default_registry.register(Tool(
    name="TIME",
    description="Returns the current local system time.",
    parameters={},
    risk_level="LOW",
    func=get_current_time
))


