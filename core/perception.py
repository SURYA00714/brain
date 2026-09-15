import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

from tools.apps import default_app_tracker, get_active_window_app_name
from tools.vision import default_vision, ScreenElement


VALID_SCREEN_STATES = {
    "NORMAL", "LOADING", "ERROR", "LOGIN", "DIALOG",
    "CONFIRMATION", "SUCCESS", "EMPTY", "BLOCKED", "UNKNOWN"
}

PERCEPTION_SOURCES = {
    "APP_TRACKER", "BROWSER_DOM", "ACCESSIBILITY", "OCR", "VISION_MODEL"
}


@dataclass
class PerceptionResult:
    """Standardized representation of screen and environmental perception with provenance."""
    source: str = "OCR"
    timestamp: float = field(default_factory=time.time)
    application: str = "unknown"
    window: Optional[str] = None
    screen_state: str = "NORMAL"
    detected_text: List[str] = field(default_factory=list)
    detected_elements: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    observations: List[str] = field(default_factory=list)
    uncertainty: float = 0.0
    stale_status: str = "FRESH"  # FRESH, STALE, INVALIDATED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_stale(self, max_age_seconds: float = 15.0) -> bool:
        if self.stale_status in ("STALE", "INVALIDATED"):
            return True
        return (time.time() - self.timestamp) > max_age_seconds

    def invalidate(self) -> None:
        self.stale_status = "INVALIDATED"


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


class PerceptionRouter:
    """
    Perception Router for Brain.
    Orchestrates screen and application understanding following the priority hierarchy:
      1. Deterministic Application & OS state (AppTracker, active X11 window)
      2. Browser DOM / structured state (if browser is active)
      3. Desktop OCR perception (RapidOCR)
      4. Visual reasoning via ModelGateway (only when genuinely needed)
    """
    def __init__(self, vision_provider=None, app_tracker=None):
        self.vision_provider = vision_provider or default_vision
        self.app_tracker = app_tracker or default_app_tracker
        self._last_result: Optional[PerceptionResult] = None

    def perceive(
        self,
        image_path: Optional[str] = None,
        force_refresh: bool = False,
        require_visual_reasoning: bool = False
    ) -> PerceptionResult:
        """
        Executes hierarchical perception across system, structured, OCR, and vision layers.
        Returns a rich PerceptionResult with provenance and confidence metrics.
        """
        # Step 1: Query deterministic application and focused window state
        focused_app = self.app_tracker.get_focused_app() or get_active_window_app_name() or "desktop"
        running_apps = [a for a in ["brave", "terminal", "file_manager", "text_editor"] if self.app_tracker.is_running(a)]

        # Step 2: Check cached observation freshness if no refresh forced
        if not force_refresh and self._last_result and not self._last_result.is_stale(max_age_seconds=15.0):
            return self._last_result

        # Step 3: Run desktop perception via vision_provider
        if not image_path:
            from tools.screen import capture_screen
            cap_res = capture_screen()
            if isinstance(cap_res, dict) and cap_res.get("success"):
                image_path = cap_res.get("image_path")

        if self.vision_provider.is_observation_fresh(max_age_seconds=15) and self.vision_provider.get_current_observation():
            ocr_obs = self.vision_provider.get_current_observation()
        else:
            ocr_obs = self.vision_provider.analyze_screen(image_path=image_path)

        elements = ocr_obs.get("elements", []) if isinstance(ocr_obs, dict) else []
        texts = [e.get("text", "") for e in elements if isinstance(e, dict) and e.get("text")]

        # Step 4: Classify Screen State
        state_name, uncertainty = PerceptionClassifier.classify(texts, elements)

        # Step 5: Construct observations list
        observations = []
        if focused_app:
            observations.append(f"Active window: {focused_app}")
        if running_apps:
            observations.append(f"Running applications: {', '.join(running_apps)}")
        observations.append(f"Screen state: {state_name} ({len(elements)} visible elements detected)")

        result = PerceptionResult(
            source="OCR",
            timestamp=ocr_obs.get("timestamp", time.time()) if isinstance(ocr_obs, dict) else time.time(),
            application=focused_app,
            window=focused_app,
            screen_state=state_name,
            detected_text=texts,
            detected_elements=elements,
            confidence=max(0.0, 1.0 - uncertainty),
            observations=observations,
            uncertainty=uncertainty,
            stale_status="FRESH"
        )

        self._last_result = result
        return result

    def get_last_result(self) -> Optional[PerceptionResult]:
        return self._last_result

    def invalidate_cache(self) -> None:
        if self._last_result:
            self._last_result.invalidate()
        self.vision_provider.clear_observation()


default_perception_router = PerceptionRouter()
