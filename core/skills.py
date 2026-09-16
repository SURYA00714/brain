"""
Brain Procedural Skill System (Phase 19 Companion Evolution).
Implements procedural memory allowing Brain to store, match, execute, and learn
reusable multi-step operational procedures with verification rules and recovery recipes.
"""

import os
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from tools.plan import ExecutionPlan, ExecutionStep


@dataclass
class SkillStep:
    """A single declarative step within a procedural skill."""
    action: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    expected_observation: Optional[str] = None
    verification_method: str = "none"
    allow_failure: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillStep":
        return cls(
            action=data.get("action", ""),
            arguments=data.get("arguments", {}),
            expected_observation=data.get("expected_observation"),
            verification_method=data.get("verification_method", "none"),
            allow_failure=data.get("allow_failure", False),
            description=data.get("description", "")
        )


@dataclass
class SkillDefinition:
    """Full procedural specification for a reusable Brain skill."""
    name: str
    description: str
    trigger_patterns: List[str]
    required_capabilities: List[str] = field(default_factory=list)
    steps: List[SkillStep] = field(default_factory=list)
    verification_rules: List[str] = field(default_factory=list)
    failure_recovery: Dict[str, str] = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    is_learned: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() if isinstance(s, SkillStep) else s for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillDefinition":
        raw_steps = data.get("steps", [])
        steps = [SkillStep.from_dict(s) if isinstance(s, dict) else s for s in raw_steps]
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            trigger_patterns=data.get("trigger_patterns", []),
            required_capabilities=data.get("required_capabilities", []),
            steps=steps,
            verification_rules=data.get("verification_rules", []),
            failure_recovery=data.get("failure_recovery", {}),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            is_learned=data.get("is_learned", False),
            created_at=data.get("created_at", time.time())
        )

    def to_execution_plan(self, user_request: str, params: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """Instantiates this procedural skill into an executable ExecutionPlan."""
        plan = ExecutionPlan(goal=user_request)
        params = params or {}

        for idx, s in enumerate(self.steps, start=1):
            # Parameter substitution in arguments
            resolved_args = {}
            for k, v in s.arguments.items():
                if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                    var_name = v.strip("{}")
                    resolved_args[k] = params.get(var_name, v)
                else:
                    resolved_args[k] = v

            plan.add_step(ExecutionStep(
                step_id=idx,
                action_type="tool",
                tool_name=s.action,
                arguments=resolved_args,
                expected_outcome=s.expected_observation,
                verification_method=s.verification_method,
                allow_failure=s.allow_failure,
                depends_on=[idx - 1] if idx > 1 else [],
                description=s.description or f"Skill step {idx} ({s.action})"
            ))
        return plan


class SkillRegistry:
    """Central repository of procedural skills (built-in and learned)."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "skills")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._skills: Dict[str, SkillDefinition] = {}
        self._register_builtin_skills()
        self._load_learned_skills()

    def register(self, skill: SkillDefinition):
        self._skills[skill.name.lower()] = skill

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name.lower())

    def list_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def match_skill(self, text: str) -> Optional[SkillDefinition]:
        """Matches user request against registered skill trigger patterns."""
        if not text:
            return None
        norm = re.sub(r"[^\w\s]", "", text.lower()).strip()
        for skill in self._skills.values():
            for pat in skill.trigger_patterns:
                pat_norm = re.sub(r"[^\w\s]", "", pat.lower()).strip()
                if pat_norm and pat_norm in norm:
                    return skill
        return None

    def save_learned_skill(self, skill: SkillDefinition) -> bool:
        """Persists a new learned skill to data/skills/."""
        skill.is_learned = True
        self.register(skill)
        try:
            filename = f"{re.sub(r'[^a-z0-9_]', '_', skill.name.lower())}.json"
            filepath = os.path.join(self.data_dir, filename)
            with open(filepath, "w") as f:
                json.dump(skill.to_dict(), f, indent=2)
            return True
        except Exception:
            return False

    def learn_trajectory_as_skill(self, name: str, description: str, trigger_patterns: List[str], plan: ExecutionPlan) -> Optional[SkillDefinition]:
        """
        Controlled learning: extracts a successful multi-step ExecutionPlan into a reusable procedural skill.
        Enforces that only safe, registered tools are retained.
        """
        if not plan or not plan.steps:
            return None

        skill_steps = []
        for s in plan.steps:
            if s.action_type == "tool" and s.tool_name:
                skill_steps.append(SkillStep(
                    action=s.tool_name,
                    arguments=dict(s.arguments),
                    expected_observation=s.expected_outcome,
                    verification_method=s.verification_method,
                    allow_failure=s.allow_failure,
                    description=s.description
                ))

        if not skill_steps:
            return None

        skill = SkillDefinition(
            name=name,
            description=description,
            trigger_patterns=trigger_patterns,
            steps=skill_steps,
            is_learned=True
        )
        self.save_learned_skill(skill)
        return skill

    def _load_learned_skills(self):
        """Loads persistent learned skills from disk."""
        if not os.path.exists(self.data_dir):
            return
        for fname in os.listdir(self.data_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self.data_dir, fname), "r") as f:
                        data = json.load(f)
                        skill = SkillDefinition.from_dict(data)
                        self.register(skill)
                except Exception:
                    pass

    def _register_builtin_skills(self):
        """Initializes high-value built-in procedural skills."""
        # 1. Research GitHub Repository
        self.register(SkillDefinition(
            name="research_github_repository",
            description="Inspects a GitHub repository structure, README, and architecture.",
            trigger_patterns=["analyze this github repo", "research this repo", "research this github", "inspect this repository"],
            required_capabilities=["brave", "browser_search"],
            steps=[
                SkillStep(action="OPEN_APP", arguments={"app_name": "brave"}, expected_observation="Brave open", verification_method="app_running", description="Open Brave browser"),
                SkillStep(action="FOCUS_APP", arguments={"app_name": "brave"}, expected_observation="Brave focused", verification_method="focus", description="Focus Brave"),
                SkillStep(action="BROWSER_SEARCH_FOREGROUND", arguments={"query": "{repo_query}"}, expected_observation="Search results", verification_method="text_on_screen", description="Search repository"),
                SkillStep(action="CLICK_FIRST_RESULT", arguments={"query": "{repo_query}"}, expected_observation="Repository page loaded", verification_method="url_or_page", description="Navigate to repo"),
                SkillStep(action="ANALYZE_SCREEN", arguments={}, expected_observation="Landing observation", verification_method="observation", description="Inspect README and files")
            ],
            verification_rules=["Repository page must be active on screen"]
        ))

        # 2. Inspect Disk Hoggers
        self.register(SkillDefinition(
            name="inspect_disk_hoggers",
            description="Inspects filesystem usage and identifies large directory consumers.",
            trigger_patterns=["check my disk and tell me what is taking space", "what is taking up space", "find disk hoggers", "check disk space hogs"],
            required_capabilities=["disk"],
            steps=[
                SkillStep(action="CHECK_DISK_SPACE", arguments={"target_path": "/"}, expected_observation="Root disk usage", verification_method="none", description="Check root disk space"),
                SkillStep(action="LIST_FILES", arguments={"target_path": "Downloads"}, expected_observation="Downloads directory listed", verification_method="none", description="Inspect Downloads directory")
            ],
            verification_rules=["Disk usage reported accurately"]
        ))

        # 3. Browser Deep Search
        self.register(SkillDefinition(
            name="browser_deep_search",
            description="Searches topic in foreground browser, clicks top result, and verifies content.",
            trigger_patterns=["search and open the first useful result", "open first useful result", "deep search and open"],
            required_capabilities=["brave", "browser_search"],
            steps=[
                SkillStep(action="OPEN_APP", arguments={"app_name": "brave"}, expected_observation="Brave open", verification_method="app_running", description="Open Brave"),
                SkillStep(action="FOCUS_APP", arguments={"app_name": "brave"}, expected_observation="Brave focused", verification_method="focus", description="Focus Brave"),
                SkillStep(action="BROWSER_SEARCH_FOREGROUND", arguments={"query": "{query}"}, expected_observation="Search performed", verification_method="text_on_screen", description="Search in Brave"),
                SkillStep(action="CLICK_FIRST_RESULT", arguments={"query": "{query}"}, expected_observation="Result loaded", verification_method="url_or_page", description="Open first result"),
                SkillStep(action="ANALYZE_SCREEN", arguments={}, expected_observation="Content observation", verification_method="observation", description="Analyze landing page")
            ],
            verification_rules=["First result opened and verified"]
        ))


default_skills = SkillRegistry()
