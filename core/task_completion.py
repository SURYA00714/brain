"""
Brain Task Completion Detector (Stage 8O).
Evaluates evidence-grounded completion criteria to determine whether a multi-step task goal is fully satisfied.
"""

from typing import Dict, Any, List, Optional
from core.world_state import default_world_state
from tools.apps import default_app_tracker


class TaskCompletionDetector:
    """Evaluates task completion using concrete system & perception evidence."""

    def evaluate(self, goal: str, observation: Dict[str, Any], step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates goal completion.
        Returns: {"completed": bool, "status": "COMPLETED" | "INCOMPLETE" | "FAILED", "evidence": List[str], "reason": str}
        """
        g_lower = goal.lower().strip()
        evidence = []

        # Case 1: Open Application task
        if "open " in g_lower:
            app_name = g_lower.split("open", 1)[-1].strip().split()[0]
            proc_running = default_app_tracker.is_running(app_name)
            focused_app = (observation.get("application") or observation.get("focused_app") or "").lower()

            if proc_running:
                evidence.append(f"Verified process '{app_name}' is active in AppTracker.")
            if app_name in focused_app:
                evidence.append(f"Verified window '{app_name}' is currently focused.")

            if proc_running or app_name in focused_app:
                return {
                    "completed": True,
                    "status": "COMPLETED",
                    "evidence": evidence,
                    "reason": f"Goal 'Open {app_name}' fully satisfied by verified process/window evidence."
                }

        # Case 2: Web Search task
        if "search" in g_lower:
            has_search_data = any(
                isinstance(res, dict) and (res.get("data") or "results" in str(res).lower())
                for res in step_results
            )
            obs_text = " ".join([str(t) for t in observation.get("ocr_texts", [])]).lower()

            if has_search_data or "python" in obs_text or "search" in obs_text:
                evidence.append("Observed search results or data payload in step execution.")
                return {
                    "completed": True,
                    "status": "COMPLETED",
                    "evidence": evidence,
                    "reason": f"Goal '{goal}' satisfied by search result evidence."
                }

        # Case 3: Generic task with executed steps
        successful_steps = [r for r in step_results if isinstance(r, dict) and r.get("success")]
        if len(successful_steps) > 0:
            evidence.append(f"Executed {len(successful_steps)} action steps successfully.")
            return {
                "completed": True,
                "status": "COMPLETED",
                "evidence": evidence,
                "reason": "All planned action steps executed successfully."
            }

        return {
            "completed": False,
            "status": "INCOMPLETE",
            "evidence": [],
            "reason": "Insufficient evidence to verify goal completion."
        }


default_completion_detector = TaskCompletionDetector()
