"""
Brain Bounded Agent Loop (Phase 19 Companion Evolution).
Implements the autonomous agent loop:
UNDERSTAND -> CONTEXTUALIZE -> FORM GOAL -> CHECK SAFETY -> SELECT SKILL -> PLAN -> ACT -> OBSERVE -> VERIFY -> ADAPT -> COMPLETE
Strictly enforces registered tool validation, bounded retries, and evidence-grounded verification.
"""

import time
from typing import Dict, Any, List, Optional
from tools.registry import default_registry
from tools.router import FastRouter
from core.skills import default_skills, SkillDefinition
from core.goals import default_goals, PersistentGoal
from core.world_state import default_world_state
from core.context import default_short_term_memory
from core.telemetry import default_telemetry
from tools.apps import verify_app_open
from tools.input import validate_gui_action_safety, screen_prompt_safety
from tools.screen import analyze_captured_screen
from tools.vision import default_vision


class AgentLoop:
    """Bounded, evidence-grounded execution loop for Brain AI companion."""

    def __init__(self, registry=None, skills=None, goals=None):
        self.registry = registry or default_registry
        self.skills = skills or default_skills
        self.goals = goals or default_goals
        self.fast_router = FastRouter()
        self.max_steps_per_turn = 8
        self.max_retries_per_step = 2

    def run(self, user_request: str, quiet: bool = True) -> Dict[str, Any]:
        """
        Executes a single user request through the full bounded agent lifecycle.
        Returns structured execution report dict.
        """
        t0 = time.time()
        telemetry = default_telemetry.start_request(user_request)

        # Update Session & Generation token
        from core.session import default_session_manager
        from core.event_bus import default_event_bus
        from core.resource_governor import default_resource_governor
        from core.autonomy import default_proactive_awareness, default_autonomy_controller


        gen_id = default_session_manager.bump_generation()
        default_session_manager.update_session(user_input=user_request, task=user_request)
        default_event_bus.publish("USER_MESSAGE", {"request": user_request, "generation_id": gen_id})
        default_resource_governor.check_and_govern()
        default_proactive_awareness.inspect_environment()

        # 1. UNDERSTAND & IMMEDIATE SAFETY CHECK
        is_safe, safety_err = screen_prompt_safety(user_request)
        if not is_safe:
            telemetry.total_ms = (time.time() - t0) * 1000.0
            default_telemetry.finish_request()
            default_event_bus.publish("SAFETY_BLOCK", {"request": user_request, "error": safety_err})
            return {
                "success": False,
                "status": "BLOCKED",
                "answer": safety_err,
                "evidence": ["Immediate prompt safety gate block triggered"]
            }

        # 2. CONTEXTUALIZE & CHECK RESUMPTION / GOAL STATUS
        lowered = user_request.lower().strip()
        if lowered in ("continue", "continue what we were doing", "brain, continue the project", "continue project", "what am i currently working on", "what are we doing"):
            active_goal = self.goals.get_active_goal()
            if active_goal:
                progress = active_goal.progress_summary()
                telemetry.total_ms = (time.time() - t0) * 1000.0
                default_telemetry.finish_request()
                return {
                    "success": True,
                    "status": active_goal.status,
                    "answer": f"Current active project:\n{progress}",
                    "evidence": [f"Active goal {active_goal.id} resumed"]
                }
            else:
                telemetry.total_ms = (time.time() - t0) * 1000.0
                default_telemetry.finish_request()
                return {
                    "success": True,
                    "status": "IDLE",
                    "answer": "We don't have an active background project paused right now. What would you like to start?",
                    "evidence": []
                }

        # 3. FAST ROUTER PRE-CHECK (Deterministic answers, system state, zero LLM)
        fast_route = self.fast_router.route(user_request)
        if fast_route:
            rtype = fast_route.get("type")
            if rtype == "final":
                telemetry.total_ms = (time.time() - t0) * 1000.0
                telemetry.deterministic_success = True
                default_telemetry.finish_request()
                default_event_bus.publish("TASK_COMPLETED", {"route": "fast_route", "answer": fast_route.get("answer")})
                return {
                    "success": True,
                    "status": "COMPLETED",
                    "answer": fast_route.get("answer"),
                    "evidence": ["Direct deterministic fast route match"]
                }

        # 4. SELECT SKILL (Procedural Memory Lookup)
        matched_skill = self.skills.match_skill(user_request)
        plan = None
        if matched_skill:
            if not quiet:
                print(f"Brain: Matched procedural skill '{matched_skill.name}'.")
            plan = matched_skill.to_execution_plan(user_request)

        # 5. FORM GOAL & PLAN (Compound planning or fast router plan)
        if not plan:
            if fast_route and fast_route.get("type") == "plan":
                plan = fast_route.get("plan")
            else:
                from core.cognition import default_cognition
                plan = default_cognition.plan_autonomous_goal(user_request)

        # If still no plan, route to cognition / reasoning
        if not plan:
            from core.cognition import default_cognition
            reasoning_res = default_cognition.process_reasoning_query(user_request)
            telemetry.total_ms = (time.time() - t0) * 1000.0
            default_telemetry.finish_request()
            return {
                "success": True,
                "status": "COMPLETED",
                "answer": reasoning_res,
                "evidence": ["Cognitive reasoning model output"]
            }

        # 6. ACT -> OBSERVE -> VERIFY LOOP
        step_idx = 0
        collected_evidence = []
        last_tool_res = None
        default_autonomy_controller.start_autonomy(user_request)

        while not plan.is_complete() and step_idx < len(plan.steps) and step_idx < self.max_steps_per_turn:
            can_cont, stop_reason = default_autonomy_controller.can_continue()
            if not can_cont:
                plan.status = "PAUSED"
                return {
                    "success": False,
                    "status": "PAUSED",
                    "answer": f"Autonomy controller paused execution: {stop_reason}",
                    "evidence": collected_evidence
                }

            step = plan.steps[step_idx]
            step_idx += 1
            plan.current_step_idx = step_idx - 1

            if step.action_type == "final":
                plan.status = "COMPLETED"
                break

            tool_name = step.tool_name.upper()
            args = step.arguments

            # Strict Safety Gate before tool execution
            is_tool_safe, tool_safety_err = validate_gui_action_safety(tool_name, args)
            if not is_tool_safe:
                plan.status = "FAILED"
                step.status = "FAILED"
                step.error = tool_safety_err
                default_event_bus.publish("SAFETY_BLOCK", {"tool": tool_name, "error": tool_safety_err})
                return {
                    "success": False,
                    "status": "BLOCKED",
                    "answer": f"Brain Safety Block: {tool_safety_err}",
                    "evidence": collected_evidence
                }

            # Confirmation Manager Check (Stage 7J)
            from core.confirmation import default_confirmation_manager
            conf_status, conf_req = default_confirmation_manager.evaluate_action(tool_name, args)
            if conf_status == "REQUIRED" and conf_req:
                plan.status = "PAUSED"
                return {
                    "success": False,
                    "status": "CONFIRMATION_REQUIRED",
                    "answer": f"Action '{tool_name}' is sensitive and requires explicit user confirmation (Request ID: {conf_req.request_id}).",
                    "evidence": collected_evidence,
                    "confirmation_request": conf_req.to_dict()
                }

            # Tool Execution with Registered Registry
            if not self.registry.has_tool(tool_name):
                step.status = "FAILED"
                step.error = f"Tool '{tool_name}' is not in the approved tool registry."
                return {
                    "success": False,
                    "status": "FAILED",
                    "answer": f"Execution halted: Unknown action '{tool_name}'.",
                    "evidence": collected_evidence
                }

            # Stage 6G / 7E Interruption & Generation Check
            from core.companion_state import default_interruption_controller
            if default_interruption_controller.is_cancelled():
                default_interruption_controller.reset()
                plan.status = "INTERRUPTED"
                default_autonomy_controller.cancel("user_interruption")
                return {
                    "success": False,
                    "status": "INTERRUPTED",
                    "answer": "Action interrupted by user request.",
                    "evidence": collected_evidence
                }

            if not quiet:
                print(f"Brain: [Step {step_idx}/{len(plan.steps)}] {tool_name} with args {args}")

            # Update CompanionState to WORKING
            from core.companion_state import default_companion_state, CompanionActivity
            default_companion_state.set_state(
                activity=CompanionActivity.WORKING,
                action=tool_name,
                task=f"Executing {tool_name}"
            )

            res = self.registry.execute(tool_name, args)
            last_tool_res = res
            default_autonomy_controller.record_step(res.get("success", False))

            # 7. OBSERVE & VERIFY (Stage 6C & 6D Smart Observation Policy)
            from core.perception import default_perception_router
            from tools.screen import cleanup_screenshots

            should_sub_observe = default_perception_router.policy.should_observe(
                last_action=tool_name,
                action_executed=res.get("success", False)
            )

            if should_sub_observe:
                post_obs = default_perception_router.perceive(force_refresh=True, last_action_result=res)
                cleanup_screenshots(keep_latest=True)
            else:
                post_obs = default_perception_router.get_last_result() or default_perception_router.perceive()

            verified = False

            if tool_name == "OPEN_APP":
                app_to_check = args.get("app_name", "")
                ver_res = verify_app_open(app_to_check, timeout=1.5)
                verified = ver_res.get("verified", False)
                if not verified:
                    step.status = "FAILED"
                    step.error = ver_res.get("error", f"App '{app_to_check}' failed readiness check.")
                    # Bounded 1-retry recovery
                    time.sleep(0.5)
                    ver_res_retry = verify_app_open(app_to_check, timeout=1.5)
                    if ver_res_retry.get("verified"):
                        verified = True
                    else:
                        plan.status = "FAILED"
                        default_companion_state.set_state(activity=CompanionActivity.ERROR, verification="FAILED")
                        return {
                            "success": False,
                            "status": "FAILED",
                            "answer": f"Action failed: {step.error}",
                            "evidence": collected_evidence
                        }
            else:
                verified = res.get("success", False)

            if verified:
                step.status = "COMPLETED"
                step.result = res
                obs_app = getattr(post_obs, "application", "desktop")
                obs_state = getattr(post_obs, "screen_state", "NORMAL")
                collected_evidence.append(f"{tool_name}: Success [Observed window: '{obs_app}', state: {obs_state}]")
                default_world_state.record_action_outcome(tool_name, args, res, verified=True, verification_status="CONFIRMED")
                default_companion_state.set_state(activity=CompanionActivity.SUCCESS, verification="CONFIRMED")
            else:
                step.status = "FAILED"
                default_companion_state.set_state(activity=CompanionActivity.ERROR, verification="FAILED")
                if not step.allow_failure:
                    plan.status = "FAILED"
                    return {
                        "success": False,
                        "status": "FAILED",
                        "answer": f"Action '{tool_name}' did not produce the expected evidence.",
                        "evidence": collected_evidence
                    }

        plan.status = "COMPLETED"
        default_autonomy_controller.complete()
        telemetry.total_ms = (time.time() - t0) * 1000.0
        default_telemetry.finish_request()

        # Build final response text
        final_ans = f"Completed {len(plan.steps)} steps successfully."
        if plan.steps and plan.steps[-1].action_type == "final" and plan.steps[-1].answer:
            final_ans = plan.steps[-1].answer

        from core.companion_state import default_companion_state, CompanionActivity
        default_companion_state.set_state(activity=CompanionActivity.IDLE)
        default_session_manager.update_session(brain_response=final_ans)

        return {
            "success": True,
            "status": "COMPLETED",
            "answer": final_ans,
            "evidence": collected_evidence,
            "plan_steps": len(plan.steps)
        }

    def _explain_failure(self, tool_name: str, arguments: Dict[str, Any], error_reason: str) -> str:
        """Stage 7K — Structured, evidence-grounded failure explanation layer."""
        return (
            f"Attempted action: {tool_name} with arguments {arguments}.\n"
            f"Result: Execution failed.\n"
            f"Reason: {error_reason}.\n"
            f"Verification: Could not verify expected state change.\n"
            f"Recovery: Safe to retry or ask user for guidance."
        )


default_agent_loop = AgentLoop()

