"""
Brain Interaction Session Manager (Phase 7).
Tracks session lifecycle, generation tokens, and turn activity across conversational turns
without requiring process restarts.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List


@dataclass
class InteractionSession:
    """Bounded, persistent interaction session snapshot."""
    session_id: str = field(default_factory=lambda: f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}")
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    current_task: Optional[str] = None
    current_goal: Optional[str] = None
    current_state: str = "ACTIVE"  # ACTIVE, PAUSED, IDLE, ENDED
    recent_user_input: Optional[str] = None
    recent_brain_response: Optional[str] = None
    interruption_status: str = "NONE"  # NONE, INTERRUPTED, CANCELLED
    generation_id: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SessionManager:
    """Thread-safe interaction session controller."""
    def __init__(self):
        self._current_session: Optional[InteractionSession] = None
        self.start_session()

    def start_session(self, session_id: Optional[str] = None) -> InteractionSession:
        now = time.time()
        sid = session_id or f"session_{int(now)}_{uuid.uuid4().hex[:6]}"
        self._current_session = InteractionSession(
            session_id=sid,
            started_at=now,
            last_activity=now,
            current_state="ACTIVE",
            generation_id=1
        )
        return self._current_session

    def get_active_session(self) -> InteractionSession:
        if not self._current_session or self._current_session.current_state == "ENDED":
            return self.start_session()
        return self._current_session

    def update_session(
        self,
        user_input: Optional[str] = None,
        brain_response: Optional[str] = None,
        task: Optional[str] = None,
        goal: Optional[str] = None,
        state: Optional[str] = None,
        interruption_status: Optional[str] = None
    ) -> InteractionSession:
        sess = self.get_active_session()
        now = time.time()
        sess.last_activity = now

        if user_input is not None:
            sess.recent_user_input = user_input
        if brain_response is not None:
            sess.recent_brain_response = brain_response
        if task is not None:
            sess.current_task = task
        if goal is not None:
            sess.current_goal = goal
        if state is not None:
            sess.current_state = state
        if interruption_status is not None:
            sess.interruption_status = interruption_status

        return sess

    def bump_generation(self) -> int:
        """Increments generation token when new user requests or interruptions arrive."""
        sess = self.get_active_session()
        sess.generation_id += 1
        sess.last_activity = time.time()
        return sess.generation_id

    def interrupt_session(self, reason: str = "user_request") -> InteractionSession:
        """Interrupts current session, updates interruption status, and bumps generation token."""
        sess = self.get_active_session()
        sess.interruption_status = "INTERRUPTED"
        sess.last_activity = time.time()
        self.bump_generation()
        return sess

    def reset_session(self) -> InteractionSession:
        return self.start_session()


    def end_session(self) -> None:
        if self._current_session:
            self._current_session.current_state = "ENDED"
            self._current_session.last_activity = time.time()


@dataclass
class UserProfile:
    """Individual personal environment profile for multi-user adaptation."""
    name: str = "default"
    working_style: str = "concise"  # concise, thorough, beginner, technical
    preferred_model: str = "qwen3.5:2b-q4_K_M"
    custom_instructions: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            name=data.get("name", "default"),
            working_style=data.get("working_style", "concise"),
            preferred_model=data.get("preferred_model", "qwen3.5:2b-q4_K_M"),
            custom_instructions=data.get("custom_instructions", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )


class UserProfileManager:
    """Manages isolated personal environments, preferences, and workflows per user."""
    def __init__(self, profiles_dir: Optional[Any] = None):
        import os
        from pathlib import Path
        self.profiles_dir = Path(profiles_dir) if profiles_dir else Path("data/profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.active_profile_file = self.profiles_dir / "active.txt"
        self._ensure_default_profile()

    def _ensure_default_profile(self) -> None:
        default_file = self.profiles_dir / "default.json"
        if not default_file.exists():
            prof = UserProfile(name="default")
            self._save_profile_file(prof)
        if not self.active_profile_file.exists():
            self.active_profile_file.write_text("default", encoding="utf-8")

    def _save_profile_file(self, profile: UserProfile) -> None:
        import json
        prof_file = self.profiles_dir / f"{profile.name}.json"
        prof_file.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    def get_active_profile(self) -> UserProfile:
        import json
        name = "default"
        if self.active_profile_file.exists():
            name = self.active_profile_file.read_text(encoding="utf-8").strip() or "default"
        prof_file = self.profiles_dir / f"{name}.json"
        if prof_file.exists():
            try:
                data = json.loads(prof_file.read_text(encoding="utf-8"))
                return UserProfile.from_dict(data)
            except Exception:
                pass
        return UserProfile(name=name)

    def switch_profile(self, name: str) -> UserProfile:
        self.active_profile_file.write_text(name, encoding="utf-8")
        return self.get_active_profile()

    def create_profile(
        self,
        name: str,
        working_style: str = "concise",
        preferred_model: str = "qwen3.5:2b-q4_K_M",
        custom_instructions: str = ""
    ) -> UserProfile:
        prof = UserProfile(
            name=name,
            working_style=working_style,
            preferred_model=preferred_model,
            custom_instructions=custom_instructions
        )
        self._save_profile_file(prof)
        return prof

    def list_profiles(self) -> List[str]:
        profiles = []
        for f in self.profiles_dir.glob("*.json"):
            profiles.append(f.stem)
        return sorted(profiles)


default_user_profile_manager = UserProfileManager()
default_session_manager = SessionManager()
