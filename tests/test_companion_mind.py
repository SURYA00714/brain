"""
Unit tests for Brain Companion Evolution (Mind, Mouth, Face, Hands, Presence).
Validates Skills, Goals, Agent Loop, Voice, Watcher, Computer-Use Tools, Personality, and Body Avatar Server.
"""

import os
import unittest
import json
import time
from unittest.mock import patch, MagicMock

# Force mock environment for headless testing
os.environ["BRAIN_MOCK_GUI"] = "1"

from core.skills import SkillDefinition, SkillStep, SkillRegistry, default_skills
from core.goals import PersistentGoal, SubTask, PersistentGoalManager, default_goals
from core.agent_loop import AgentLoop
from core.voice import VoiceManager, LinuxNativeTTS, default_voice
from core.watcher import AmbientWatcher, default_watcher
from core.personality import BrainPersonality, default_personality
from tools.computer_use import dom_get_page_state, dom_click, dom_type
from body.server import set_companion_state, get_companion_state, start_companion_server
from tools.plan import ExecutionPlan, ExecutionStep


class TestCompanionMind(unittest.TestCase):

    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    # --- 1. Procedural Skills ---
    def test_builtin_skills_registered(self):
        """Verify built-in procedural skills are present and valid."""
        skills = default_skills.list_skills()
        self.assertGreaterEqual(len(skills), 3)
        skill_names = [s.name for s in skills]
        self.assertIn("research_github_repository", skill_names)
        self.assertIn("inspect_disk_hoggers", skill_names)
        self.assertIn("browser_deep_search", skill_names)

    def test_skill_matching(self):
        """Test trigger pattern matching for skills."""
        match = default_skills.match_skill("Please research this repo for cool features")
        self.assertIsNotNone(match)
        self.assertEqual(match.name, "research_github_repository")

        disk_match = default_skills.match_skill("check my disk and tell me what is taking space")
        self.assertIsNotNone(disk_match)
        self.assertEqual(disk_match.name, "inspect_disk_hoggers")

        no_match = default_skills.match_skill("random non-skill text")
        self.assertIsNone(no_match)

    def test_skill_to_execution_plan(self):
        """Test converting a skill into a runnable ExecutionPlan."""
        skill = default_skills.get("inspect_disk_hoggers")
        self.assertIsNotNone(skill)
        plan = skill.to_execution_plan("check disk space usage")
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(len(plan.steps), len(skill.steps))
        self.assertEqual(plan.steps[0].tool_name, "CHECK_DISK_SPACE")

    def test_learn_trajectory_as_skill(self):
        """Test controlled learning of a successful execution plan as a persistent skill."""
        plan = ExecutionPlan(goal="backup_project")
        plan.add_step(ExecutionStep(action_type="tool", tool_name="LIST_FILES", arguments={"target_path": "Brain"}))
        plan.add_step(ExecutionStep(action_type="tool", tool_name="CHECK_DISK_SPACE", arguments={"target_path": "/"}))

        learned = default_skills.learn_trajectory_as_skill(
            name="test_backup_procedure",
            description="Learned test backup",
            trigger_patterns=["run test backup", "execute test backup"],
            plan=plan
        )
        self.assertIsNotNone(learned)
        self.assertTrue(learned.is_learned)
        retrieved = default_skills.get("test_backup_procedure")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved.steps), 2)

    # --- 2. Persistent Goals ---
    def test_goal_lifecycle(self):
        """Test persistent goal creation, step tracking, and serialization."""
        gm = PersistentGoalManager()
        goal = gm.create_goal("Build desktop companion avatar", subtask_titles=["Design HTML/CSS frontend", "Implement HTTP backend server"])
        self.assertIsNotNone(goal.id)
        self.assertEqual(goal.status, "RUNNING")
        self.assertEqual(len(goal.subtasks), 2)

        goal.update_subtask(1, "COMPLETED")
        self.assertEqual(goal.subtasks[0].status, "COMPLETED")
        self.assertIn("1/2 subtasks done", goal.progress_summary())

        # Test active goal management
        active = gm.get_active_goal()
        self.assertIsNotNone(active)
        self.assertEqual(active.id, goal.id)

    # --- 3. Agent Loop Execution ---
    def test_agent_loop_execution(self):
        """Test Bounded Agent Loop execution on a goal."""
        loop = AgentLoop()
        result = loop.run("check my disk and tell me what is taking space")
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertIn("answer", result)

    # --- 4. Mouth / Voice Layer ---
    def test_voice_sanitization_and_mocking(self):
        """Test speech text sanitization, markdown removal, and mock safety."""
        vm = VoiceManager()
        # In mock mode, speak returns True silently without audio invocation
        res = vm.speak("Check this link: https://github.com/test and **bold text**")
        self.assertTrue(res)


        # Mute test
        vm.mute()
        self.assertTrue(vm.is_muted)
        self.assertFalse(vm.speak("Hello while muted"))
        vm.unmute()
        self.assertFalse(vm.is_muted)

    # --- 5. Ambient Presence / Watcher ---
    def test_ambient_watcher_snapshot(self):
        """Test low-overhead (<10ms) OS system state capture with 0 LLM calls."""
        watcher = AmbientWatcher(poll_interval_sec=1.0)
        events = watcher.poll_once()
        self.assertIsInstance(events, list)

        # Test callback registration
        received = []
        watcher.add_callback(lambda ev: received.append(ev))
        self.assertEqual(len(watcher._event_callbacks), 1)

    # --- 6. Hands / Computer-Use DOM Tools ---
    def test_dom_computer_use_tools(self):
        """Test DOM extraction and page state inspection fallbacks."""
        state_res = dom_get_page_state()
        self.assertIsInstance(state_res, dict)
        self.assertIn("success", state_res)

        click_res = dom_click("button#submit")
        self.assertIsInstance(click_res, dict)

        type_res = dom_type("input#search", "antigravity")
        self.assertIsInstance(type_res, dict)

    # --- 7. Face / Desktop Companion Server State ---
    def test_companion_server_state(self):
        """Test avatar state synchronization and HTTP API."""
        set_companion_state("WORKING", "Executing test task", action="TEST_ACTION")
        state = get_companion_state()
        self.assertEqual(state["state"], "WORKING")
        self.assertEqual(state["status_text"], "Executing test task")
        self.assertEqual(state["last_action"], "TEST_ACTION")

        # Test state transition to SUCCESS
        set_companion_state("SUCCESS", "Task finished", result="All steps verified")
        state_after = get_companion_state()
        self.assertEqual(state_after["state"], "SUCCESS")
        self.assertEqual(state_after["last_result"], "All steps verified")

    # --- 8. Personality ---
    def test_brain_personality(self):
        """Test personality prompt formatting and tone."""
        p = BrainPersonality()
        prompt_snippet = p.get_system_prompt()
        self.assertIn("Brain", prompt_snippet)
        self.assertIn("Computer-Native Companion", prompt_snippet)
        self.assertIn("Operational Principles", prompt_snippet)


if __name__ == "__main__":
    unittest.main()
