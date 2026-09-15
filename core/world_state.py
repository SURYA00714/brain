import os
import time
import platform
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from tools.apps import default_app_tracker, get_active_window_app_name, APPROVED_APPS


@dataclass
class WorldState:
    """Snapshot representing verified physical PC and Brain runtime conditions."""
    os_name: str
    user_name: str
    running_apps: List[str] = field(default_factory=list)
    brain_owned_apps: List[str] = field(default_factory=list)
    focused_app: Optional[str] = None
    active_task: Optional[str] = None
    last_action: Optional[str] = None
    last_action_result: Optional[str] = None
    observation_status: str = "UNKNOWN"  # KNOWN, UNKNOWN, STALE
    last_verified_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "os_name": self.os_name,
            "user_name": self.user_name,
            "running_apps": self.running_apps,
            "brain_owned_apps": self.brain_owned_apps,
            "focused_app": self.focused_app,
            "active_task": self.active_task,
            "last_action": self.last_action,
            "last_action_result": self.last_action_result,
            "observation_status": self.observation_status,
            "last_verified_time": self.last_verified_time
        }


class WorldStateManager:
    """
    Maintains and reconciles current operating environment state.
    Guarantees no hallucinated/fake states by validating through AppTracker
    and OS window checks. Detects staleness across restarts or idle gaps.
    """
    def __init__(self, staleness_threshold_seconds: float = 60.0):
        self.staleness_threshold = staleness_threshold_seconds
        self.os_name = f"{platform.system()} {platform.release()}"
        self.user_name = os.environ.get("USER", "user")
        self.current_state = WorldState(
            os_name=self.os_name,
            user_name=self.user_name,
            observation_status="UNKNOWN",
            last_verified_time=0.0
        )

    def sync_from_system(self) -> WorldState:
        """
        Reconciles world state against real system conditions.
        Inspects active window and queries AppTracker for verified processes.
        """
        running_apps = []
        brain_owned_apps = []

        for app in APPROVED_APPS.keys():
            if default_app_tracker.is_running(app):
                running_apps.append(app)
                if default_app_tracker.is_brain_owned(app):
                    brain_owned_apps.append(app)

        # Query OS active window title
        focused = get_active_window_app_name() or default_app_tracker.get_focused_app()

        now = time.time()
        self.current_state.running_apps = sorted(list(set(running_apps)))
        self.current_state.brain_owned_apps = sorted(list(set(brain_owned_apps)))
        self.current_state.focused_app = focused
        self.current_state.last_verified_time = now
        self.current_state.observation_status = "KNOWN"

        return self.current_state

    def check_staleness(self) -> str:
        """
        Evaluates whether current state is fresh, stale, or unknown.
        """
        if self.current_state.last_verified_time == 0.0:
            self.current_state.observation_status = "UNKNOWN"
            return "UNKNOWN"

        age = time.time() - self.current_state.last_verified_time
        if age > self.staleness_threshold:
            self.current_state.observation_status = "STALE"
            return "STALE"

        return "KNOWN"

    def mark_stale(self) -> None:
        """Explicitly marks state as stale (e.g. after system restart or unverified idle gap)."""
        self.current_state.observation_status = "STALE"

    def record_action_outcome(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        verified: bool = False
    ) -> None:
        """
        Records the verified outcome of an executed action into the current world state.
        Never marks state as verified unless execution confirmed it.
        """
        t_upper = str(tool_name).upper()
        self.current_state.last_action = t_upper

        if isinstance(result, dict):
            res_str = result.get("error") if not result.get("success") else str(result.get("data") or "Success")
        else:
            res_str = str(result)
        self.current_state.last_action_result = res_str[:120]

        if verified:
            self.sync_from_system()
        else:
            # Action was performed but not yet verified -> mark state as needing verification
            self.current_state.observation_status = "STALE"

    def set_active_task(self, task_description: Optional[str]) -> None:
        self.current_state.active_task = task_description

    def get_snapshot(self) -> WorldState:
        self.check_staleness()
        return self.current_state

    def get_state_prompt_snippet(self) -> str:
        """
        Produces a compact world-state block for cognitive model prompts.
        Only includes verified or staleness-flagged details.
        """
        self.check_staleness()
        st = self.current_state
        running_str = ", ".join(st.running_apps) if st.running_apps else "none"
        focused_str = st.focused_app or "none"

        status_flag = f"[{st.observation_status}]"
        lines = [
            f"WORLD STATE {status_flag}:",
            f"- Running Applications: {running_str}",
            f"- Focused Window: {focused_str}"
        ]
        if st.last_action:
            lines.append(f"- Last Action: {st.last_action} -> {st.last_action_result}")
        if st.active_task:
            lines.append(f"- Active Task: {st.active_task}")

        return "\n".join(lines)


default_world_state = WorldStateManager()
