

import time
from typing import Dict, Any, Optional, Tuple

from tools.apps import default_app_tracker, focus_app
from core.perception import default_perception_router, PerceptionResult


FAILURE_REASONS = {
    "ACTION_FAILED",
    "ACTION_NOT_VERIFIED",
    "ACTION_BLOCKED_BY_SAFETY",
    "ACTION_IMPOSSIBLE_WITH_AVAILABLE_PERCEPTION",
    "APPLICATION_STATE_UNKNOWN"
}


class AdaptiveRecoveryManager:
    """
    Adaptive Recovery & Failure Diagnostics Engine for Brain Phase 12.
    Diagnoses the root cause of execution failures and devises bounded,
    state-aware recovery strategies without infinite loops.
    """
    def __init__(self, max_recovery_attempts: int = 2):
        self.max_recovery_attempts = max_recovery_attempts

    def diagnose_failure(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        perception: Optional[PerceptionResult] = None
    ) -> Tuple[str, str]:
        """
        Classifies failure into a standardized root cause reason and descriptive explanation.
        Returns: (reason_code: str, explanation: str)
        """
        err = str(result.get("error") or "")

        # 0. Unregistered / Invalid Tool Check
        if "not registered" in err.lower() or "invalid tool" in err.lower() or "does not exist" in err.lower():
            return "INVALID_TOOL", f"Tool '{tool_name}' does not exist in Brain's registered capabilities."

        # 1. Safety Block Check
        if "Safety Block" in err or "Access Denied" in err:
            return "ACTION_BLOCKED_BY_SAFETY", f"Action '{tool_name}' was blocked by the deterministic safety controller: {err}"

        # 2. Perception & Element Locating Failures
        if "element" in err.lower() or "not found" in err.lower() or "target" in err.lower():
            if perception and perception.screen_state == "LOADING":
                return "ACTION_NOT_VERIFIED", "Target element not found because application is currently in a LOADING state."
            if perception and perception.screen_state == "ERROR":
                return "ACTION_FAILED", f"Application displayed an ERROR state on screen: {', '.join(perception.detected_text[:3])}"
            return "ACTION_IMPOSSIBLE_WITH_AVAILABLE_PERCEPTION", f"Target element could not be resolved from current screen perception: {err}"

        # 3. Application State & Focus Failures
        if tool_name in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP"):
            app_name = arguments.get("app_name", "")
            if not default_app_tracker.is_running(app_name):
                return "APPLICATION_STATE_UNKNOWN", f"Application '{app_name}' is not currently running or process exited unexpectedly."
            return "ACTION_NOT_VERIFIED", f"Application '{app_name}' action was requested but could not be verified in system state."

        # 4. Tool Execution Failure
        if not result.get("success"):
            return "ACTION_FAILED", f"Tool '{tool_name}' reported execution failure: {err or 'Unknown error'}"

        return "ACTION_NOT_VERIFIED", f"Action '{tool_name}' executed but expected post-condition was not verified."

    def determine_recovery_strategy(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        reason_code: str,
        attempt: int,
        perception: Optional[PerceptionResult] = None
    ) -> Dict[str, Any]:
        """
        Determines the appropriate bounded recovery action based on diagnostic reason.
        Returns recovery instruction dict: {"action": "RETRY" | "REFOCUS" | "WAIT" | "HALT", ...}
        """
        if reason_code == "INVALID_TOOL":
            from tools.registry import default_registry
            available_tools = ", ".join(sorted(t["name"] for t in default_registry.list_tools()))
            return {
                "action": "REPLAN",
                "message": f"Tool '{tool_name}' is not registered. Available tools: {available_tools}."
            }

        if attempt >= self.max_recovery_attempts:
            return {
                "action": "HALT",
                "message": f"Halting: Reached maximum recovery attempts ({self.max_recovery_attempts}) for '{tool_name}'."
            }

        if reason_code == "ACTION_BLOCKED_BY_SAFETY":
            return {
                "action": "HALT",
                "message": "Halting: Safety controller blocks cannot be autonomously bypassed or retried."
            }

        if reason_code == "APPLICATION_STATE_UNKNOWN":
            target_app = arguments.get("app_name") or default_app_tracker.get_focused_app()
            if target_app:
                focus_app(target_app)
            return {
                "action": "REFOCUS",
                "target_app": target_app,
                "message": f"Refocusing application '{target_app}' before re-attempting action."
            }

        if reason_code == "ACTION_IMPOSSIBLE_WITH_AVAILABLE_PERCEPTION":
            # Invalidate cached perception to force a fresh screen capture and OCR pass
            default_perception_router.invalidate_cache()
            return {
                "action": "REFRESH_PERCEPTION",
                "message": "Invalidated stale perception cache. Re-observing screen for updated coordinates."
            }

        if reason_code == "ACTION_NOT_VERIFIED":
            if perception and perception.screen_state == "LOADING":
                return {
                    "action": "WAIT_AND_OBSERVE",
                    "delay": 0.2,
                    "message": "Application is loading. Pausing briefly to allow UI to settle before verifying."
                }

        # Default bounded retry
        return {
            "action": "RETRY",
            "message": f"Retrying action '{tool_name}' (Attempt {attempt + 1}/{self.max_recovery_attempts})."
        }


default_recovery_manager = AdaptiveRecoveryManager()
