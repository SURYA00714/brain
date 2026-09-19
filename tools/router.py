import re


class FastRouter:
    """
    Lightweight Deterministic Pre-Router for Brain.
    Pre-routes unambiguous, high-confidence intents to tool calls or direct responses
    in <100ms without invoking LLM generation.
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
        clean_norm = re.sub(r"[^\w\s]", " ", lowered)
        clean_norm = re.sub(r"\s+", " ", clean_norm).strip()

        # 1. Greetings & Simple Conversations
        greetings = {
            "hello", "hi", "hey", "hello!", "hi!", "good morning", "good evening", "good afternoon",
            "ello", "hiya", "howdy", "sup", "yo", "greetings"
        }
        if norm_text in greetings:
            return {"type": "final", "answer": "Hello! How can I assist you today?"}

        gratitudes = {"thanks", "thank you", "thanks!", "thank you!", "thx", "many thanks", "appreciate it"}
        if norm_text in gratitudes:
            return {"type": "final", "answer": "You're welcome! Let me know if you need anything else."}

        farewells = {"bye", "goodbye", "see you", "see ya", "exit", "quit", "cya"}
        if norm_text in farewells:
            return {"type": "final", "answer": "Goodbye! Brain is standing by whenever you need assistance."}

        # 1b. Deterministic Identity & Capabilities (NO LLM, NO WEB SEARCH)
        identity_queries = {
            "who are you", "who are you?", "what are you", "what are you?",
            "what is your name", "what's your name", "who made you",
            "tell me about yourself", "what can you do", "what are your capabilities",
            "help", "capabilities"
        }
        if norm_text in identity_queries:
            from core.identity import default_identity
            if norm_text in {"what can you do", "what are your capabilities", "help", "capabilities"}:
                caps = "\n".join(f"- {c}" for c in default_identity.capabilities)
                return {
                    "type": "final",
                    "answer": f"I am {default_identity.name} ({default_identity.version}), {default_identity.persona}\n\nHere is what I can do:\n{caps}"
                }
            return {
                "type": "final",
                "answer": f"I am {default_identity.name} ({default_identity.version}), {default_identity.persona} {default_identity.communication_style}"
            }

        # 1b-2. Cloud Intelligence & Model Runtime Status Diagnostic (NO LLM, SAFE, <1ms)
        cloud_status_queries = {
            "brain cloud status", "cloud status", "cloud intelligence status", "brain cloud",
            "model status", "cloud model status"
        }
        if norm_text in cloud_status_queries:
            from models.gateway import default_gateway
            stat = default_gateway.get_cloud_status()
            return {"type": "final", "answer": stat["report"]}

        model_identity_queries = {
            "what do you use", "what model do you use", "what models do you use",
            "what model are you using", "what models are you using", "which model do you use",
            "what is your model", "which models do you use", "what llm do you use", "what ai model do you use"
        }
        if norm_text in model_identity_queries or clean_norm in model_identity_queries:
            from models.gateway import ModelRuntimeStatus
            return {"type": "final", "answer": ModelRuntimeStatus.get_runtime_identity_summary()}


        # 1b-3. Procedural Skills & Task Continuity Queries (NO LLM, <2ms)
        skills_queries = {"list skills", "what skills do you have", "show skills", "procedural skills", "skills"}
        if norm_text in skills_queries or clean_norm in skills_queries:
            from core.skills import default_skills
            skills_list = default_skills.list_skills()
            if skills_list:
                s_str = "\n".join(f"- {s.name}: {s.description}" for s in skills_list)
                return {"type": "final", "answer": f"Brain Procedural Skills:\n{s_str}"}
            return {"type": "final", "answer": "No procedural skills registered."}

        goals_queries = {"list goals", "what are my goals", "show goals", "my projects", "what are we doing", "what am i currently working on", "continue what we were doing", "continue project", "continue the project"}
        if norm_text in goals_queries or clean_norm in goals_queries:
            from core.goals import default_goals
            active_goal = default_goals.get_active_goal()
            if active_goal:
                return {"type": "final", "answer": f"Active Project:\n{active_goal.progress_summary()}"}
            return {"type": "final", "answer": "We don't have an active background project paused right now. What would you like to work on?"}

        learn_queries = {"remember how we fixed this", "remember this procedure", "save this procedure", "learn this skill", "remember this fix"}
        if norm_text in learn_queries or clean_norm in learn_queries:
            import time
            from core.skills import default_skills
            from core.world_state import default_world_state
            from tools.plan import ExecutionPlan, ExecutionStep
            plan = ExecutionPlan(goal="learned_fix")
            if getattr(default_world_state, "last_opened_app", None):
                plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": default_world_state.last_opened_app}, description=f"Open {default_world_state.last_opened_app}"))
                plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": default_world_state.last_opened_app}, description=f"Focus {default_world_state.last_opened_app}"))
            else:
                plan.add_step(ExecutionStep(action_type="tool", tool_name="CHECK_DISK_SPACE", arguments={"target_path": "/"}, description="Verify system storage"))
            learned = default_skills.learn_trajectory_as_skill(
                name=f"learned_fix_{int(time.time())}",
                description="Learned procedure from recent successful trajectory",
                trigger_patterns=["run the learned fix", "apply recent fix"],
                plan=plan
            )
            return {"type": "final", "answer": f"I've recorded that procedure as a persistent skill ({learned.name if learned else 'saved'}). You can trigger it anytime."}

        # 1b-4. Procedural Skills Direct Execution (NO LLM, <2ms)
        from core.skills import default_skills
        matched_skill = default_skills.match_skill(clean_text)
        if matched_skill:
            params = {"query": clean_text, "repo_query": clean_text}
            plan = matched_skill.to_execution_plan(clean_text, params=params)
            return {"type": "plan", "plan": plan}


        # 1c. Deterministic System & Environment Information (NO LLM)
        os_queries = {
            "what operating system am i using", "what operating system am i on",
            "what os am i using", "what os is this", "what is my os", "what's my os",
            "what os am i on", "operating system"
        }
        if norm_text in os_queries:
            import platform
            return {"type": "final", "answer": f"You are using Linux Mint (XFCE edition) on kernel {platform.release()}."}

        desktop_queries = {
            "what desktop am i using", "what desktop environment am i using",
            "what desktop is this", "what desktop environment", "desktop environment"
        }
        if norm_text in desktop_queries:
            return {"type": "final", "answer": "You are using the XFCE desktop environment on Linux Mint."}

        # 1c-1. Multi-signal System State & Application Inspection (NO LLM, <200ms)
        # Compound: "What apps are currently open on my computer, and which one am I using?"
        is_compound_apps_using = (
            ("apps" in clean_norm or "applications" in clean_norm) and
            ("open" in clean_norm or "running" in clean_norm) and
            ("using" in clean_norm or "active" in clean_norm or "focus" in clean_norm)
        )
        if is_compound_apps_using:
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            running = state.get("running_apps", [])
            app_map = {"brave": "Brave Browser", "file_manager": "File Manager (Thunar)", "terminal": "Terminal", "text_editor": "Text Editor", "calculator": "Calculator"}
            apps_str = ", ".join([app_map.get(a, a.title()) for a in running]) if running else "None"
            active = state.get("active_app")
            active_str = app_map.get(active, active.title()) if active else "None"
            return {"type": "final", "answer": f"Open applications: {apps_str}. You are currently using: {active_str}."}

        # Running / Open Apps Queries
        running_apps_queries = {
            "what applications are running", "what apps are running",
            "what is running", "what's running", "list running apps", "show running apps",
            "which apps are running", "what apps are open", "what apps are currently open",
            "what applications are currently open", "what applications are open",
            "which apps are open", "what apps do i have open", "list open apps"
        }
        is_open_apps_query = (
            norm_text in running_apps_queries or
            clean_norm in running_apps_queries or
            (("what apps" in clean_norm or "what applications" in clean_norm or "which apps" in clean_norm) and ("running" in clean_norm or "open" in clean_norm))
        )
        if is_open_apps_query:
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            running = state.get("running_apps", [])
            if running:
                app_map = {"brave": "Brave Browser", "file_manager": "File Manager (Thunar)", "terminal": "Terminal", "text_editor": "Text Editor", "calculator": "Calculator"}
                app_names = [app_map.get(a, a.title()) for a in running]
                return {"type": "final", "answer": f"Currently running applications verified by Brain: {', '.join(app_names)}."}
            else:
                return {"type": "final", "answer": "No Brain-tracked applications are currently running."}

        # Active App / Window Queries
        if norm_text in {"active window", "focused window", "get active window", "current active window"}:
            return {"type": "tool", "tool": "ACTIVE_WINDOW", "arguments": {}}

        active_app_queries = {
            "which app am i using", "what app am i using", "which application am i using",
            "what application am i using", "what app is active", "what is the active app",
            "which app is active", "what window is active", "focused app"
        }
        if norm_text in active_app_queries or clean_norm in active_app_queries:
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            active = state.get("active_app")
            title = state.get("active_window_title")
            app_map = {"brave": "Brave Browser", "file_manager": "File Manager (Thunar)", "terminal": "Terminal", "text_editor": "Text Editor", "calculator": "Calculator"}
            if active:
                act_display = app_map.get(active, active.title())
                title_extra = f" ('{title}')" if title else ""
                return {"type": "final", "answer": f"You are currently using: {act_display}{title_extra}."}
            return {"type": "final", "answer": "No active application window is currently detected."}

        # Disk Space Queries (NO LLM)
        disk_queries = {
            "how much disk space do i have", "how much disk space is left", "how much disk space",
            "disk space", "disk usage", "free disk space", "how much storage do i have", "storage space",
            "check disk space", "disk status"
        }
        if norm_text in {"disk status", "show disk status", "show disk", "disk info"}:
            return {"type": "tool", "tool": "DISK_STATUS", "arguments": {}}
        elif (norm_text in disk_queries or clean_norm in disk_queries or ("disk space" in clean_norm or "free disk" in clean_norm)) and "terminal" not in clean_norm:
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            disk = state.get("disk", {})
            return {"type": "final", "answer": f"Disk space: You have {disk.get('free_gb', 0)}GB free disk space out of {disk.get('total_gb', 0)}GB ({disk.get('percent_used', 0)}% used)."}

        # Memory / RAM Queries (NO LLM)
        ram_queries = {
            "how much ram is available", "how much memory is available", "how much ram do i have",
            "how much free ram", "ram usage", "memory usage", "free ram", "free memory",
            "ram available", "memory available"
        }
        if norm_text in {"memory status", "show memory status", "show memory", "memory info"}:
            return {"type": "tool", "tool": "MEMORY_STATUS", "arguments": {}}
        elif norm_text in ram_queries or clean_norm in ram_queries or ("ram" in clean_norm and ("available" in clean_norm or "free" in clean_norm or "usage" in clean_norm)):
            from tools.apps import get_system_state_summary
            state = get_system_state_summary()
            mem = state.get("memory", {})
            avail = mem.get("available_mb", 0)
            total = mem.get("total_mb", 0)
            pct = round(((total - avail) / total) * 100, 1) if total else 0
            return {"type": "final", "answer": f"You have {avail}MB RAM available out of {total}MB ({pct}% used)."}

        browser_queries = {
            "what browser am i using", "what is my browser", "what's my browser",
            "preferred browser", "what is my preferred browser"
        }
        if norm_text in browser_queries:
            from core.identity import default_identity
            pref = default_identity.user_preferences.get("preferred_browser", "brave")
            return {"type": "final", "answer": f"Your configured browser is {pref.title()}."}

        # 1c-2. Last Opened App / Physical Application State
        last_app_queries = {
            "what app did we just open", "what app did we open", "what app was just opened",
            "what application did we just open", "what application was opened", "which app did we open",
            "what app did we launch", "what did we just open"
        }
        if norm_text in last_app_queries or norm_text.startswith("what app did we"):
            from core.world_state import default_world_state
            from tools.apps import default_app_tracker
            app = getattr(default_world_state, "last_opened_app", None) or default_app_tracker.get_focused_app()
            if not app and default_app_tracker._tracked_apps:
                for k, v in default_app_tracker._tracked_apps.items():
                    if any(e.get("process_alive") for e in v):
                        app = k
                        break
            if app:
                app_map = {"brave": "Brave", "terminal": "Terminal", "file_manager": "File Manager", "text_editor": "Text Editor", "calculator": "Calculator"}
                display_name = app_map.get(app, app.title())
                return {"type": "final", "answer": f"The {display_name} application was just opened."}
            return {"type": "final", "answer": "No applications have been opened recently."}

        # 1c-3. Recent Dialogue & Conversation Context Recall
        recent_talk_queries = {
            "what was the last thing we talked about", "what did we just talk about",
            "what was our last conversation", "what was the last topic",
            "what did i just say", "what did i tell you"
        }
        if norm_text in recent_talk_queries or "last thing we talked about" in norm_text or "what did i tell you" in norm_text:
            from core.context import default_short_term_memory
            last_query = default_short_term_memory.get_last_query()
            if last_query:
                return {"type": "final", "answer": f"The last thing we talked about was: '{last_query}'."}
            return {"type": "final", "answer": "We have not discussed anything yet in this session."}

        # 1c-4. User Name & Personal Fact Lookup (Deterministic Memory Fact Retrieval)
        name_queries = {"what is my name", "what's my name", "who am i", "do you know my name", "tell me my name"}
        if norm_text in name_queries:
            from core.memory import default_memory
            mem = default_memory.get_memory("FACT", "user", "my_name") or default_memory.get_memory("FACT", "user", "name")
            if not mem:
                mems = default_memory.search_memories("name", limit=1)
                mem = mems[0] if mems else None
            if mem and mem.value:
                return {"type": "final", "answer": f"Your name is {mem.value}."}
            return {"type": "final", "answer": "I do not have your name recorded in memory yet."}

        # 1d. Find Element on Screen (Perception without Clicking)
        find_elem_match = re.match(r"^find (?:the )?(.+?)(?: button)? (?:on|in) (?:my )?screen$", norm_text)
        if find_elem_match:
            target_label = find_elem_match.group(1).strip()
            from tools.screen import analyze_captured_screen
            from tools.vision import default_vision
            analyze_captured_screen()
            elem = default_vision.find_element(target_label)
            if elem and not elem.get("ambiguous"):
                found_text = elem.get("text") or target_label.title()
                return {
                    "type": "final",
                    "answer": f"Found '{found_text}' at coordinates ({elem.get('center_x')}, {elem.get('center_y')}) with confidence {elem.get('confidence', 1.0):.2f}. (ID: {elem.get('id')})"
                }
            elif elem and elem.get("ambiguous"):
                candidates = ", ".join(f"'{c.get('text')}'" for c in elem.get("candidates", []))
                return {
                    "type": "final",
                    "answer": f"Found multiple candidates matching '{target_label}': {candidates}."
                }
            else:
                return {
                    "type": "final",
                    "answer": f"Element '{target_label}' was not detected on the current screen."
                }

        # 1e. Continue / Re-observe Screen (Stale Observation Refresh)
        if norm_text in {"continue", "refresh screen", "re-observe", "reobserve"}:
            from tools.screen import analyze_captured_screen
            from core.perception import default_perception_router
            default_perception_router.invalidate_cache()
            obs = analyze_captured_screen(force_refresh=True)
            elems = obs.get("elements", [])
            perc = obs.get("perception", {})
            return {
                "type": "final",
                "answer": f"Screen observation refreshed. Status: {obs.get('status', 'OK')}. Detected {len(elems)} visible elements (State: {perc.get('screen_state', 'NORMAL')})."
            }

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

        # 2c. Memory Retrieval / Preference Recall Queries
        recall_preference_queries = {
            "what do you remember about my preference",
            "what do you remember about my preferences",
            "what do you remember about my preference?",
            "what are my preferences",
            "what is my preference",
            "what do you remember",
            "what do you know about me"
        }
        if norm_text in recall_preference_queries or norm_text.startswith("what do you remember about "):
            from core.memory import default_memory
            mems = default_memory.search_memories("preference", limit=5)
            if not mems:
                mems = default_memory.search_memories("user", limit=5)
            if mems:
                mem_items = [f"- {m.key.replace('_', ' ').title()}: {m.value}" for m in mems]
                return {"type": "final", "answer": f"Here is what I remember about your preferences:\n" + "\n".join(mem_items)}
            else:
                return {"type": "final", "answer": "I do not have any stored preferences recorded yet."}

        # 3. Deterministic Compound Multi-Step Workflows (e.g. Open Brave & Search, Open + Observe, File Manager)
        # Check compound workflows BEFORE semantic triggers to build fast ExecutionPlans without LLM
        from tools.plan import ExecutionPlan, ExecutionStep

        # 3a-0. Open Brave, open new tab and search for X [optional: and click first result]
        new_tab_search_match = re.match(
            r"^(?:open )?brave(?:,)? (?:and )?(?:open )?(?:a )?new tab (?:and )?(?:search (?:for )?|find )(.+)$",
            norm_text,
            flags=re.IGNORECASE
        )
        if new_tab_search_match:
            rest = new_tab_search_match.group(1).strip()
            has_open_first = bool(re.search(r"(,\s*)?(and\s+)?(then\s+)?(open|click)\s+(the\s+)?(first\s+)?(result|link|item)", rest, flags=re.IGNORECASE))
            if has_open_first:
                query = re.sub(r"(,\s*)?(and\s+)?(then\s+)?(open|click)\s+(the\s+)?(first\s+)?(result|link|item).*$", "", rest, flags=re.IGNORECASE).strip().strip(".,")
            else:
                query = rest.strip().strip(".,")

            if query:
                plan = ExecutionPlan(goal=clean_text)
                plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}, expected_outcome="Brave open", verification_method="app_running", description="Open Brave browser"))
                plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}, expected_outcome="Brave focused", verification_method="focus", description="Focus Brave window"))
                plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="tool", tool_name="NEW_TAB", arguments={}, expected_outcome="New tab ready", verification_method="none", description="Open new tab in Brave"))
                plan.add_step(ExecutionStep(step_id=4, depends_on=[3], action_type="tool", tool_name="BROWSER_SEARCH_FOREGROUND", arguments={"query": query}, expected_outcome=f"Search for '{query}'", verification_method="text_on_screen", description=f"Search for '{query}' in new tab"))
                if has_open_first:
                    plan.add_step(ExecutionStep(step_id=5, depends_on=[4], action_type="tool", tool_name="CLICK_FIRST_RESULT", arguments={"query": query}, expected_outcome="First result clicked", verification_method="url_or_page", description="Click first search result"))
                    plan.add_step(ExecutionStep(step_id=6, depends_on=[5], action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}, expected_outcome="Landing page verified", verification_method="observation", description="Verify landing page"))
                    plan.add_step(ExecutionStep(step_id=7, depends_on=[6], action_type="final", answer=f"Opened Brave, opened a new tab, searched for '{query}', and opened the first result."))
                else:
                    plan.add_step(ExecutionStep(step_id=5, depends_on=[4], action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}, expected_outcome="Search results verified", verification_method="observation", description="Verify search results on screen"))
                    plan.add_step(ExecutionStep(step_id=6, depends_on=[5], action_type="final", answer=f"Opened Brave, opened a new tab, and searched for '{query}'."))
                return {"type": "plan", "plan": plan}

        # 3a-2. Open <app> and maximize it / make full screen
        open_max_match = re.match(r"^(?:open|launch|start) (.+?) (?:and |, )?(?:maximize it|maximize|make it full screen|full screen)$", norm_text, flags=re.IGNORECASE)
        if open_max_match:
            app_target = open_max_match.group(1).strip()
            if app_target:
                plan = ExecutionPlan(goal=clean_text)
                plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": app_target}, expected_outcome=f"{app_target} open", description=f"Open {app_target}"))
                plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="FOCUS_WINDOW", arguments={"target": app_target}, expected_outcome=f"{app_target} focused", description=f"Focus {app_target} window"))
                plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="tool", tool_name="MAXIMIZE_WINDOW", arguments={"target": app_target}, expected_outcome=f"{app_target} maximized", description=f"Maximize {app_target} window"))
                plan.add_step(ExecutionStep(step_id=4, depends_on=[3], action_type="final", answer=f"Opened and maximized {app_target}."))
                return {"type": "plan", "plan": plan}

        # 3a-3. Open Brave and go to / navigate to <url>
        open_nav_match = re.match(r"^(?:open|launch|start) (?:brave|browser) (?:and |, )?(?:go to|navigate to) (.+)$", norm_text, flags=re.IGNORECASE)
        if open_nav_match:
            target_url = open_nav_match.group(1).strip()
            if target_url:
                plan = ExecutionPlan(goal=clean_text)
                plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}, expected_outcome="Brave open", description="Open Brave browser"))
                plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="BROWSER_NAVIGATE", arguments={"url": target_url}, expected_outcome=f"Navigated to {target_url}", description=f"Navigate to {target_url}"))
                plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="final", answer=f"Opened Brave and navigated to {target_url}."))
                return {"type": "plan", "plan": plan}

        # 3a. Open Brave and search for X [optional: then tell me what you see]
        for prefix in [
            "open brave and search for ", "open brave and search ",
            "open brave, search for ", "open brave, search ",
            "open brave, and search for ", "open brave, and search ",
            "open brave and find ", "open brave, find ",
            "in brave search for ", "in brave search ",
            "using brave search for ", "using brave search "
        ]:
            if norm_text.startswith(prefix):
                rest = clean_text[len(prefix):].strip()
                # Check for click / open first result
                has_open_first = bool(re.search(r"(,\s*)?(and\s+)?(then\s+)?(open|click)\s+(the\s+)?(first\s+)?(result|link|item)", rest, flags=re.IGNORECASE))
                if has_open_first:
                    query = re.sub(r"(,\s*)?(and\s+)?(then\s+)?(open|click)\s+(the\s+)?(first\s+)?(result|link|item).*$", "", rest, flags=re.IGNORECASE).strip().strip(".,")
                    if query:
                        plan = ExecutionPlan(goal=clean_text)
                        plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}, expected_outcome="Brave open", verification_method="app_running", description="Open Brave browser"))
                        plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}, expected_outcome="Brave focused", verification_method="focus", description="Focus Brave window"))
                        plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="tool", tool_name="BROWSER_SEARCH_FOREGROUND", arguments={"query": query}, expected_outcome=f"Search for '{query}'", verification_method="text_on_screen", description=f"Search for '{query}'"))
                        plan.add_step(ExecutionStep(step_id=4, depends_on=[3], action_type="tool", tool_name="CLICK_FIRST_RESULT", arguments={"query": query}, expected_outcome="First result clicked", verification_method="url_or_page", description="Click first search result"))
                        plan.add_step(ExecutionStep(step_id=5, depends_on=[4], action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}, expected_outcome="Landing page verified", verification_method="observation", description="Verify landing page"))
                        plan.add_step(ExecutionStep(step_id=6, depends_on=[5], action_type="final", answer=f"Opened Brave, searched for '{query}', and opened the first result."))
                        return {"type": "plan", "plan": plan}

                # Strip trailing "then tell me what you see", ", then tell me...", etc.
                has_perception_req = bool(re.search(r"(,\s*)?(then\s+)?(and\s+)?tell\s+me\s+(what\s+you\s+see|what\s+is\s+on\s+the\s+screen|the\s+results?)$", rest, flags=re.IGNORECASE))
                query = re.sub(r"(,\s*)?(then\s+)?(and\s+)?tell\s+me\s+(what\s+you\s+see|what\s+is\s+on\s+the\s+screen|the\s+results?)$", "", rest, flags=re.IGNORECASE).strip().strip(".,")
                if query:
                    plan = ExecutionPlan(goal=clean_text)
                    plan.add_step(ExecutionStep(step_id=1, action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "brave"}, expected_outcome="Brave open", verification_method="app_running", description="Open Brave browser"))
                    plan.add_step(ExecutionStep(step_id=2, depends_on=[1], action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "brave"}, expected_outcome="Brave focused", verification_method="focus", description="Focus Brave window"))
                    plan.add_step(ExecutionStep(step_id=3, depends_on=[2], action_type="tool", tool_name="BROWSER_SEARCH_FOREGROUND", arguments={"query": query}, expected_outcome=f"Search for '{query}'", verification_method="text_on_screen", description=f"Search for '{query}'"))
                    if has_perception_req or "tell me what you see" in norm_text or "tell me what is on the screen" in norm_text:
                        plan.add_step(ExecutionStep(step_id=4, depends_on=[3], action_type="tool", tool_name="ANALYZE_SCREEN", arguments={}, expected_outcome="Screen analyzed", verification_method="observation", description="Analyze screen"))
                        plan.add_step(ExecutionStep(step_id=5, depends_on=[4], action_type="final", answer=f"Opened Brave, searched for '{query}', and analyzed the screen."))
                    else:
                        plan.add_step(ExecutionStep(step_id=4, depends_on=[3], action_type="final", answer=f"Opened Brave and searched for '{query}'."))
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

        # 3c. Open File Manager and open folder
        file_mgr_match = re.match(r"^open file manager (?:and )?(?:open |go to |show )(.+)$", norm_text)
        if file_mgr_match:
            target_f = file_mgr_match.group(1).strip()
            folder_clean = "Brain" if "brain" in target_f.lower() else ("Downloads" if "download" in target_f.lower() else target_f)
            plan = ExecutionPlan(goal=clean_text)
            plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "file_manager"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "file_manager"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="LIST_FILES", arguments={"target_path": folder_clean}))
            plan.add_step(ExecutionStep(action_type="final", answer=f"File Manager opened and {folder_clean} listed."))
            return {"type": "plan", "plan": plan}

        # 3d. Open terminal and type X / run X
        for prefix in ["open terminal and type ", "in terminal type ", "open terminal and run ", "open terminal and execute "]:
            if norm_text.startswith(prefix):
                cmd = clean_text[len(prefix):].strip()
                if cmd:
                    plan = ExecutionPlan(goal=clean_text)
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"}))
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="FOCUS_APP", arguments={"app_name": "terminal"}))
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="TYPE_TEXT", arguments={"text": cmd + "\n"}))
                    plan.add_step(ExecutionStep(action_type="final", answer=f"Terminal opened and executed '{cmd}'."))
                    return {"type": "plan", "plan": plan}

            if norm_text.startswith(prefix):
                cmd = clean_text[len(prefix):].strip()
                if cmd:
                    plan = ExecutionPlan(goal=clean_text)
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"}))
                    plan.add_step(ExecutionStep(action_type="tool", tool_name="TYPE_TEXT", arguments={"text": cmd}))
                    return {"type": "plan", "plan": plan}

        # 3e. Open terminal and check free disk space
        if "terminal" in norm_text and ("disk" in norm_text or "space" in norm_text or "storage" in norm_text):
            plan = ExecutionPlan(goal=clean_text)
            plan.add_step(ExecutionStep(action_type="tool", tool_name="OPEN_APP", arguments={"app_name": "terminal"}))
            plan.add_step(ExecutionStep(action_type="tool", tool_name="CHECK_DISK_SPACE", arguments={"target_path": "/"}))
            return {"type": "plan", "plan": plan}

        # List Apps (Developer/Debug Installed Applications Inventory)
        list_apps_queries = {"list apps", "list installed apps", "show installed apps", "show apps", "list applications", "installed apps"}
        if norm_text in list_apps_queries or clean_norm in list_apps_queries:
            return {"type": "tool", "tool": "LIST_APPS", "arguments": {}}

        # 4. Simple Single-Intent App Launch & System Requests
        # Strictly match simple single-intent requests, NOT multi-step compound requests ("open brave and search...")
        if " and " not in norm_text and " then " not in norm_text and "," not in norm_text and not re.search(r"[;&|`$]", norm_text):
            app_req_text = norm_text
            for noise in ["can you ", "could you ", "please ", "i want to ", "would you "]:
                if app_req_text.startswith(noise):
                    app_req_text = app_req_text[len(noise):].strip()

            # Open App
            for open_prefix in ["open ", "launch ", "start "]:
                if app_req_text.startswith(open_prefix):
                    match = re.search(r"^(?:can you\s+|could you\s+|please\s+|i want to\s+|would you\s+)?(?:open|launch|start)\s+(.+)$", clean_text, flags=re.IGNORECASE)
                    candidate_app = match.group(1).strip() if match else app_req_text[len(open_prefix):].strip()
                    if candidate_app:
                        app_map = {
                            "brave": "brave", "brave browser": "brave", "browser": "brave", "the browser": "brave", "my browser": "brave",
                            "file manager": "file_manager", "thunar": "file_manager", "files": "file_manager",
                            "terminal": "terminal", "console": "terminal",
                            "text editor": "text_editor", "editor": "text_editor",
                            "calculator": "calculator", "calc": "calculator"
                        }
                        mapped_app = app_map.get(candidate_app.lower(), candidate_app)
                        return {"type": "tool", "tool": "OPEN_APP", "arguments": {"name": mapped_app, "app_name": mapped_app}}

            # Close App
            for close_prefix in ["close ", "quit ", "exit ", "kill "]:
                if app_req_text.startswith(close_prefix):
                    candidate_app = app_req_text[len(close_prefix):].strip()
                    app_map = {
                        "brave": "brave", "brave browser": "brave", "browser": "brave", "the browser": "brave", "my browser": "brave",
                        "file manager": "file_manager", "thunar": "file_manager", "files": "file_manager",
                        "terminal": "terminal", "console": "terminal",
                        "text editor": "text_editor", "editor": "text_editor",
                        "calculator": "calculator", "calc": "calculator"
                    }
                    if candidate_app in app_map:
                        return {"type": "tool", "tool": "CLOSE_APP", "arguments": {"app_name": app_map[candidate_app]}}

            # Focus App
            for focus_prefix in ["focus ", "switch to "]:
                if app_req_text.startswith(focus_prefix):
                    candidate_app = app_req_text[len(focus_prefix):].strip()
                    app_map = {
                        "brave": "brave", "brave browser": "brave", "browser": "brave",
                        "file manager": "file_manager", "thunar": "file_manager", "files": "file_manager",
                        "terminal": "terminal", "console": "terminal",
                        "text editor": "text_editor", "editor": "text_editor",
                        "calculator": "calculator"
                    }
                    if candidate_app in app_map:
                        return {"type": "tool", "tool": "FOCUS_APP", "arguments": {"app_name": app_map[candidate_app]}}

            # Screenshot (Raw Screen Capture ONLY, NO OCR)
            if norm_text in {"take a screenshot", "capture screen", "take screenshot", "screenshot"}:
                return {"type": "tool", "tool": "SCREENSHOT", "arguments": {}}

            # Phase 1: System Control Tools Routing
            # Audio & Brightness
            if norm_text in {"volume up", "increase volume", "turn up volume", "turn volume up", "volume +"}:
                return {"type": "tool", "tool": "VOLUME_UP", "arguments": {}}
            if norm_text in {"volume down", "decrease volume", "turn down volume", "turn volume down", "volume -"}:
                return {"type": "tool", "tool": "VOLUME_DOWN", "arguments": {}}
            if norm_text in {"mute", "unmute", "mute volume", "toggle mute", "volume mute"}:
                return {"type": "tool", "tool": "VOLUME_MUTE", "arguments": {}}

            if norm_text in {"brightness up", "increase brightness", "turn up brightness", "screen brightness up"}:
                return {"type": "tool", "tool": "BRIGHTNESS_UP", "arguments": {}}
            if norm_text in {"brightness down", "decrease brightness", "turn down brightness", "screen brightness down"}:
                return {"type": "tool", "tool": "BRIGHTNESS_DOWN", "arguments": {}}

            if norm_text in {"lock screen", "lock computer", "lock desktop", "lock"}:
                return {"type": "tool", "tool": "LOCK_SCREEN", "arguments": {}}

            # Network Controls
            if norm_text in {"wifi status", "check wifi", "is wifi on", "wifi state"}:
                return {"type": "tool", "tool": "WIFI_STATUS", "arguments": {}}
            if norm_text in {"wifi on", "turn on wifi", "enable wifi", "start wifi"}:
                return {"type": "tool", "tool": "WIFI_ON", "arguments": {}}
            if norm_text in {"wifi off", "turn off wifi", "disable wifi", "stop wifi"}:
                return {"type": "tool", "tool": "WIFI_OFF", "arguments": {}}

            if norm_text in {"bluetooth status", "check bluetooth", "is bluetooth on", "bluetooth state"}:
                return {"type": "tool", "tool": "BLUETOOTH_STATUS", "arguments": {}}
            if norm_text in {"bluetooth on", "turn on bluetooth", "enable bluetooth", "start bluetooth"}:
                return {"type": "tool", "tool": "BLUETOOTH_ON", "arguments": {}}
            if norm_text in {"bluetooth off", "turn off bluetooth", "disable bluetooth", "stop bluetooth"}:
                return {"type": "tool", "tool": "BLUETOOTH_OFF", "arguments": {}}

            # System Information & Metrics
            if norm_text in {"system info", "show system info", "system information", "show system information", "system status"}:
                return {"type": "tool", "tool": "SYSTEM_INFO", "arguments": {}}
            if norm_text in {"memory status", "show memory status", "show memory", "memory info"}:
                return {"type": "tool", "tool": "MEMORY_STATUS", "arguments": {}}
            if norm_text in {"disk status", "show disk status", "show disk", "disk info"}:
                return {"type": "tool", "tool": "DISK_STATUS", "arguments": {}}
            if norm_text in {"cpu status", "show cpu status", "show cpu", "cpu info", "cpu usage"}:
                return {"type": "tool", "tool": "CPU_STATUS", "arguments": {}}

            # Disruptive Operations (Confirmation Gated)
            if norm_text in {"shutdown", "shutdown computer", "turn off computer", "power off", "shutdown system", "turn off pc"}:
                return {"type": "tool", "tool": "SHUTDOWN", "arguments": {}}
            if norm_text in {"restart", "restart computer", "reboot", "reboot computer", "restart pc", "reboot pc"}:
                return {"type": "tool", "tool": "RESTART", "arguments": {}}
            if norm_text in {"suspend", "suspend computer", "sleep", "sleep computer", "put pc to sleep", "suspend system", "sleep system"}:
                return {"type": "tool", "tool": "SUSPEND", "arguments": {}}
            if norm_text in {"logout", "log out", "logout user", "exit session"}:
                return {"type": "tool", "tool": "LOGOUT", "arguments": {}}

            # Phase 2: Window Management Routing
            if norm_text in {"list windows", "show windows", "list open windows", "show open windows", "get windows"}:
                return {"type": "tool", "tool": "LIST_WINDOWS", "arguments": {}}

            # Window actions with target window/app
            for min_p in ["minimize window ", "minimize "]:
                if norm_text.startswith(min_p) and not norm_text.startswith("minimize window"):
                    target = clean_text[len(min_p):].strip()
                    if target:
                        return {"type": "tool", "tool": "MINIMIZE_WINDOW", "arguments": {"target": target}}

            for max_p in ["maximize window ", "maximize ", "make full screen "]:
                if norm_text.startswith(max_p):
                    target = clean_text[len(max_p):].strip()
                    if target:
                        return {"type": "tool", "tool": "MAXIMIZE_WINDOW", "arguments": {"target": target}}

            for rest_p in ["restore window ", "restore ", "unmaximize "]:
                if norm_text.startswith(rest_p):
                    target = clean_text[len(rest_p):].strip()
                    if target:
                        return {"type": "tool", "tool": "RESTORE_WINDOW", "arguments": {"target": target}}

            for close_p in ["close window ", "close "]:
                if norm_text.startswith(close_p):
                    target = clean_text[len(close_p):].strip()
                    # Exclude close app & tab aliases
                    if target and not target.startswith("tab") and target not in {"brave", "terminal", "file_manager", "text_editor", "calculator"}:
                        return {"type": "tool", "tool": "CLOSE_WINDOW", "arguments": {"target": target}}

            if norm_text in {"ocr screen", "ocr", "extract text from screen", "read screen text"}:
                return {"type": "tool", "tool": "OCR_SCREEN", "arguments": {}}

            # Analyze Screen (Screen Capture + OCR Perception)
            screen_perception_queries = {
                "analyze screen", "analyze my screen", "read screen",
                "tell me what you see", "what do you see", "what is on my screen",
                "what is on the screen", "what's on my screen", "describe the screen",
                "describe my screen", "what can you see", "what is on my screen right now",
                "what's on my screen right now", "what is on the screen right now",
                "what is on my screen now", "what is on screen right now"
            }
            if norm_text in screen_perception_queries or norm_text.startswith("what is on my screen") or norm_text.startswith("what's on my screen"):
                return {"type": "tool", "tool": "ANALYZE_SCREEN", "arguments": {}}

            # Phase 3: Safe Filesystem Operations Routing
            if norm_text in {"list downloads", "show downloads", "list downloads folder", "show downloads folder"}:
                return {"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": "Downloads"}}

            for list_p in ["list folder ", "list directory ", "open folder ", "show folder "]:
                if norm_text.startswith(list_p):
                    target_f = clean_text[len(list_p):].strip()
                    if target_f:
                        return {"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": target_f}}

            for cf_p in ["create folder ", "make folder ", "mkdir "]:
                if norm_text.startswith(cf_p):
                    fname = clean_text[len(cf_p):].strip()
                    if fname:
                        return {"type": "tool", "tool": "CREATE_FOLDER", "arguments": {"folder_name": fname}}

            for cfile_p in ["create file ", "create empty file ", "touch "]:
                if norm_text.startswith(cfile_p):
                    fname = clean_text[len(cfile_p):].strip()
                    if fname:
                        return {"type": "tool", "tool": "CREATE_FILE", "arguments": {"file_name": fname}}

            # Copy file: "copy <src> to <dst>"
            copy_match = re.match(r"^copy (.+?) to (.+)$", norm_text, flags=re.IGNORECASE)
            if copy_match:
                src_p, dst_p = copy_match.group(1).strip(), copy_match.group(2).strip()
                if src_p and dst_p:
                    return {"type": "tool", "tool": "COPY_FILE", "arguments": {"source": src_p, "destination": dst_p}}

            # Move file: "move <src> to <dst>"
            move_match = re.match(r"^move (.+?) to (.+)$", norm_text, flags=re.IGNORECASE)
            if move_match:
                src_p, dst_p = move_match.group(1).strip(), move_match.group(2).strip()
                if src_p and dst_p:
                    return {"type": "tool", "tool": "MOVE_FILE", "arguments": {"source": src_p, "destination": dst_p}}

            # Rename file: "rename <src> to <new_name>"
            rename_match = re.match(r"^rename (.+?) to (.+)$", norm_text, flags=re.IGNORECASE)
            if rename_match:
                src_p, nname = rename_match.group(1).strip(), rename_match.group(2).strip()
                if src_p and nname:
                    return {"type": "tool", "tool": "RENAME_FILE", "arguments": {"source": src_p, "new_name": nname}}

            for del_p in ["delete file ", "delete folder ", "delete ", "remove file ", "remove folder "]:
                if norm_text.startswith(del_p):
                    tpath = clean_text[len(del_p):].strip()
                    if tpath and not any(tpath.startswith(w) for w in ["app", "window", "tab"]):
                        return {"type": "tool", "tool": "DELETE_FILE", "arguments": {"target_path": tpath}}

            for info_p in ["file info ", "inspect file ", "file details "]:
                if norm_text.startswith(info_p):
                    tpath = clean_text[len(info_p):].strip()
                    if tpath:
                        return {"type": "tool", "tool": "FILE_INFO", "arguments": {"target_path": tpath}}

            # Phase 4: Deterministic Browser Control Routing
            if norm_text in {"go back", "browser back", "back page", "navigate back"}:
                return {"type": "tool", "tool": "BROWSER_BACK", "arguments": {}}
            if norm_text in {"go forward", "browser forward", "forward page", "navigate forward"}:
                return {"type": "tool", "tool": "BROWSER_FORWARD", "arguments": {}}
            if norm_text in {"reload", "reload page", "refresh page", "reload browser", "refresh browser"}:
                return {"type": "tool", "tool": "BROWSER_RELOAD", "arguments": {}}
            if norm_text in {"page title", "get page title", "what is page title", "get browser title"}:
                return {"type": "tool", "tool": "BROWSER_TITLE", "arguments": {}}
            if norm_text in {"page url", "get page url", "current url", "get current url", "what is current url"}:
                return {"type": "tool", "tool": "BROWSER_URL", "arguments": {}}
            if norm_text in {"close tab", "close browser tab", "close current tab"}:
                return {"type": "tool", "tool": "BROWSER_CLOSE_TAB", "arguments": {}}
            if norm_text in {"list tabs", "show tabs", "list browser tabs"}:
                return {"type": "tool", "tool": "BROWSER_LIST_TABS", "arguments": {}}

            if norm_text in {"scroll down", "scroll page down", "page down"}:
                return {"type": "tool", "tool": "BROWSER_SCROLL", "arguments": {"direction": "down", "amount": 500}}
            if norm_text in {"scroll up", "scroll page up", "page up"}:
                return {"type": "tool", "tool": "BROWSER_SCROLL", "arguments": {"direction": "up", "amount": 500}}

            for dl_p in ["download file ", "download "]:
                if norm_text.startswith(dl_p):
                    target_url = clean_text[len(dl_p):].strip()
                    if target_url and (target_url.startswith("http://") or target_url.startswith("https://") or "." in target_url):
                        return {"type": "tool", "tool": "BROWSER_DOWNLOAD", "arguments": {"url": target_url}}

            # Phase 5: Desktop Control & Observation Routing
            if norm_text in {"screen size", "screen dimensions", "display size", "get screen size"}:
                return {"type": "tool", "tool": "SCREEN_SIZE", "arguments": {}}
            if norm_text in {"ocr screen", "ocr", "extract text from screen", "read screen text"}:
                return {"type": "tool", "tool": "OCR_SCREEN", "arguments": {}}
            if norm_text in {"active window", "focused window", "get active window", "current active window"}:
                return {"type": "tool", "tool": "ACTIVE_WINDOW", "arguments": {}}

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

        # Semantic Exclusion Guard: Requests containing open-ended reasoning/summary triggers MUST reach the cloud model
        semantic_triggers = [
            "summarize", "whether", "recommend", "useful", "best",
            "why", "how", "compare", "should", "improvement", "whatever", "find the best",
            "look into", "crashing", "crash", "slow", "error", "broken", "issue"
        ]
        if any(trigger in norm_text for trigger in semantic_triggers):
            return None

        # 5. Direct Web Search Intents (e.g. "search Marvel", "search for Python 3.12")
        for prefix in [
            "search the web for ", "search web for ", "search for ", "look up ", "search "
        ]:
            if norm_text.startswith(prefix):
                q = clean_text[len(prefix):].strip()
                if q:
                    from core.world_state import default_world_state
                    active_app = default_world_state.get_focused_app()
                    if active_app == "brave":
                        return {"type": "tool", "tool": "BROWSER_SEARCH_FOREGROUND", "arguments": {"query": q}}
                    return {"type": "tool", "tool": "BROWSER_SEARCH", "arguments": {"query": q, "mode": "BACKGROUND"}}

        return None


default_router = FastRouter()

