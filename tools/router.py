import re


class FastRouter:
    """
    Lightweight Deterministic Pre-Router for Brain.
    Pre-routes unambiguous, high-confidence intents to tool calls or direct responses
    in <100ms without invoking Ollama Qwen generation.
    Returns parsed action dict or None.
    """
    def __init__(self):
        pass

    def route(self, user_request):
        if not user_request or not isinstance(user_request, str):
            return None

        clean_text = user_request.strip()
        lowered = clean_text.lower()
        norm_text = re.sub(r"\s+", " ", lowered).strip(".?!")

        # 1. Greetings & Simple Conversations
        greetings = {"hello", "hi", "hey", "hello!", "hi!", "good morning", "good evening"}
        if norm_text in greetings:
            return {"type": "final", "answer": "Hello! How can I assist you today?"}

        # 2. Deterministic TIME Queries (evaluated BEFORE semantic triggers to prevent "tell me" exclusion)
        time_queries = {
            "tell me the time", "tell me the time.", "what time is it", "what time is it?",
            "what's the current time", "what's the current time?", "what is the time",
            "what is the time?", "current time", "current time?", "time please", "time"
        }
        if norm_text in time_queries:
            return {"type": "tool", "tool": "TIME", "arguments": {}}

        # 2b. Deterministic Memory Storage Queries (e.g. "remember that I prefer Python", "remember that my browser is Brave")
        for prefix in ["remember that ", "remember "]:
            if norm_text.startswith(prefix):
                content = clean_text[len(prefix):].strip()
                if content:
                    is_pref = any(w in norm_text for w in ["prefer", "favorite", "like", "love", "hate", "dislike"])
                    key_val = content
                    m_key = "user_preference" if is_pref else "fact"
                    if " is " in content:
                        parts = content.split(" is ", 1)
                        m_key = parts[0].strip().replace(" ", "_").lower()
                        key_val = parts[1].strip()
                    elif " prefers " in content:
                        parts = content.split(" prefers ", 1)
                        m_key = "preferred_choice"
                        key_val = parts[1].strip()

                    return {
                        "type": "tool",
                        "tool": "REMEMBER",
                        "arguments": {
                            "memory_type": "PREFERENCE" if is_pref else "FACT",
                            "subject": "user",
                            "key": m_key,
                            "value": key_val
                        }
                    }

        # 3. Deterministic Compound Multi-Step Workflows (e.g. Open Brave & Search, Open + Observe, File Manager)
        # Check compound workflows BEFORE semantic triggers to build fast ExecutionPlans without Qwen
        from tools.plan import ExecutionPlan, ExecutionStep

        # 3a. Open Brave and search for X [optional: then tell me what you see]
        for prefix in [
            "open brave and search for ", "open brave and search ",
            "in brave search for ", "in brave search ",
            "using brave search for ", "using brave search "
        ]:
            if norm_text.startswith(prefix):
                rest = clean_text[len(prefix):].strip()
                # Strip trailing "then tell me what you see", ", then tell me...", etc.
                query = re.sub(r"(,\s*)?(then\s+)?tell\s+me\s+(what\s+you\s+see|what\s+is\s+on\s+the\s+screen|the\s+results?)$", "", rest, flags=re.IGNORECASE).strip()
                if query:
                    plan = ExecutionPlan(goal=clean_text)
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="BROWSER_SEARCH_FOREGROUND", arguments={"query": query}))
                    if "tell me" in norm_text or "see" in norm_text or "what" in norm_text:
                        plan.add_step(ExecutionStep(action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}))
                        plan.add_step(ExecutionStep(action_type="final", answer="Search completed in Brave. Visual results captured on screen."))
                    return {"type": "plan", "plan": plan}

        # 3b. Open Brave and tell me what is on the screen / Open Brave and describe screen
        if norm_text in {
            "open brave and tell me what is on the screen", "open brave and tell me what is on the screen.",
            "open brave and tell me what you see", "open brave and describe the screen",
            "open brave and analyze screen", "open brave and analyze my screen"
        }:
            plan = ExecutionPlan(goal=clean_text)
            plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}))
            plan.add_step(ExecutionStep(action_type="final", answer="Brave opened and focused. Screen analyzed."))
            return {"type": "plan", "plan": plan}

        # 3c. Open File Manager and open my Brain folder
        if norm_text in {
            "open file manager and open my brain folder", "open file manager and open brain folder",
            "open file manager and open brain", "open file manager and show brain folder"
        }:
            plan = ExecutionPlan(goal=clean_text)
            plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "file_manager"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "file_manager"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="LIST_FILES", arguments={"target_path": "Brain"}))
            plan.add_step(ExecutionStep(action_type="final", answer="File Manager opened and Brain folder listed."))
            return {"type": "plan", "plan": plan}

        # 3d. Open terminal and type X / run X
        for prefix in ["open terminal and type ", "in terminal type ", "open terminal and run "]:
            if norm_text.startswith(prefix):
                cmd = clean_text[len(prefix):].strip()
                if cmd:
                    plan = ExecutionPlan(goal=clean_text)
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"}))
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="TYPE_TEXT", arguments={"text": cmd}))
                    return {"type": "plan", "plan": plan}

        # 4. Simple Single-Intent App Launch & System Requests
        # Strictly match simple single-intent requests, NOT multi-step compound requests ("open brave and search...")
        if " and " not in norm_text and " then " not in norm_text and "," not in norm_text:
            # Brave
            if norm_text in {"open brave", "open brave browser", "open browser", "launch brave", "launch browser"}:
                return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "brave"}}
            if norm_text in {"close brave", "close brave browser", "close browser", "quit brave", "exit brave"}:
                return {"type": "tool", "tool": "CLOSE_APP", "arguments": {"app_name": "brave"}}
            if norm_text in {"focus brave", "focus brave browser", "focus browser"}:
                return {"type": "tool", "tool": "FOCUS_APP", "arguments": {"app_name": "brave"}}

            # File Manager
            if norm_text in {"open file manager", "open thunar", "open files", "launch file manager"}:
                return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "file_manager"}}
            if norm_text in {"close file manager", "close thunar", "close files", "quit file manager"}:
                return {"type": "tool", "tool": "CLOSE_APP", "arguments": {"app_name": "file_manager"}}
            if norm_text in {"focus file manager", "focus thunar", "focus files"}:
                return {"type": "tool", "tool": "FOCUS_APP", "arguments": {"app_name": "file_manager"}}

            # Terminal
            if norm_text in {"open terminal", "launch terminal"}:
                return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "terminal"}}
            if norm_text in {"close terminal", "quit terminal"}:
                return {"type": "tool", "tool": "CLOSE_APP", "arguments": {"app_name": "terminal"}}
            if norm_text in {"focus terminal", "focus console"}:
                return {"type": "tool", "tool": "FOCUS_APP", "arguments": {"app_name": "terminal"}}

            # Text Editor
            if norm_text in {"open text editor", "open editor", "open nano"}:
                return {"type": "tool", "tool": "OPEN_APP", "arguments": {"app_name": "text_editor"}}
            if norm_text in {"close text editor", "close editor"}:
                return {"type": "tool", "tool": "CLOSE_APP", "arguments": {"app_name": "text_editor"}}

            # Screenshot (Raw Screen Capture ONLY, NO OCR)
            if norm_text in {"take a screenshot", "capture screen", "take screenshot", "screenshot"}:
                return {"type": "tool", "tool": "SCREENSHOT", "arguments": {}}

            # Analyze Screen (Screen Capture + OCR Perception)
            if norm_text in {"analyze screen", "analyze my screen", "read screen", "ocr screen"}:
                return {"type": "tool", "tool": "ANALYZE_SCREEN", "arguments": {}}

            # Directory Listing
            if norm_text in {
                "list files", "list files in brain", "list files in my brain project",
                "list files in project", "show files in brain", "list directory"
            }:
                return {"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": "Brain"}}

            # Finding Python Files
            if norm_text in {
                "find python files", "find all python files", "find *.py files",
                "search python files", "find py files"
            }:
                return {"type": "tool", "tool": "FIND_FILES", "arguments": {"pattern": "*.py", "search_root": "Brain"}}

        # Semantic Exclusion Guard: Requests containing open-ended reasoning/summary triggers MUST reach Qwen
        semantic_triggers = [
            "summarize", "whether", "recommend", "useful", "best",
            "why", "how", "compare", "should", "improvement", "whatever", "find the best",
            "look into"
        ]
        if any(trigger in norm_text for trigger in semantic_triggers):
            return None

        # 5. Background Web Search Intents (e.g. "Search the web for Python 3.12 features")
        for prefix in [
            "search the web for ", "search web for ", "search for ", "look up "
        ]:
            if norm_text.startswith(prefix):
                q = clean_text[len(prefix):].strip()
                if q:
                    return {"type": "tool", "tool": "BROWSER_SEARCH", "arguments": {"query": q, "mode": "BACKGROUND"}}

        return None


default_router = FastRouter()

