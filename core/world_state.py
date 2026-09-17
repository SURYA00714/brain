import os
import time
import platform
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from tools.apps import default_app_tracker, get_active_window_app_name, APPROVED_APPS


VERIFICATION_STATUSES = {"CONFIRMED", "LIKELY", "UNKNOWN", "FAILED"}


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

    # Phase 6 Enhanced World State Fields
    active_application: Optional[str] = None
    active_window: Optional[str] = None
    screen_dimensions: Dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})
    desktop_workspace: str = "1"
    brain_activity: str = "IDLE"          # IDLE, LISTENING, THINKING, WORKING, SEARCHING, SPEAKING
    companion_activity: str = "IDLE"      # IDLE, SPEAKING, ANIMATING, DESKTOP_PRESENCE
    current_goal: Optional[str] = None
    current_task: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None
    last_verification: str = "UNKNOWN"    # CONFIRMED, LIKELY, UNKNOWN, FAILED
    model_provider: str = "qwen2.5:3b"
    desktop_mate_status: str = "UNAVAILABLE" # AVAILABLE, UNAVAILABLE, DISCONNECTED
    voice_status: str = "UNAVAILABLE"        # AVAILABLE, UNAVAILABLE
    browser_status: str = "IDLE"             # IDLE, ACTIVE, CLOSED
    # Stage 8B Computer Context Model Fields
    window_class: Optional[str] = None
    window_geometry: Dict[str, int] = field(default_factory=dict)
    browser_url: Optional[str] = None
    browser_title: Optional[str] = None
    visible_ui_summary: Optional[str] = None
    focused_element: Optional[str] = None
    confidence: float = 1.0
    stale: bool = False
    timestamp: float = field(default_factory=time.time)

    def is_stale(self, max_age_seconds: float = 30.0) -> bool:
        return self.stale or (time.time() - self.timestamp) > max_age_seconds

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "os_name": self.os_name,
            "user_name": self.user_name,
            "running_apps": self.running_apps,
            "brain_owned_apps": self.brain_owned_apps,
            "focused_app": self.focused_app,
            "active_task": self.active_task,
            "last_action": self.last_action,
            "last_action_result": self.last_action_result,
            "observation_status": self.observation_status,
            "last_verified_time": self.last_verified_time,
            "active_application": self.active_application or self.focused_app,
            "active_window": self.active_window,
            "screen_dimensions": self.screen_dimensions,
            "desktop_workspace": self.desktop_workspace,
            "brain_activity": self.brain_activity,
            "companion_activity": self.companion_activity,
            "current_goal": self.current_goal,
            "current_task": self.current_task or self.active_task,
            "last_verification": self.last_verification,
            "model_provider": self.model_provider,
            "desktop_mate_status": self.desktop_mate_status,
            "voice_status": self.voice_status,
            "browser_status": self.browser_status,
            "window_class": self.window_class,
            "window_geometry": self.window_geometry,
            "browser_url": self.browser_url,
            "browser_title": self.browser_title,
            "visible_ui_summary": self.visible_ui_summary,
            "focused_element": self.focused_element,
            "confidence": self.confidence,
            "stale": self.is_stale(),
            "timestamp": self.timestamp,
        }
        if self.last_observation:
            d["last_observation"] = self.last_observation
        return d


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

    def get_focused_app(self) -> Optional[str]:
        """Returns the verified currently focused application name."""
        return self.current_state.focused_app or self.current_state.active_application

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
        self.current_state.active_application = focused
        self.current_state.last_verified_time = now
        self.current_state.timestamp = now
        self.current_state.observation_status = "KNOWN"

        return self.current_state

    def update_from_perception(self, perception_data: Dict[str, Any]) -> None:
        """Updates world state from fused perception result."""
        if not isinstance(perception_data, dict):
            return

        now = time.time()
        app = perception_data.get("application") or perception_data.get("focused_app")
        if app:
            self.current_state.active_application = app
            self.current_state.focused_app = app
        win = perception_data.get("window") or perception_data.get("active_window")
        if win:
            self.current_state.active_window = str(win)

        scr_meta = perception_data.get("screen_meta") or perception_data.get("screen")
        if isinstance(scr_meta, dict):
            w = scr_meta.get("width") or 1920
            h = scr_meta.get("height") or 1080
            self.current_state.screen_dimensions = {"width": int(w), "height": int(h)}
            if "workspace" in scr_meta:
                self.current_state.desktop_workspace = str(scr_meta["workspace"])

        conf = perception_data.get("confidence_state", "UNKNOWN")
        if conf in VERIFICATION_STATUSES:
            self.current_state.last_verification = conf

        # Bounded store of last observation summary
        obs_summary = {
            "screen_state": perception_data.get("screen_state", "UNKNOWN"),
            "elements_count": len(perception_data.get("detected_elements", [])),
            "timestamp": perception_data.get("timestamp", now)
        }
        self.current_state.last_observation = obs_summary
        self.current_state.last_verified_time = now
        self.current_state.timestamp = now
        self.current_state.observation_status = "KNOWN"

    def check_staleness(self) -> str:
        """Evaluates whether current state is fresh, stale, or unknown."""
        if self.current_state.last_verified_time == 0.0:
            self.current_state.observation_status = "UNKNOWN"
            return "UNKNOWN"

        age = time.time() - self.current_state.last_verified_time
        if age > self.staleness_threshold:
            self.current_state.observation_status = "STALE"
            return "STALE"

        return self.current_state.observation_status

    def mark_stale(self) -> None:
        """Explicitly marks state as stale (e.g. after system restart or unverified idle gap)."""
        self.current_state.observation_status = "STALE"

    def record_action_outcome(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        verified: bool = False,
        verification_status: Optional[str] = None
    ) -> None:
        """
        Records the outcome of an executed action into the current world state.
        Never marks state as verified unless execution confirmed it.
        """
        t_upper = str(tool_name).upper()
        self.current_state.last_action = t_upper

        if isinstance(result, dict):
            res_str = result.get("error") if not result.get("success") else str(result.get("data") or "Success")
            status_val = result.get("status", "executed_unverified")
        else:
            res_str = str(result)
            status_val = "executed_unverified"

        self.current_state.last_action_result = res_str[:120]

        if verification_status and verification_status in VERIFICATION_STATUSES:
            self.current_state.last_verification = verification_status
        elif verified or status_val == "verified":
            self.current_state.last_verification = "CONFIRMED"
        else:
            self.current_state.last_verification = "UNKNOWN"

        if verified:
            self.sync_from_system()
        else:
            self.current_state.observation_status = "STALE"

    def set_active_task(self, task_description: Optional[str]) -> None:
        self.current_state.active_task = task_description
        self.current_state.current_task = task_description

    def set_current_goal(self, goal_description: Optional[str]) -> None:
        self.current_state.current_goal = goal_description

    def set_brain_activity(self, activity: str) -> None:
        self.current_state.brain_activity = activity

    def set_companion_activity(self, activity: str) -> None:
        self.current_state.companion_activity = activity

    def set_desktop_mate_status(self, status: str) -> None:
        self.current_state.desktop_mate_status = status

    def set_voice_status(self, status: str) -> None:
        self.current_state.voice_status = status

    def set_browser_status(self, status: str) -> None:
        self.current_state.browser_status = status

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
        focused_str = st.focused_app or st.active_application or "none"

        status_flag = f"[{st.observation_status}]"
        lines = [
            f"WORLD STATE {status_flag}:",
            f"- Active Application: {focused_str}",
            f"- Active Window: {st.active_window or 'none'}",
            f"- Running Applications: {running_str}",
            f"- Brain Activity: {st.brain_activity}",
            f"- Verification Status: {st.last_verification}"
        ]
        if st.last_action:
            lines.append(f"- Last Action: {st.last_action} -> {st.last_action_result}")
        if st.active_task or st.current_task:
            lines.append(f"- Active Task: {st.active_task or st.current_task}")
        if st.current_goal:
            lines.append(f"- Current Goal: {st.current_goal}")

        return "\n".join(lines)


default_world_state = WorldStateManager()

