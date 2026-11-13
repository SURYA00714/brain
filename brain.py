import json
import os
import re
import requests
import time

from tools.registry import default_registry, ToolRegistry
from tools.apps import open_app, close_app, focus_app, open_brave, APPROVED_APPS, default_app_tracker
from tools.search import perform_web_search
from tools.files import list_files, find_files, read_text_file, create_folder
from tools.vision import default_vision
from tools.screen import analyze_captured_screen
from tools.profiler import PerformanceProfiler
from tools.router import default_router
from tools.browser import browser_search, browser_navigate, browser_search_foreground
from tools.plan import ExecutionPlan, ExecutionStep
from tools.input import validate_gui_action_safety
from models.gateway import default_gateway
from core.identity import default_identity
from core.memory import default_memory
from core.world_state import default_world_state
from core.context import default_context_builder
from core.cognition import default_cognition, verify_step_execution, validate_step_permissions, validate_step_parameters
from core.formatter import format_tool_response
from brain_constants import (
    UI_MODIFYING_TOOLS,
    DESTRUCTIVE_TOOLS,
    ALLOWED_INTENTS,
    APPROVED_BROWSER_KEYWORDS,
    MAX_STEPS,
    MAX_RECOVERY_ATTEMPTS,
)

from core.planner import (
    clean_search_query,
    parse_model_action,
    is_visual_request,
    build_planner_prompt
)
from core.executor import (
    TaskState,
    execute_plan
)
from core.router_pipeline import process_fast_route


def determine_execution_mode(user_request):
    """
    Determines execution strategy mode: FOREGROUND, BACKGROUND, or AUTO.
    Contextually evaluated via default_cognition.
    """
    return default_cognition.determine_execution_mode(user_request)


def ask_brain(text):
    """
    Backward-compatibility function for single-intent classification tests.
    Parses intent tuple (intent_name, arg) from model response.
    """
    resp = default_gateway.generate(prompt=f"Classify: {text}", tier="LOCAL", timeout=10.0)
    if not resp.success:
        return (None, None)
    raw_output = resp.text.strip()

    action, _ = parse_model_action(raw_output)
    if not action:
        return ("CHAT", None)

    if action["type"] == "tool":
        tool_name = action["tool"]
        args = action.get("arguments", {})
        if tool_name == "OPEN_APP":
            app_name = args.get("app_name", "")
            return ("OPEN_APP", app_name) if app_name in APPROVED_APPS else ("UNAPPROVED_APP", app_name)
        elif tool_name == "WEB_SEARCH":
            return ("WEB_SEARCH", args.get("query", ""))
        elif tool_name == "LIST_FILES":
            return ("LIST_FILES", args.get("target_path", "Brain"))
        elif tool_name == "FIND_FILES":
            return ("FIND_FILES", (args.get("pattern", "*.py"), args.get("search_root", "Brain")))
        elif tool_name == "READ_TEXT_FILE":
            return ("READ_TEXT_FILE", args.get("filepath", ""))
        elif tool_name == "CREATE_FOLDER":
            return ("CREATE_FOLDER", (args.get("folder_name", ""), args.get("parent_root", "Downloads")))

    return ("CHAT", None)


def _notify_companion(state, status_text="", action=None, result=None):
    try:
        from body.server import set_companion_state
        set_companion_state(state, status_text=status_text, action=action, result=result)
    except Exception:
        pass


def _companion_speak(text):
    if os.environ.get("BRAIN_VOICE") == "1" and os.environ.get("BRAIN_MOCK_GUI") != "1":
        try:
            from core.voice import default_voice
            default_voice.speak(text)
        except Exception:
            pass


def run_planner_task(user_request, registry=None, max_steps=MAX_STEPS, quiet=False, debug=False):
    """
    Executes the multi-step reasoning and tool-execution planner loop.
    Supports FastRouter pre-routing for <100ms response latency on high-confidence tasks,
    single-pass ExecutionPlan execution without LLM re-entry per step,
    and PerformanceProfiler telemetry metrics tracking.
    Returns final answer string or error message.
    """
    _notify_companion("THINKING", "Processing request...")
    from core.telemetry import default_telemetry
    with default_telemetry.track_request(user_request):
        res = _raw_run_planner_task(user_request, registry=registry, max_steps=max_steps, quiet=quiet, debug=debug)
        if isinstance(res, str) and res.startswith("Brain Error"):
            _notify_companion("ERROR", "Action halted", result=res[:60])
        else:
            _notify_companion("SUCCESS", "Task complete", result=str(res)[:60])
            _companion_speak(str(res))
        return res


def _raw_run_planner_task(user_request, registry=None, max_steps=MAX_STEPS, quiet=False, debug=False):
    if registry is None:
        registry = default_registry

    profiler = PerformanceProfiler()
    profiler.start()

    from core.telemetry import default_telemetry
    t_req_start = time.perf_counter()
    telemetry = default_telemetry.current

    # Phase 15: Zero-Latency Immediate Safety Screen (<1ms)
    t_safe0 = time.perf_counter()
    from tools.input import screen_prompt_safety
    is_safe_prompt, prompt_safety_err = screen_prompt_safety(user_request)
    t_safe1 = time.perf_counter()
    telemetry.safety_ms = (t_safe1 - t_safe0) * 1000.0

    if not is_safe_prompt:
        profiler.record_total()
        profiler.log_summary(user_request, mode="AUTO", status="FAILED")
        telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
        telemetry.llm_calls_this_request = 0
        default_telemetry.finish_request()
        return prompt_safety_err

    # Task State Isolation: guarantee fresh start for each independent user task
    default_vision.clear_observation()
    from tools.input import default_chain_tracker
    default_chain_tracker.clear()

    # Phase 14: Short-Term Memory Reference Resolution ("close it", "search that", etc.)
    from core.context import default_short_term_memory
    effective_request = user_request
    if registry is default_registry or registry is None:
        resolved_request = default_short_term_memory.resolve_references(user_request)
        if resolved_request:
            effective_request = resolved_request

    # Fast deterministic pre-routing check (<100ms execution path)
    if registry is default_registry or registry is None:
        fast_res = process_fast_route(
            user_request=user_request,
            effective_request=effective_request,
            registry=registry,
            profiler=profiler,
            t_req_start=t_req_start,
            quiet=quiet,
            debug=debug
        )
        if fast_res.handled:
            return fast_res.response

    # Phase 14: Cognitive Engine Evaluation (when using default production registry)
    if registry is default_registry or registry is None:
        from core.cognition import default_cognition
        intent_info = default_cognition.understand_intent(effective_request)
        intent_name = intent_info.get("intent")

        # 1. Static Information (no LLM, no web search needed)
        if intent_name == "INFORMATION":
            static_ans = default_cognition.handle_static_information(effective_request)
            if static_ans:
                default_short_term_memory.add_turn(user_request, static_ans)
                profiler.record_route("COGNITIVE_ENGINE", "STATIC_INFO")
                profiler.record_total()
                profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
                telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
                telemetry.llm_calls_this_request = 0
                telemetry.provenance = "STATIC"
                default_telemetry.finish_request()
                return static_ans

        # 2. Web Research (freshness / live information)
        if intent_name == "RESEARCH":
            research_res = default_cognition.execute_web_research(effective_request)
            res_text = research_res.get("text", "")
            default_short_term_memory.add_turn(user_request, res_text, referenced_query=effective_request)
            profiler.record_route("COGNITIVE_ENGINE", "WEB_RESEARCH")
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            synthesis_resp = getattr(default_cognition, "last_synthesis_response", None)
            if research_res.get("model_used") or (synthesis_resp and synthesis_resp.success):
                telemetry.llm_calls_this_request = 1
                telemetry.provenance = "WEB + MODEL"
                telemetry.reasoning_required = True
                if synthesis_resp:
                    telemetry.cloud_attempted = synthesis_resp.cloud_attempted
                    telemetry.llm_provider = synthesis_resp.provider
                    telemetry.llm_time_ms = synthesis_resp.duration_ms
                else:
                    telemetry.llm_provider = research_res.get("provider") or "groq"
            else:
                telemetry.llm_calls_this_request = 0
                telemetry.provenance = "WEB"
            default_telemetry.finish_request()
            return res_text

        # 3. Ambiguous request with clarification
        if intent_name == "AMBIGUOUS" and intent_info.get("clarification"):
            clarification = intent_info.get("clarification")
            default_short_term_memory.add_turn(user_request, clarification)
            profiler.record_route("COGNITIVE_ENGINE", "AMBIGUOUS_CLARIFICATION")
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            telemetry.provenance = "STATIC"
            default_telemetry.finish_request()
            return clarification

        # 4. Autonomous Compound / Task Goal Execution
        if intent_name in ("COMPOUND_GOAL", "TASK_GOAL"):
            auto_plan = default_cognition.plan_autonomous_goal(effective_request)
            if auto_plan:
                profiler.record_route("COGNITIVE_ENGINE", "AUTONOMOUS_GOAL")
                res = execute_plan(auto_plan, registry, profiler, effective_request, mode="AUTO", quiet=quiet, debug=debug)
                default_short_term_memory.add_turn(user_request, res)
                profiler.record_total()
                profiler.log_summary(user_request, mode="AUTO", status="SUCCESS" if auto_plan.status == "COMPLETED" else "FAILED")
                telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
                resp_plan = getattr(default_cognition, "last_planning_response", None)
                if resp_plan:
                    telemetry.llm_calls_this_request = 1
                    telemetry.provenance = "MODEL"
                    telemetry.reasoning_required = True
                    telemetry.llm_provider = resp_plan.provider
                    telemetry.llm_time_ms = resp_plan.duration_ms
                    telemetry.fallback_used = resp_plan.fallback_used
                else:
                    telemetry.llm_calls_this_request = 0
                    telemetry.provenance = "WORLD_STATE"
                telemetry.goal_status = auto_plan.goal_state.status
                default_telemetry.finish_request()
                return res

        # 5. Diagnostic / Troubleshooting (Evidence-First)
        if intent_name == "TROUBLESHOOTING":
            diag_res = default_cognition.inspect_and_troubleshoot(effective_request)
            default_short_term_memory.add_turn(user_request, diag_res)
            profiler.record_route("COGNITIVE_ENGINE", "TROUBLESHOOTING_EVIDENCE")
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.provenance = "OBSERVED EVIDENCE + MODEL" if "Analysis & Remedies:" in diag_res else "OBSERVED"
            if "Analysis & Remedies:" in diag_res:
                telemetry.llm_calls_this_request = 1
                telemetry.reasoning_required = True
            else:
                telemetry.llm_calls_this_request = 0
            default_telemetry.finish_request()
            return diag_res

        # 6. Unverifiable Epistemic Refusal (extraterrestrial/unobservable real-time events)
        if intent_name == "UNVERIFIABLE":
            unverifiable_ans = intent_info.get("message", "I do not have verified real-time information for that query.")
            default_short_term_memory.add_turn(user_request, unverifiable_ans)
            profiler.record_route("COGNITIVE_ENGINE", "EPISTEMIC_SAFETY")
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            telemetry.provenance = "STATIC"
            default_telemetry.finish_request()
            return unverifiable_ans

        # 7. General Open-Ended Reasoning (Comparative, Explanatory)
        if intent_name == "GENERAL_REASONING":
            profiler.record_route("COGNITIVE_ENGINE", "GENERAL_REASONING")
            t_llm_start = time.perf_counter()
            reasoning_ans = default_cognition.process_reasoning_query(effective_request)
            t_llm_end = time.perf_counter()
            default_short_term_memory.add_turn(user_request, reasoning_ans)
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.reasoning_required = True
            telemetry.llm_calls_this_request = 1
            resp_obj = getattr(default_cognition, "last_reasoning_response", None)
            if resp_obj:
                telemetry.cloud_attempted = resp_obj.cloud_attempted
                telemetry.llm_provider = resp_obj.provider
                telemetry.llm_time_ms = resp_obj.duration_ms if resp_obj.duration_ms > 0 else (t_llm_end - t_llm_start) * 1000.0
                telemetry.fallback_used = resp_obj.fallback_used
                telemetry.cloud_failure_reason = resp_obj.cloud_failure_reason
            else:
                groq_avail = default_gateway.providers["groq"].is_available()
                gemini_avail = default_gateway.providers["gemini"].is_available()
                telemetry.cloud_attempted = groq_avail or gemini_avail
                telemetry.llm_provider = "groq" if groq_avail else "gemini"
                telemetry.llm_time_ms = (t_llm_end - t_llm_start) * 1000.0
            telemetry.provenance = "MODEL"
            default_telemetry.finish_request()
            return reasoning_ans

    # Execution Mode Determination
    exec_mode = determine_execution_mode(user_request)
    gui_browser_req = any(kw in user_request.lower() for kw in APPROVED_BROWSER_KEYWORDS)

    task_state = TaskState(user_request)

    # Phase 11: World State & Task Context Sync
    default_world_state.sync_from_system()
    default_world_state.set_active_task(user_request)

    history = []
    step_count = 0
    non_progress_count = 0

    while step_count < max_steps:
        step_count += 1
        task_state.task_status = "PLANNING" if step_count == 1 else "OBSERVING"
        prompt = build_planner_prompt(user_request, history)

        if debug:
            print(f"\n--- [DEBUG] STEP {step_count} PROMPT (TaskState: {task_state.task_status}) ---")
            print(f"USER REQUEST: {user_request}")
            print(f"PROMPT CHAR COUNT: {len(prompt)}")
            print(f"PROMPT ESTIMATED TOKENS: {len(prompt) // 4}")

        # Cognitive Multi-Model Gateway generation (local action planner loop)
        t0 = time.time()
        resp = default_gateway.generate(prompt=prompt, tier="LOCAL", timeout=120.0)
        t1 = time.time()
        profiler.record_llm(t1 - t0)

        if not resp.success:
            task_state.task_status = "FAILED"
            default_world_state.set_active_task(None)
            default_memory.record_event("TASK", f"Goal: {user_request}", status="FAILED")
            profiler.record_total()
            profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
            return f"Brain Error: {resp.error}"

        raw_output = resp.text.strip()
        gen_ms = resp.duration_ms or ((t1 - t0) * 1000.0)

        llm_telemetry = {
            "llm_called": True,
            "provider": resp.provider,
            "endpoint": resp.provider,
            "fallback_used": resp.fallback_used,
            "request_started": t0,
            "request_finished": t1,
            "generation_time_ms": gen_ms,
            "prompt_size": len(prompt),
            "response_length": len(raw_output)
        }
        if not quiet:
            print(f"[LLM_TELEMETRY] llm_called=True model={resp.model} endpoint={resp.provider} gen_time_ms={gen_ms:.2f} prompt_chars={len(prompt)} resp_chars={len(raw_output)}")

        if debug:
            print(f"[DEBUG] MODEL ({resp.provider}) RESPONSE DURATION: {t1 - t0:.2f}s")
            print(f"[DEBUG] RAW MODEL RESPONSE: {raw_output}")

        action, err = parse_model_action(raw_output)
        if debug:
            print(f"[DEBUG] PARSED ACTION: {action} (err={err})")

        if err or not action:
            task_state.task_status = "FAILED"
            default_world_state.set_active_task(None)
            default_memory.record_event("TASK", f"Goal: {user_request}", status="FAILED")
            profiler.record_total()
            profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
            return f"Brain Error: Invalid model response ({err}). Request halted."

        task_state.update_action(action)

        if action["type"] == "final":
            task_state.task_status = "COMPLETED"
            default_world_state.set_active_task(None)
            default_memory.record_event("TASK", f"Goal: {user_request}", status="COMPLETED")
            profiler.record_total()
            profiler.log_summary(user_request, mode=exec_mode, status="SUCCESS")
            return action.get("answer", "Task complete.")

        if action["type"] == "plan":
            plan_obj = action.get("plan")
            if plan_obj:
                res = execute_plan(plan_obj, registry, profiler, user_request, mode=exec_mode, quiet=quiet, debug=debug)
                profiler.record_total()
                profiler.log_summary(user_request, mode=exec_mode, status="SUCCESS" if plan_obj.status == "COMPLETED" else "FAILED")
                return res

        if action["type"] == "tool":
            tool_name = action.get("tool", "").upper()
            args = action.get("arguments", {})

            # Terminal Safety Gate check before execution
            is_safe, safety_err = validate_gui_action_safety(tool_name, args)
            if not is_safe:
                task_state.task_status = "FAILED"
                profiler.record_total()
                profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
                return f"Brain Error: {safety_err}"

            # Prevent infinite loops on consecutive identical actions
            action_hash = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
            last_hash = history[-1]["action_hash"] if history and "action_hash" in history[-1] else None
            if action_hash == last_hash:
                task_state.task_status = "FAILED"
                profiler.record_total()
                profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
                return f"Brain Error: Repeated identical action '{tool_name}' detected consecutively. Halting to prevent infinite loop."

            if not quiet:
                print(f"Brain: [Step {step_count}/{max_steps}] Executing {tool_name} with args {args}...")

            # Application GUI Task Routing Enforcement:
            # If user explicitly requested doing a browser GUI action (e.g. "Open Brave, search..."),
            # block substitution of background WEB_SEARCH tool to force direct GUI execution in the opened browser.
            if not registry.has_tool(tool_name):
                result = {
                    "success": False,
                    "tool": tool_name,
                    "data": None,
                    "error": f"Tool '{tool_name}' is not registered."
                }
            elif tool_name == "WEB_SEARCH" and gui_browser_req:
                result = {
                    "success": False,
                    "tool": "WEB_SEARCH",
                    "data": None,
                    "error": "Routing Block: The user explicitly requested searching using the Brave browser GUI. Do NOT use WEB_SEARCH. Use desktop GUI interaction tools (ANALYZE_SCREEN, TYPE_IN_ELEMENT, HOTKEY, TYPE_TEXT, PRESS_KEY) to interact directly with the opened browser window."
                }
            else:
                t0_tool = time.time()
                result = registry.execute(tool_name, args)
                t1_tool = time.time()
                profiler.record_tool(tool_name, t1_tool - t0_tool)

            if debug:
                print(f"[DEBUG] TOOL RESULT ({tool_name}): {result}")

            # Verify action outcome and goal progress
            verification_status = "UNVERIFIED"
            is_read_only = tool_name in ("ANALYZE_SCREEN", "SCREENSHOT", "TIME", "LIST_APPS")
            last_was_read_only = bool(history and history[-1]["action"].get("tool", "").upper() in ("ANALYZE_SCREEN", "SCREENSHOT", "TIME", "LIST_APPS"))

            if is_read_only and last_was_read_only:
                # Consecutive read-only perception without state modification indicates lack of progress
                non_progress_count += 1
                verification_status = "VERIFIED" if result.get("success") else "UNVERIFIED"
            elif result.get("success"):
                verification_status = "VERIFIED"
                non_progress_count = 0
            else:
                non_progress_count += 1

            task_state.update_result(result, verification_status=verification_status)
            default_world_state.record_action_outcome(tool_name, args, result, verified=result.get("success", False))

            # Bounded Recovery Check
            if not result.get("success"):
                from core.recovery import default_recovery_manager
                diag_code, diag_expl = default_recovery_manager.diagnose_failure(tool_name, args, result)

                # INVALID_TOOL: do not burn normal tool execution recovery attempts
                if diag_code == "INVALID_TOOL":
                    task_state.recovery_attempts = max(0, task_state.recovery_attempts - 1)

                if task_state.recovery_attempts > MAX_RECOVERY_ATTEMPTS:
                    task_state.task_status = "FAILED"
                    default_world_state.set_active_task(None)
                    default_memory.record_event("TASK", f"Goal: {user_request}", status="FAILED")
                    profiler.record_total()
                    profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
                    return f"Brain Error: Action '{tool_name}' failed after {task_state.recovery_attempts} recovery attempts ({diag_expl}). Halting."

                strat = default_recovery_manager.determine_recovery_strategy(tool_name, args, diag_code, max(0, task_state.recovery_attempts - 1))
                if not quiet:
                    print(f"Brain: Notice - Action '{tool_name}' failed (Attempt {task_state.recovery_attempts}/{MAX_RECOVERY_ATTEMPTS}). Recovery strategy: {strat.get('message')}")

                if strat.get("action") == "REFOCUS":
                    focus_app(strat.get("target_app") or "brave")
                elif strat.get("action") == "REFRESH_PERCEPTION":
                    analyze_captured_screen(force_refresh=True)

            # Progress & Loop Detection Check
            if non_progress_count >= 3:
                task_state.task_status = "FAILED"
                default_world_state.set_active_task(None)
                default_memory.record_event("TASK", f"Goal: {user_request}", status="FAILED")
                profiler.record_total()
                profiler.log_summary(user_request, mode=exec_mode, status="FAILED")
                return "Brain Error: Halting execution because 3 consecutive actions produced no progress toward completing the goal."

            # Record in task memory history
            history.append({
                "action": action,
                "result": result,
                "action_hash": action_hash
            })

            # Smart Observation Policy: refresh screen observation after UI-changing tools
            if tool_name in UI_MODIFYING_TOOLS and result.get("success"):
                analyze_captured_screen(force_refresh=True)

            # Print tool result notice
            if not quiet:
                if not result.get("success"):
                    print(f"Brain: Tool {tool_name} returned failure: {result.get('error')}")
                else:
                    if tool_name in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP"):
                        print(f"Brain: {result.get('data')}")

    profiler.record_total()
    default_world_state.set_active_task(None)
    default_memory.record_event("TASK", f"Goal: {user_request}", status="MAX_STEPS")
    profiler.log_summary(user_request, mode=exec_mode, status="MAX_STEPS")
    return f"Brain Notice: Maximum plan execution limit ({max_steps} steps) reached."



def run_brain():
    """Main interactive execution loop for Brain."""
    import sys
    import os
    companion_mode = "--companion" in sys.argv
    voice_mode = "--voice" in sys.argv or companion_mode

    if voice_mode:
        os.environ["BRAIN_VOICE"] = "1"

    if companion_mode:
        from core.config import companion_config
        from models.gateway import ModelRuntimeStatus
        print("=" * 60)
        print("  BRAIN — DESKTOP AI COMPANION")
        print(f"  Mind: {ModelRuntimeStatus.get_runtime_identity_summary()}")
        print(f"  Voice: {'Active' if companion_config.voice.enabled else 'Muted'} | Avatar: http://{companion_config.avatar.host}:{companion_config.avatar.port}/")
        print("=" * 60)
        from body.server import start_companion_server, launch_companion_window
        from core.watcher import default_watcher
        from bridge import DesktopMateBridge
        from core.desktop_presence import DesktopPresenceManager

        # Ensure live Desktop Mate desktop presence
        presence_mgr = DesktopPresenceManager()
        pres_res = presence_mgr.ensure_running()
        if pres_res.get("success"):
            print(f"Brain: Live Desktop Mate active (Window ID: {pres_res.get('window_id')})")
        else:
            print(f"Brain Notice: Desktop Mate desktop presence status: {pres_res.get('error')}")

        start_companion_server(host=companion_config.avatar.host, port=companion_config.avatar.port)
        launch_companion_window()
        
        # Start DesktopMate Bridge
        bridge = DesktopMateBridge()
        bridge.start()
        print("Brain: DesktopMate Bridge initialized.")

        if companion_config.presence.background_watcher:
            default_watcher.start()
        print(f"Brain: Companion active | Live Desktop Mate & Bridge online")

    print("Brain PC Assistant ready. Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Brain. Goodbye!")
            break

        # Empty line handling: prompt again without sending to the LLM
        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("Exiting Brain. Goodbye!")
            break

        final_response = run_planner_task(user_input)
        print(f"\nBrain: {final_response}")


if __name__ == "__main__":
    run_brain()