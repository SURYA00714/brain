"""
Brain Router Pipeline.
Handles deterministic fast pre-routing, conversational shortcuts, single-pass plans,
and low-latency direct tool dispatches without invoking the LLM.
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional

from brain_constants import UI_MODIFYING_TOOLS
from tools.router import default_router
from tools.input import validate_gui_action_safety
from tools.screen import analyze_captured_screen
from core.context import default_short_term_memory
from core.world_state import default_world_state
from core.telemetry import default_telemetry
from core.formatter import format_tool_response
from core.executor import execute_plan


@dataclass
class FastRouteResult:
    handled: bool
    response: Optional[str] = None
    fallback_needed: bool = False
    error: Optional[str] = None


def process_fast_route(
    user_request: str,
    effective_request: str,
    registry: Any,
    profiler: Any,
    t_req_start: float,
    quiet: bool = False,
    debug: bool = False
) -> FastRouteResult:
    """
    Evaluates deterministic router for the user request.
    Returns FastRouteResult indicating whether request was completely handled or needs fallback.
    """
    telemetry = default_telemetry.current

    # Phase 1.9: Deterministic AST math, conversions, percentages, and sequences fast path (<1ms)
    from core.math_logic import try_deterministic_math_or_logic, evaluate_counterfactual_scenario
    det_math = try_deterministic_math_or_logic(effective_request)
    if det_math and det_math.get("solved"):
        ans = det_math.get("answer", "")
        default_short_term_memory.add_turn(user_request, str(ans))
        profiler.record_route("DETERMINISTIC_AST_MATH", det_math.get("method", "math"))
        profiler.record_total()
        profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
        telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
        telemetry.llm_calls_this_request = 0
        telemetry.provenance = "STATIC"
        default_telemetry.finish_request()
        return FastRouteResult(handled=True, response=f"{ans}")

    # Counterfactual reasoning fast path
    if any(k in effective_request.lower() for k in ("what if", "suppose", "assuming")):
        cf_res = evaluate_counterfactual_scenario(effective_request)
        if cf_res.get("valid") and "conclusion" in cf_res:
            ans = cf_res["conclusion"]
            default_short_term_memory.add_turn(user_request, ans)
            profiler.record_route("COUNTERFACTUAL_EVALUATOR", "REASONING")
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            telemetry.provenance = "STATIC"
            default_telemetry.finish_request()
            return FastRouteResult(handled=True, response=ans)

    t_route_start = time.perf_counter()
    fast_match = default_router.route(effective_request)
    t_route_end = time.perf_counter()

    if not fast_match:
        profiler.record_router(t_route_end - t_route_start, matched=False)
        return FastRouteResult(handled=False)

    tool_name_matched = fast_match.get("tool", "") or ("PLAN" if fast_match.get("type") == "plan" else "")
    profiler.record_router(t_route_end - t_route_start, matched=True, tool_name=tool_name_matched)
    action_type = fast_match.get("type", "").lower()

    # 1. Final direct response (chat, help, identity, system state queries)
    if action_type == "final":
        answer = fast_match.get("answer", "Hello! How can I assist you today?")
        default_short_term_memory.add_turn(user_request, answer)
        profiler.record_route("FAST_ROUTER", "CHAT")
        profiler.record_total()
        profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
        telemetry.classifier_ms = (t_route_end - t_route_start) * 1000.0
        telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
        telemetry.llm_calls_this_request = 0
        if "name" in user_request.lower() or "talked about" in user_request.lower() or "discussed" in answer:
            telemetry.provenance = "MEMORY"
        elif "app" in user_request.lower():
            telemetry.provenance = "WORLD_STATE"
        else:
            telemetry.provenance = "STATIC"
        default_telemetry.finish_request()
        return FastRouteResult(handled=True, response=answer)

    # 2. Pre-computed deterministic multi-step plan
    if action_type == "plan":
        plan_obj = fast_match.get("plan")
        if plan_obj:
            profiler.record_route("FAST_ROUTER", "MULTI_STEP_PLAN")
            res = execute_plan(plan_obj, registry, profiler, user_request, mode="AUTO", quiet=quiet, debug=debug)
            app_ref = None
            query_ref = None
            for step in plan_obj.steps:
                if step.tool_name in ("OPEN_APP", "FOCUS_APP"):
                    app_ref = step.arguments.get("app_name")
                elif "SEARCH" in step.tool_name:
                    query_ref = step.arguments.get("query")
            default_short_term_memory.add_turn(
                user_text=user_request,
                agent_response=res,
                referenced_app=app_ref,
                referenced_query=query_ref,
                tool_used="PLAN"
            )
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS" if plan_obj.status == "COMPLETED" else "FAILED")
            telemetry.classifier_ms = (t_route_end - t_route_start) * 1000.0
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            telemetry.provenance = "WORLD_STATE"
            telemetry.goal_status = plan_obj.goal_state.status
            default_telemetry.finish_request()
            return FastRouteResult(handled=True, response=res)

    # 3. Direct single tool execution
    if action_type == "tool":
        tool_name = fast_match.get("tool", "").upper()
        args = fast_match.get("arguments", {})
        profiler.record_route("FAST_ROUTER", tool_name)

        # Safety Gate check before FastRoute execution
        is_safe, safety_err = validate_gui_action_safety(tool_name, args)
        if not is_safe:
            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="FAILED")
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            default_telemetry.finish_request()
            return FastRouteResult(handled=True, response=f"Brain Error: {safety_err}")

        if not quiet:
            print(f"Brain: [FastRoute] Executing {tool_name} with args {args}...")

        t_start = time.perf_counter()
        result = registry.execute(tool_name, args)
        t_end = time.perf_counter()
        profiler.record_tool(tool_name, t_end - t_start, is_gui=(tool_name in UI_MODIFYING_TOOLS))

        # Physical State Verification
        if result.get("success"):
            if tool_name == "OPEN_APP":
                app_to_check = args.get("name") or args.get("app_name") or ""
                from tools.apps import verify_app_open
                default_world_state.sync_from_system()
                ver_res = verify_app_open(app_to_check, timeout=1.5)
                if not ver_res.get("verified"):
                    result = {"success": False, "error": f"Verification failed: Process '{app_to_check}' not detected in system state."}
                    telemetry.false_verification = True
                else:
                    default_world_state.last_opened_app = app_to_check
                    telemetry.verification_method = ver_res.get("method", "multi_signal")
            elif tool_name == "CLOSE_APP":
                app_to_check = args.get("app_name", "")
                from tools.apps import default_app_tracker
                default_world_state.sync_from_system()
                if os.environ.get("BRAIN_MOCK_GUI") != "1" and default_app_tracker.is_running(app_to_check):
                    result = {"success": False, "error": f"Verification failed: Process '{app_to_check}' is still active."}

        if result.get("success"):
            if tool_name in UI_MODIFYING_TOOLS:
                t_obs0 = time.perf_counter()
                analyze_captured_screen(force_refresh=True)
                t_obs1 = time.perf_counter()
                profiler.record_verification(t_obs1 - t_obs0)

            resp = format_tool_response(tool_name, result, args)

            app_ref = args.get("app_name") if tool_name in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP") else None
            query_ref = args.get("query") if "SEARCH" in tool_name else None
            default_short_term_memory.add_turn(
                user_text=user_request,
                agent_response=resp,
                referenced_app=app_ref,
                referenced_query=query_ref,
                tool_used=tool_name
            )

            profiler.record_total()
            profiler.log_summary(user_request, mode="AUTO", status="SUCCESS")
            telemetry.classifier_ms = (t_route_end - t_route_start) * 1000.0
            telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
            telemetry.llm_calls_this_request = 0
            if tool_name == "TIME":
                telemetry.provenance = "STATIC"
            elif tool_name in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP"):
                telemetry.provenance = "WORLD_STATE"
            elif tool_name in ("ANALYZE_SCREEN", "SCREENSHOT", "CHECK_DISK_SPACE"):
                telemetry.provenance = "OBSERVED"
            elif tool_name in ("WEB_SEARCH", "BROWSER_SEARCH"):
                telemetry.provenance = "WEB"
            else:
                telemetry.provenance = "OBSERVED"
            default_telemetry.finish_request()
            return FastRouteResult(handled=True, response=resp)
        else:
            if tool_name == "REMEMBER" or (result.get("error") and any(k in str(result.get("error")) for k in ("Safety Block:", "Verification failed:", "not in the approved safety allowlist", "not installed", "not found"))):
                profiler.record_total()
                profiler.log_summary(user_request, mode="AUTO", status="FAILED")
                telemetry.total_ms = (time.perf_counter() - t_req_start) * 1000.0
                telemetry.llm_calls_this_request = 0
                telemetry.provenance = "STATIC"
                default_telemetry.finish_request()
                return FastRouteResult(handled=True, response=f"Brain Error: {result.get('error')}")

            if not quiet:
                print(f"Brain: FastRoute for {tool_name} returned failure ({result.get('error')}). Falling back to planner loop.")
            return FastRouteResult(handled=False, fallback_needed=True, error=result.get("error"))

    return FastRouteResult(handled=False)
