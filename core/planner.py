"""
Brain Planner & Prompt Builder.
Single source of truth for constructing planner system prompts, parsing LLM actions,
and formatting task context and tool definitions.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from brain_constants import APPROVED_BROWSER_KEYWORDS
from tools.registry import default_registry, ToolRegistry
from tools.vision import default_vision
from tools.plan import ExecutionPlan
from core.context import default_context_builder

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planner_template.txt"


def clean_search_query(user_text: str, extracted_query: str = "") -> str:
    """Cleans and extracts search query keywords from raw input or model output."""
    if extracted_query and extracted_query.strip():
        query = extracted_query.strip()
    else:
        query = user_text.strip() if user_text else ""

    patterns = [
        r"^(please\s+)?search(\s+the\s+web|\s+internet)?\s+for\s+",
        r"^(please\s+)?look\s+up\s+",
        r"^(please\s+)?find\s+information\s+about\s+",
        r"^(please\s+)?find\s+"
    ]
    for pattern in patterns:
        query = re.sub(pattern, "", query, flags=re.IGNORECASE).strip()

    return query if query else (user_text.strip() if user_text else "")


def is_visual_request(request_text: str) -> bool:
    """Checks if user request explicitly asks for screen analysis or visual information."""
    if not request_text or not isinstance(request_text, str):
        return False
    lowered = request_text.lower()
    visual_keywords = ["screen", "desktop", "display", "what can you see", "what do you see", "see on my", "look at my"]
    return any(kw in lowered for kw in visual_keywords)


def parse_model_action(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parses LLM output into a structured action dictionary.
    Action formats:
    - Tool call: {"type": "tool", "tool": "TOOL_NAME", "arguments": {...}}
    - Final answer: {"type": "final", "answer": "..."}
    Returns (action_dict, error_message).
    """
    if not response_text or not isinstance(response_text, str):
        return None, "Empty response from model."

    clean_text = response_text.strip()

    # Attempt 1: Direct JSON parsing
    try:
        data = json.loads(clean_text)
        if isinstance(data, dict) and "type" in data:
            action_type = str(data.get("type")).lower()
            if action_type == "final" and "answer" in data:
                return {"type": "final", "answer": str(data["answer"])}, None
            if action_type == "tool" and "tool" in data:
                tool_name = str(data.get("tool")).upper()
                args = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
                return {"type": "tool", "tool": tool_name, "arguments": args}, None
            if action_type == "plan" and ("steps" in data or "plan" in data):
                raw_p = data.get("plan") if isinstance(data.get("plan"), dict) else data
                plan_obj = ExecutionPlan.from_dict(raw_p)
                if plan_obj and plan_obj.steps:
                    return {"type": "plan", "plan": plan_obj}, None
    except json.JSONDecodeError:
        pass

    # Attempt 2: Extract valid JSON objects (handling nested dicts and multi-JSON strings)
    def extract_json_dicts(text: str) -> List[Dict[str, Any]]:
        objs = []
        for i, char in enumerate(text):
            if char == '{':
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                        if depth == 0:
                            candidate = text[i:j+1]
                            try:
                                data = json.loads(candidate)
                                if isinstance(data, dict):
                                    objs.append(data)
                            except json.JSONDecodeError:
                                pass
                            break
        return objs

    for data in extract_json_dicts(clean_text):
        if "type" in data:
            action_type = str(data.get("type")).lower()
            if action_type == "final" and "answer" in data:
                return {"type": "final", "answer": str(data["answer"])}, None
            if action_type == "tool" and "tool" in data:
                tool_name = str(data.get("tool")).upper()
                args = data.get("arguments") if isinstance(data.get("arguments"), dict) else {}
                return {"type": "tool", "tool": tool_name, "arguments": args}, None
            if action_type == "plan" and ("steps" in data or "plan" in data):
                raw_p = data.get("plan") if isinstance(data.get("plan"), dict) else data
                plan_obj = ExecutionPlan.from_dict(raw_p)
                if plan_obj and plan_obj.steps:
                    return {"type": "plan", "plan": plan_obj}, None

    # Attempt 3: Legacy Intent String Fallback (Backward Compatibility)
    first_line = clean_text.splitlines()[0].strip() if clean_text else ""
    first_word_upper = first_line.split(":", 1)[0].strip().upper() if ":" in first_line else first_line.upper()

    if first_word_upper == "OPEN_BRAVE" or (first_word_upper == "OPEN_APP" and "BRAVE" in first_line.upper()):
        return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "brave"}}, None

    if first_word_upper == "OPEN_APP":
        app_name = ""
        if ":" in first_line:
            app_name = first_line.split(":", 1)[1].strip().lower()
        return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": app_name}}, None

    if first_word_upper == "WEB_SEARCH":
        query = ""
        if ":" in first_line:
            query = first_line.split(":", 1)[1].strip()
        return {"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": query if query else clean_text}}, None

    if first_word_upper == "LIST_FILES":
        loc = "Brain"
        if ":" in first_line:
            loc = first_line.split(":", 1)[1].strip()
        return {"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": loc}}, None

    if first_word_upper == "FIND_FILES":
        pat, loc = "*.py", "Brain"
        if ":" in first_line:
            parts = first_line.split(":", 1)[1].split("|")
            pat = parts[0].strip()
            if len(parts) > 1:
                loc = parts[1].strip()
        return {"type": "tool", "tool": "FIND_FILES", "arguments": {"pattern": pat, "search_root": loc}}, None

    if first_word_upper == "READ_TEXT_FILE":
        path = ""
        if ":" in first_line:
            path = first_line.split(":", 1)[1].strip()
        return {"type": "tool", "tool": "READ_TEXT_FILE", "arguments": {"filepath": path}}, None

    if first_word_upper == "CREATE_FOLDER":
        name, parent = "", "Downloads"
        if ":" in first_line:
            parts = first_line.split(":", 1)[1].split("|")
            name = parts[0].strip()
            if len(parts) > 1:
                parent = parts[1].strip()
        return {"type": "tool", "tool": "CREATE_FOLDER", "arguments": {"folder_name": name, "parent_root": parent}}, None

    # Default: Treat plain model text as a final answer
    return {"type": "final", "answer": clean_text}, None


def build_planner_prompt(user_request: str, history: List[Dict[str, Any]], registry: Optional[ToolRegistry] = None) -> str:
    """Builds system prompt for the LLM specifying tools, JSON format, screen observations, and isolated task history."""
    reg = registry or default_registry
    req_lowered = user_request.lower() if user_request else ""
    gui_browser_req = any(kw in req_lowered for kw in APPROVED_BROWSER_KEYWORDS)

    tools_info = ""
    for tool in reg.list_tools():
        if tool['name'] == "WEB_SEARCH" and gui_browser_req:
            continue
        tools_info += f"- {tool['name']}: {tool['description']}\n  Parameters: {tool['parameters']}\n"

    obs_text = ""
    from core.perception import default_perception_router
    last_perc = default_perception_router.get_last_result()
    current_obs = default_vision.get_current_observation()

    use_perc = False
    if last_perc and not last_perc.is_stale(max_age_seconds=15):
        if not current_obs or last_perc.timestamp >= current_obs.get("timestamp", 0):
            use_perc = True

    if use_perc and last_perc:
        obs_text = f"\nCURRENT SCREEN PERCEPTION (Source: {last_perc.source}, State: [{last_perc.screen_state}], App: {last_perc.application}):\n"
        if last_perc.observations:
            for o in last_perc.observations:
                obs_text += f"- {o}\n"
        elems = last_perc.detected_elements[:15]
        if elems:
            obs_text += f"<untrusted_data source=\"{last_perc.source}\">\nVisible Elements:\n"
            for idx, elem in enumerate(elems, 1):
                txt_disp = elem.get('text', '')
                if len(txt_disp) > 30:
                    txt_disp = txt_disp[:30] + "..."
                conf = elem.get('confidence', 1.0)
                obs_text += f"{idx}. [{elem.get('type', 'element')}] '{txt_disp}' center: ({elem.get('center_x')}, {elem.get('center_y')}) conf: {conf:.2f} ID: {elem.get('id')}\n"
            obs_text += "</untrusted_data>\n"
        else:
            obs_text += "No visible elements detected on screen.\n"
    elif current_obs:
        status = current_obs.get("status", "NO_OBSERVATION")
        scr = current_obs.get("screen", {})
        elems = current_obs.get("elements", [])
        if len(elems) > 15:
            elems = elems[:15]
        obs_text = f"\nCURRENT SCREEN OBSERVATION:\nResolution: {scr.get('width', 1920)}x{scr.get('height', 1080)}\nVision Status: {status}\n"
        if status == "VISION_NOT_AVAILABLE":
            obs_text += "Visual understanding is currently unavailable. Do NOT invent UI coordinates or elements.\n"
        elif status == "NO_OBSERVATION":
            obs_text += "No active screen analysis available. Call ANALYZE_SCREEN if visual screen observation is required.\n"
        elif elems:
            obs_text += "<untrusted_data source=\"SCREEN_OBSERVATION\">\nVisible Elements:\n"
            for idx, elem in enumerate(elems, 1):
                txt_disp = elem.get('text', '')
                if len(txt_disp) > 30:
                    txt_disp = txt_disp[:30] + "..."
                conf = elem.get('confidence', 1.0)
                obs_text += f"{idx}. [{elem.get('type', 'element')}] '{txt_disp}' center: ({elem.get('center_x')}, {elem.get('center_y')}) conf: {conf:.2f} ID: {elem.get('id')}\n"
            obs_text += "</untrusted_data>\n"
        else:
            obs_text += "No visible elements detected on screen.\n"

    untrusted_tools = {"READ_TEXT_FILE", "WEB_SEARCH", "BROWSER_SEARCH", "BROWSER_NAVIGATE", "ANALYZE_SCREEN", "LIST_FILES", "FIND_FILES"}
    history_text = ""
    if history:
        history_text = "\nPrevious Step Execution History:\n"
        for idx, step in enumerate(history, 1):
            t_name = str(step.get("action", {}).get("tool", "")).upper()
            raw_res = step.get("result")
            if t_name == "ANALYZE_SCREEN" and isinstance(raw_res, dict):
                d_elems = raw_res.get("elements", []) if isinstance(raw_res.get("elements"), list) else []
                concise_res = {
                    "success": raw_res.get("success", True),
                    "tool": "ANALYZE_SCREEN",
                    "status": "VISION_ANALYZED" if raw_res.get("success") else "FAILED",
                    "elements_count": len(d_elems)
                }
                res_str = json.dumps(concise_res)
            else:
                res_str = json.dumps(raw_res)

            if t_name in untrusted_tools:
                formatted_res = f"<untrusted_data source=\"{t_name}\">\n{res_str}\n</untrusted_data>\nInstruction: Tool '{t_name}' executed successfully and returned the data above. Inspect and use this data to formulate your final answer. Do NOT execute '{t_name}' again with identical arguments."
            else:
                formatted_res = res_str

            history_text += f"Step {idx}:\n  Requested Action: {json.dumps(step['action'])}\n  Execution Result: {formatted_res}\n"

    context_header = default_context_builder.build_system_context(user_request)

    template_content = ""
    if PROMPT_TEMPLATE_PATH.exists():
        template_content = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    if template_content:
        return template_content.format(
            context_header=context_header,
            tools_info=tools_info,
            user_request=user_request,
            obs_text=obs_text,
            history_text=history_text
        )

    # Fallback if template file is missing
    return f"""{context_header}

Available Tools:
{tools_info}

User Goal: {user_request}
{obs_text}
{history_text}
Next Action JSON:"""
