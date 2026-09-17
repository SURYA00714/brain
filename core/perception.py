import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

from tools.apps import default_app_tracker, get_active_window_app_name
from tools.vision import default_vision, ScreenElement
from core.window_state import default_window_provider
from tools.screen import get_screen_metadata, capture_screen, cleanup_screenshots
from core.world_state import default_world_state
from core.ui_element import UIElement


VALID_SCREEN_STATES = {
    "NORMAL", "LOADING", "ERROR", "LOGIN", "DIALOG",
    "CONFIRMATION", "SUCCESS", "EMPTY", "BLOCKED", "UNKNOWN"
}

PERCEPTION_SOURCES = {
    "APP_TRACKER", "BROWSER_DOM", "ACCESSIBILITY", "OCR", "VISION_MODEL", "WINDOW_METADATA"
}

CONFIDENCE_STATES = {"CONFIRMED", "LIKELY", "UNKNOWN", "FAILED"}


@dataclass
class ScreenObservation:
    """Structured representation of a complete desktop screen observation."""
    observation_id: str = field(default_factory=lambda: f"obs_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}")
    timestamp: float = field(default_factory=time.time)
    screen: Dict[str, Any] = field(default_factory=lambda: {"width": 1920, "height": 1080, "workspace": "1"})
    active_window: Dict[str, Any] = field(default_factory=dict)
    ocr: Dict[str, Any] = field(default_factory=lambda: {"text": [], "count": 0, "confidence": None})
    image_path: str = ""
    provider: str = "RapidOCR"
    confidence_state: str = "CONFIRMED"
    uncertainty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerceptionResult:
    """Standardized representation of screen and environmental perception with provenance."""
    source: str = "OCR"
    timestamp: float = field(default_factory=time.time)
    observation_id: str = field(default_factory=lambda: f"obs_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}")
    application: str = "unknown"
    window: Optional[str] = None
    active_window_meta: Dict[str, Any] = field(default_factory=dict)
    screen_meta: Dict[str, Any] = field(default_factory=dict)
    screen_state: str = "NORMAL"
    detected_text: List[str] = field(default_factory=list)
    detected_elements: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    confidence_state: str = "CONFIRMED"
    observations: List[str] = field(default_factory=list)
    uncertainty: float = 0.0
    stale_status: str = "FRESH"  # FRESH, STALE, INVALIDATED
    observation: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.observation:
            d["observation"] = self.observation
        return d

    def is_stale(self, max_age_seconds: float = 15.0) -> bool:
        if self.stale_status in ("STALE", "INVALIDATED"):
            return True
        return (time.time() - self.timestamp) > max_age_seconds

    def invalidate(self) -> None:
        self.stale_status = "INVALIDATED"


@dataclass
class FusedObservation:
    """Stage 8D — Fused perception result unifying window metadata, OCR, UI elements, and evidence."""
    observation_id: str
    timestamp: float
    application: str
    active_window: Dict[str, Any] = field(default_factory=dict)
    screen_meta: Dict[str, Any] = field(default_factory=dict)
    ocr_texts: List[str] = field(default_factory=list)
    detected_elements: List[Dict[str, Any]] = field(default_factory=list)
    ui_elements: List[UIElement] = field(default_factory=list)
    screen_state: str = "NORMAL"
    action_executed: bool = False
    desired_result_verified: bool = False
    verification_status: str = "UNKNOWN"
    evidence: List[str] = field(default_factory=list)
    window_title: str = ""
    window_class: str = ""
    browser_dom_summary: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    confidence_state: str = "CONFIRMED"
    sources_used: List[str] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ui_elements"] = [el.to_dict() if hasattr(el, "to_dict") else el for el in self.ui_elements]
        return d


class PerceptionClassifier:
    """
    Deterministic & heuristic classifier for UI screen states.
    Identifies common operational states (Error, Login, Confirmation, Loading, Success)
    from extracted text and elements without heavy model inference.
    """
    @classmethod
    def classify(cls, texts: List[str], elements: List[Dict[str, Any]]) -> Tuple[str, float]:
        combined = " ".join(texts).lower()

        # 1. Empty Screen
        if not texts and not elements:
            return "EMPTY", 0.1

        # 2. Blocked / Captcha / Access Denied
        blocked_keywords = ["access denied", "forbidden", "captcha", "security check", "please verify you are human"]
        if any(kw in combined for kw in blocked_keywords):
            return "BLOCKED", 0.1

        # 3. Error State
        error_keywords = [
            "error", "failed", "failure", "something went wrong",
            "crash", "traceback", "exception", "404 not found",
            "connection refused", "internal server error", "could not connect"
        ]
        if any(kw in combined for kw in error_keywords):
            return "ERROR", 0.15

        # 4. Confirmation / Alert Dialog
        confirm_keywords = [
            "are you sure", "confirm", "confirmation", "do you want to",
            "permanently delete", "cannot be undone", "discard changes"
        ]
        has_cancel = any(e.get("text", "").lower() in ["cancel", "no", "dismiss"] for e in elements)
        has_confirm = any(e.get("text", "").lower() in ["ok", "yes", "confirm", "delete", "proceed"] for e in elements)
        if any(kw in combined for kw in confirm_keywords) or (has_cancel and has_confirm):
            return "CONFIRMATION", 0.1

        # 5. Login / Authentication
        login_keywords = [
            "sign in", "log in", "login", "username", "password",
            "enter your password", "email address", "authenticator"
        ]
        has_login_fields = any(kw in combined for kw in login_keywords)
        has_password_field = any(e.get("is_sensitive", False) for e in elements)
        if has_login_fields or has_password_field:
            return "LOGIN", 0.1

        # 6. Loading / In-Progress State
        loading_keywords = ["loading", "please wait", "fetching", "buffering", "updating..."]
        if any(kw in combined for kw in loading_keywords):
            return "LOADING", 0.2

        # 7. Success State
        success_keywords = ["success", "saved successfully", "completed successfully", "changes saved"]
        if any(kw in combined for kw in success_keywords):
            return "SUCCESS", 0.15

        # 8. Normal / Default State
        if elements or texts:
            return "NORMAL", 0.05

        return "UNKNOWN", 0.8


class SmartObservationPolicy:
    """
    Stage 6D — Adaptive observation policy.
    Determines when to capture new screen state vs re-use fresh cached observation.
    Reduces unnecessary screenshots, CPU usage, and temporary storage footprint.
    """
    def __init__(self, max_freshness_seconds: float = 15.0):
        self.max_freshness_seconds = max_freshness_seconds
        self._last_observation_time: float = 0.0
        self._last_app: Optional[str] = None
        self._last_observation_id: Optional[str] = None

    def should_observe(
        self,
        last_action: Optional[str] = None,
        action_executed: bool = False,
        task_stage_changed: bool = False,
        recovery_active: bool = False,
        planner_requested: bool = False,
        force_refresh: bool = False
    ) -> bool:
        now = time.time()
        age = now - self._last_observation_time

        # Mandatory observation triggers
        if force_refresh or planner_requested or recovery_active:
            return True

        # Action verification trigger (if an action was executed)
        if action_executed and last_action:
            action_upper = last_action.upper()
            VERIFY_ACTIONS = {
                "OPEN_APP", "CLICK", "CLICK_TEXT", "CLICK_COORDINATES", "CLICK_ELEMENT",
                "DOUBLE_CLICK", "TYPE_TEXT", "TYPE_IN_ELEMENT", "NAVIGATE_URL", "SCROLL",
                "CLOSE_APP", "PRESS_KEY", "HOTKEY"
            }
            if action_upper in VERIFY_ACTIONS:
                return True


        # Active application switch trigger
        current_app = default_app_tracker.get_focused_app() or get_active_window_app_name()
        if self._last_app is not None and current_app and current_app != "unknown" and current_app != self._last_app:
            return True


        # Task stage transition trigger
        if task_stage_changed:
            return True

        # Staleness trigger
        if age > self.max_freshness_seconds:
            return True

        # Idle / unchanged state -> skip observation
        return False

    def record_observation(self, observation_id: str, app: Optional[str] = None) -> None:
        self._last_observation_time = time.time()
        self._last_observation_id = observation_id
        if app:
            self._last_app = app


class PerceptionRouter:
    """
    Perception Router for Brain.
    Orchestrates screen and application understanding following the priority hierarchy:
      1. Deterministic Application & OS state (AppTracker, active X11 window)
      2. Browser DOM / structured state (if browser is active)
      3. Desktop OCR perception (RapidOCR)
      4. Visual reasoning via ModelGateway (only when genuinely needed)
    """
    def __init__(self, vision_provider=None, app_tracker=None, window_provider=None):
        self.vision_provider = vision_provider or default_vision
        self.app_tracker = app_tracker or default_app_tracker
        self.window_provider = window_provider or default_window_provider
        self.policy = SmartObservationPolicy(max_freshness_seconds=15.0)
        self._last_result: Optional[PerceptionResult] = None
        self._last_fused: Optional[FusedObservation] = None

    def perceive(
        self,
        image_path: Optional[str] = None,
        force_refresh: bool = False,
        require_visual_reasoning: bool = False,
        target_evidence: Optional[str] = None,
        last_action_result: Optional[Dict[str, Any]] = None
    ) -> PerceptionResult:
        """
        Executes hierarchical perception across system, window metadata, OCR, and vision layers.
        Returns a rich PerceptionResult with provenance and confidence metrics.
        Updates Unified World State automatically.
        """
        now = time.time()
        obs_id = f"obs_{int(now*1000)}_{uuid.uuid4().hex[:6]}"

        # Step 1: Query active window and screen metadata
        win_meta = self.window_provider.get_active_window_metadata().get("window", {})
        scr_meta = get_screen_metadata().get("screen", {})

        focused_app = win_meta.get("class") or self.app_tracker.get_focused_app() or get_active_window_app_name() or "desktop"
        running_apps = [a for a in ["brave", "terminal", "file_manager", "text_editor"] if self.app_tracker.is_running(a)]

        # Step 2: Check cached observation freshness if no refresh forced
        if not force_refresh and self._last_result and not self._last_result.is_stale(max_age_seconds=15.0):
            return self._last_result

        # Step 3: Run desktop perception via vision_provider
        if not image_path:
            cap_res = capture_screen()
            if isinstance(cap_res, dict) and cap_res.get("success"):
                image_path = cap_res.get("image_path")

        if self.vision_provider.is_observation_fresh(max_age_seconds=15) and self.vision_provider.get_current_observation():
            ocr_obs = self.vision_provider.get_current_observation()
        else:
            ocr_obs = self.vision_provider.analyze_screen(image_path=image_path)

        elements = ocr_obs.get("elements", []) if isinstance(ocr_obs, dict) else []
        texts = [e.get("text", "") for e in elements if isinstance(e, dict) and e.get("text")]

        # Step 4: Classify Screen State & Confidence
        state_name, uncertainty = PerceptionClassifier.classify(texts, elements)

        # Distinguish ACTION SUCCEEDED from DESIRED RESULT VERIFIED (Stage 6C)
        evidence = []
        action_executed = bool(last_action_result and last_action_result.get("success"))
        desired_result_verified = False

        if focused_app:
            evidence.append(f"Window class: {focused_app}")
        if win_meta.get("title"):
            evidence.append(f"Window title: {win_meta.get('title')}")

        if target_evidence:
            target_lower = target_evidence.lower()
            combined_text = (" ".join(texts) + " " + str(win_meta.get("title", ""))).lower()
            if target_lower in combined_text:
                desired_result_verified = True
                evidence.append(f"Found target evidence matching: '{target_evidence}'")

        if desired_result_verified and uncertainty <= 0.2:
            conf_state = "CONFIRMED"
        elif action_executed and uncertainty <= 0.4:
            conf_state = "LIKELY"
        elif uncertainty < 0.8:
            conf_state = "UNKNOWN"
        else:
            conf_state = "FAILED"

        # Step 5: Construct observations list
        observations = []
        if focused_app:
            observations.append(f"Active window: {focused_app}")
        if win_meta.get("title"):
            observations.append(f"Window title: '{win_meta.get('title')}'")
        if running_apps:
            observations.append(f"Running applications: {', '.join(running_apps)}")
        observations.append(f"Screen state: {state_name} ({len(elements)} visible elements detected)")

        screen_obs = ScreenObservation(
            observation_id=obs_id,
            timestamp=ocr_obs.get("timestamp", now) if isinstance(ocr_obs, dict) else now,
            screen=scr_meta,
            active_window=win_meta,
            ocr={"text": texts[:15], "count": len(texts), "confidence": round(1.0 - uncertainty, 2)},
            image_path=image_path or "",
            provider=getattr(self.vision_provider.active_provider, "status_name", "RapidOCR"),
            confidence_state=conf_state,
            uncertainty=uncertainty
        )

        result = PerceptionResult(
            source="OCR",
            timestamp=screen_obs.timestamp,
            observation_id=obs_id,
            application=focused_app,
            window=win_meta.get("title") or focused_app,
            active_window_meta=win_meta,
            screen_meta=scr_meta,
            screen_state=state_name,
            detected_text=texts,
            detected_elements=elements,
            confidence=max(0.0, 1.0 - uncertainty),
            confidence_state=conf_state,
            observations=observations,
            uncertainty=uncertainty,
            stale_status="FRESH",
            observation=screen_obs.to_dict()
        )

        # Build Stage 6C Fused Observation
        fused = FusedObservation(
            observation_id=obs_id,
            timestamp=now,
            application=focused_app,
            active_window=win_meta,
            screen_meta=scr_meta,
            ocr_texts=texts,
            detected_elements=elements,
            screen_state=state_name,
            action_executed=action_executed,
            desired_result_verified=desired_result_verified,
            verification_status=conf_state,
            evidence=evidence
        )

        self._last_result = result
        self._last_fused = fused
        self.policy.record_observation(obs_id, focused_app)

        # Sync WorldState automatically with fused perception
        default_world_state.update_from_perception(result.to_dict())

        return result

    def get_last_result(self) -> Optional[PerceptionResult]:
        return self._last_result

    def get_last_fused(self) -> Optional[FusedObservation]:
        return self._last_fused

    def invalidate_cache(self) -> None:
        if self._last_result:
            self._last_result.invalidate()
        self.vision_provider.clear_observation()

    def detect_perception_change(self, old_res: Optional[PerceptionResult], new_res: PerceptionResult) -> Dict[str, Any]:
        """
        Stage 7O — Detects meaningful UI/screen perception changes using metadata diffs
        (active application, window title, screen state, element count) without full image pixel diff overhead.
        """
        if not old_res:
            return {
                "changed": True,
                "app_changed": True,
                "title_changed": True,
                "state_changed": True,
                "details": ["Initial perception observation established"]
            }

        app_changed = old_res.application != new_res.application
        title_changed = old_res.window != new_res.window
        state_changed = old_res.screen_state != new_res.screen_state
        element_count_diff = abs(len(old_res.detected_elements) - len(new_res.detected_elements)) > 3

        details = []
        if app_changed:
            details.append(f"Application switched: '{old_res.application}' -> '{new_res.application}'")
        if title_changed:
            details.append(f"Window title changed: '{old_res.window}' -> '{new_res.window}'")
        if state_changed:
            details.append(f"Screen state changed: {old_res.screen_state} -> {new_res.screen_state}")
        if element_count_diff:
            details.append(f"Element density changed: {len(old_res.detected_elements)} -> {len(new_res.detected_elements)} elements")

        changed = app_changed or title_changed or state_changed or element_count_diff
        return {
            "changed": changed,
            "app_changed": app_changed,
            "title_changed": title_changed,
            "state_changed": state_changed,
            "details": details
        }


default_perception_router = PerceptionRouter()




