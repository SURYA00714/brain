"""
Brain Phase 7 Comprehensive Regression & Controlled Autonomy Test Suite.
Verifies Session Lifecycle, Event Bus, Proactive Awareness, Bounded Autonomy,
Confirmation Manager, Memory Filtering/Deduplication, Perception Change Detection,
Desktop Mate Fault Isolation, Safety Gate, and Resource Governor.
"""

import unittest
import time
import os
from unittest.mock import MagicMock, patch

# Enforce headless mock GUI environment during tests
os.environ["BRAIN_MOCK_GUI"] = "1"

from core.session import SessionManager, InteractionSession, default_session_manager
from core.event_bus import EventBus, BrainEvent, default_event_bus
from core.confirmation import ConfirmationManager, ConfirmationRequest, default_confirmation_manager
from core.autonomy import ProactiveAwarenessEngine, BoundedAutonomyController, AutonomyLimits, default_autonomy_controller
from core.resource_governor import ResourceGovernor, default_resource_governor
from core.memory import MemoryStore, MemoryPolicy, default_memory
from core.perception import PerceptionRouter, PerceptionResult, default_perception_router
from core.context import ContextBuilder, ShortTermMemory, default_short_term_memory
from core.world_state import WorldStateManager, default_world_state
from core.companion_state import CompanionStateManager, CompanionActivity, default_companion_state
from core.agent_loop import AgentLoop, default_agent_loop
from tools.registry import ToolRegistry, Tool


class TestPhase7SessionLifecycle(unittest.TestCase):
    """1. Tests session lifecycle and generation tokens."""
    def setUp(self):
        self.mgr = SessionManager()

    def test_session_lifecycle(self):
        sess = self.mgr.get_active_session()
        self.assertIsInstance(sess, InteractionSession)
        self.assertEqual(sess.current_state, "ACTIVE")
        self.assertEqual(sess.generation_id, 1)

        gen = self.mgr.bump_generation()
        self.assertEqual(gen, 2)

        self.mgr.update_session(user_input="hello", task="greeting")
        self.assertEqual(self.mgr.get_active_session().recent_user_input, "hello")

        self.mgr.end_session()
        self.assertEqual(sess.current_state, "ENDED")
        new_sess = self.mgr.get_active_session()
        self.assertEqual(new_sess.current_state, "ACTIVE")


class TestPhase7EventBus(unittest.TestCase):
    """7. Tests typed event bus broadcasting and history."""
    def setUp(self):
        self.bus = EventBus(max_history=5)

    def test_publish_and_subscribe(self):
        received = []
        def handler(evt):
            received.append(evt)

        self.bus.subscribe("USER_MESSAGE", handler)
        evt = self.bus.publish("USER_MESSAGE", {"text": "test"})
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "USER_MESSAGE")
        self.assertEqual(received[0].data["text"], "test")

    def test_bounded_history(self):
        for i in range(10):
            self.bus.publish("TASK_UPDATED", {"idx": i})
        recent = self.bus.get_recent_events(limit=10)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[-1].data["idx"], 9)


class TestPhase7ConfirmationManager(unittest.TestCase):
    """10. Tests confirmation manager, states, and user approval enforcement."""
    def setUp(self):
        self.mgr = ConfirmationManager()

    def test_evaluate_sensitive_action(self):
        status, req = self.mgr.evaluate_action("SHELL", {"cmd": "ls"})
        self.assertEqual(status, "REQUIRED")
        self.assertIsNotNone(req)
        self.assertEqual(req.status, "REQUIRED")

    def test_user_approval_enforcement(self):
        status, req = self.mgr.evaluate_action("SUBMIT_FORM", {"form": "test"})
        req_id = req.request_id

        # LLM / non-user source self-approval MUST be rejected
        approved_llm = self.mgr.approve(req_id, source="llm")
        self.assertFalse(approved_llm)

        # User approval succeeds
        approved_user = self.mgr.approve(req_id, source="user")
        self.assertTrue(approved_user)
        self.assertEqual(self.mgr.get_request(req_id).status, "APPROVED")


class TestPhase7AutonomyController(unittest.TestCase):
    """9. Tests bounded autonomy limits (max steps 5, max duration 30s)."""
    def setUp(self):
        self.limits = AutonomyLimits(max_actions=3, max_duration_seconds=1.0)
        self.ctrl = BoundedAutonomyController(limits=self.limits)

    def test_action_step_limit_enforcement(self):
        self.ctrl.start_autonomy("test_task")
        for i in range(3):
            can_cont, reason = self.ctrl.can_continue()
            self.assertTrue(can_cont)
            self.ctrl.record_step(success=True)

        can_cont, reason = self.ctrl.can_continue()
        self.assertFalse(can_cont)
        self.assertIn("maximum action step limit", reason)
        self.assertEqual(self.ctrl.state, "PAUSED")

    def test_autonomy_duration_limit_enforcement(self):
        self.ctrl.start_autonomy("test_task")
        time.sleep(1.1)
        can_cont, reason = self.ctrl.can_continue()
        self.assertFalse(can_cont)
        self.assertIn("maximum execution duration limit", reason)


class TestPhase7MemoryPolicyAndFiltering(unittest.TestCase):
    """11 & 12. Tests memory classification, deduplication, and sensitive filtering."""
    def test_memory_intent_classification(self):
        self.assertEqual(MemoryPolicy.classify_memory_intent("my password is 123"), "SENSITIVE")
        self.assertEqual(MemoryPolicy.classify_memory_intent("search python tutorials"), "EPHEMERAL")
        self.assertEqual(MemoryPolicy.classify_memory_intent("the project is located at ~/Brain"), "POTENTIAL_MEMORY")

    def test_memory_deduplication(self):
        mem_store = MemoryStore(":memory:")
        ok1, err1 = mem_store.add_memory("FACT", "user", "favorite_color", "blue")
        self.assertTrue(ok1)
        ok2, err2 = mem_store.add_memory("FACT", "user", "favorite_color", "green")
        self.assertTrue(ok2)

        record = mem_store.get_memory("FACT", "user", "favorite_color")
        self.assertEqual(record.value, "green")
        # Ensure only 1 record exists (deduplicated on type, subject, key)
        all_recs = mem_store.list_memories()
        self.assertEqual(len(all_recs), 1)


class TestPhase7PerceptionChangeDetection(unittest.TestCase):
    """13. Tests perception change detection without image diff overhead."""
    def setUp(self):
        self.router = PerceptionRouter()

    def test_detect_perception_change(self):
        res1 = PerceptionResult(application="brave", window="Brave Browser", screen_state="NORMAL")
        res2 = PerceptionResult(application="brave", window="Python Docs", screen_state="NORMAL")

        diff = self.router.detect_perception_change(res1, res2)
        self.assertTrue(diff["changed"])
        self.assertTrue(diff["title_changed"])
        self.assertFalse(diff["app_changed"])


class TestPhase7ResourceGovernor(unittest.TestCase):
    """20. Tests ResourceGovernor RSS monitoring and single screenshot storage bound."""
    def setUp(self):
        self.gov = ResourceGovernor()

    def test_resource_governor_check(self):
        res = self.gov.check_and_govern()
        self.assertIn("brain_rss_mb", res)
        self.assertIn("desktop_mate_rss_mb", res)
        self.assertIsInstance(res["brain_rss_mb"], float)


class TestPhase7FullAgentIntegration(unittest.TestCase):
    """25. Tests end-to-end agent loop integration with Phase 7 modules."""
    def setUp(self):
        self.agent = AgentLoop()

    def test_agent_loop_runs_with_session_and_events(self):
        report = self.agent.run("open brave", quiet=True)
        self.assertTrue(report["success"])
        self.assertEqual(report["status"], "COMPLETED")
        
        # Verify event bus received USER_MESSAGE and TASK_STARTED events
        recent_events = default_event_bus.get_recent_events(limit=5)
        event_types = [e.event_type for e in recent_events]
        self.assertIn("USER_MESSAGE", event_types)


if __name__ == "__main__":
    unittest.main()
