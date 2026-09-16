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

        # 1. UNDERSTAND & IMMEDIATE SAFETY CHECK
        is_safe, safety_err = screen_prompt_safety(user_request)
        if not is_safe:
            telemetry.total_ms = (time.time() - t0) * 1000.0
            default_telemetry.finish_request()
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

        while not plan.is_complete() and step_idx < len(plan.steps) and step_idx < self.max_steps_per_turn:
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
                return {
                    "success": False,
                    "status": "BLOCKED",
                    "answer": f"Brain Safety Block: {tool_safety_err}",
                    "evidence": collected_evidence
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

            if not quiet:
                print(f"Brain: [Step {step_idx}/{len(plan.steps)}] {tool_name} with args {args}")

            res = self.registry.execute(tool_name, args)
            last_tool_res = res

            # 7. OBSERVE & VERIFY
            verified = False
            v_method = step.verification_method

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
                        return {
                            "success": False,
                            "status": "FAILED",
                            "answer": f"Action failed: {step.error}",
                            "evidence": collected_evidence
                        }
                default_world_state.last_opened_app = app_to_check
            else:
                verified = res.get("success", False)

            if verified:
                step.status = "COMPLETED"
                step.result = res
                collected_evidence.append(f"{tool_name}: Success")
                default_world_state.record_action_outcome(tool_name, args, res, verified=True)
            else:
                step.status = "FAILED"
                if not step.allow_failure:
                    plan.status = "FAILED"
                    return {
                        "success": False,
                        "status": "FAILED",
                        "answer": f"Action '{tool_name}' did not produce the expected evidence.",
                        "evidence": collected_evidence
                    }

        plan.status = "COMPLETED"
        telemetry.total_ms = (time.time() - t0) * 1000.0
        default_telemetry.finish_request()

        # Build final response text
        final_ans = f"Completed {len(plan.steps)} steps successfully."
        if plan.steps and plan.steps[-1].action_type == "final" and plan.steps[-1].answer:
            final_ans = plan.steps[-1].answer

        return {
            "success": True,
            "status": "COMPLETED",
            "answer": final_ans,
            "evidence": collected_evidence,
            "plan_steps": len(plan.steps)
        }


default_agent_loop = AgentLoop()
