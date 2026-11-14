"""
Brain Tool Response Formatter.
Single source of truth for converting tool execution observation dictionaries
into standardized, human-readable feedback strings across all execution paths.
"""

import json
from typing import Dict, Any, Optional

APP_DISPLAY_NAMES = {
    "brave": "Brave",
    "brave browser": "Brave",
    "browser": "Brave",
    "file_manager": "File Manager",
    "thunar": "File Manager",
    "files": "File Manager",
    "terminal": "Terminal",
    "console": "Terminal",
    "text_editor": "Text Editor",
    "editor": "Text Editor",
    "calculator": "Calculator",
    "calc": "Calculator",
}


def format_tool_response(tool_name: str, result: Dict[str, Any], args: Optional[Dict[str, Any]] = None) -> str:
    """
    Produces standardized, consistent user-facing response strings for any tool output.
    Used identically by execute_plan() and _raw_run_planner_task() fast paths.
    """
    if not isinstance(result, dict):
        return str(result or "Task completed successfully.")

    args = args or {}
    tool_upper = str(tool_name).upper()
    is_success = bool(result.get("success", False))

    if not is_success:
        err_str = str(result.get("error", "Unknown error"))
        if err_str.startswith("Error:"):
            return err_str
        return f"Brain Error: Action '{tool_upper}' failed ({err_str}). Plan halted."

    if tool_upper == "TIME":
        return str(result.get("data") or "Current time retrieved.")

    if tool_upper == "OPEN_APP":
        data_val = result.get("data", {})
        app_title = ""
        if isinstance(data_val, dict) and data_val.get("name"):
            app_title = data_val["name"]
        elif isinstance(data_val, str) and data_val.strip() and not data_val.startswith("{"):
            app_title = data_val.strip()

        if not app_title:
            raw_name = args.get("app_name") or args.get("name") or ""
            app_title = APP_DISPLAY_NAMES.get(str(raw_name).lower(), str(raw_name).title() if raw_name else "Application")

        if app_title.lower().startswith("brave"):
            app_title = "Brave"

        return f"{app_title} is open."

    if tool_upper == "CLOSE_APP":
        return str(result.get("data") or "Application closed.")

    if tool_upper == "FOCUS_APP":
        raw_name = args.get("app_name") or args.get("name") or ""
        app_title = APP_DISPLAY_NAMES.get(str(raw_name).lower(), str(raw_name).title() if raw_name else "Application")
        return f"{app_title} window is focused."

    if tool_upper == "LIST_APPS":
        apps_data = result.get("data", {}).get("apps", []) if isinstance(result.get("data"), dict) else []
        if apps_data:
            lines = ["Installed GUI applications:\n"]
            for app in apps_data:
                name = app.get("name") if isinstance(app, dict) else str(app)
                lines.append(f"- {name}")
            return "\n".join(lines)
        return "No installed GUI applications discovered."

    if tool_upper == "SCREENSHOT":
        return "Screenshot captured successfully."

    if tool_upper in ("LIST_FILES", "FIND_FILES", "READ_TEXT_FILE"):
        data = result.get("data")
        return f"Here are the file results: {data if isinstance(data, str) else json.dumps(data)}"

    if tool_upper == "READ_WEB_PAGE":
        data = result.get("data") or result.get("content")
        return str(data or "Webpage read successfully.")

    if tool_upper == "DEEP_RESEARCH":
        summary = result.get("retrieved_summary") or result.get("data")
        sources = result.get("sources", [])
        src_text = f"\n\nSources:\n" + "\n".join(f"- {s}" for s in sources[:3]) if sources else ""
        return f"Research Findings:\n{summary}{src_text}"

    if tool_upper in ("WEB_SEARCH", "BROWSER_SEARCH"):
        raw_res = result.get("data") or result.get("results")
        if isinstance(raw_res, dict) and "results" in raw_res:
            raw_res = raw_res["results"]
        if isinstance(raw_res, list):
            bullet_pts = []
            for item in raw_res[:5]:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    snip = item.get("snippet", "")
                    bullet_pts.append(f"- {title}: {snip}")
                else:
                    bullet_pts.append(f"- {item}")
            return "Search results:\n" + "\n".join(bullet_pts)
        if isinstance(raw_res, str) and raw_res.startswith("Search results for"):
            return raw_res
        return f"Search results:\n{raw_res}"

    if tool_upper == "CHECK_DISK_SPACE":
        return str(result.get("data") or "Disk space checked successfully.")

    if tool_upper == "ANALYZE_SCREEN":
        raw_d = result.get("data")
        if isinstance(raw_d, str) and raw_d:
            return raw_d
        if isinstance(raw_d, dict) and isinstance(raw_d.get("data"), str):
            return raw_d.get("data")

        elems = result.get("elements", []) or (raw_d.get("elements", []) if isinstance(raw_d, dict) else [])
        perc = result.get("perception") or (raw_d.get("perception", {}) if isinstance(raw_d, dict) else {})
        detected_texts = perc.get("detected_text") or [e.get("text") for e in elems if isinstance(e, dict) and e.get("text")]
        if detected_texts:
            sample = ", ".join(f"'{t}'" for t in detected_texts[:8])
            return f"I observed the screen ({len(elems)} elements detected, state: {perc.get('screen_state', 'NORMAL')}). Visible content includes: {sample}."
        return f"Screen analyzed. Found {len(elems)} visible elements."

    return str(result.get("data") or "Task completed successfully.")
