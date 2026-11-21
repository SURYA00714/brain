import os
import unittest
from tools.router import FastRouter
from core.context import default_context_builder
from core.memory import default_memory


class TestNaturalIntelligenceAndMemory(unittest.TestCase):
    """Tests for conversational naturalness, entity memory extraction, and compound execution."""

    def setUp(self):
        self.router = FastRouter()

    def test_remember_entity_extraction(self):
        """Verifies entity extraction from 'remember the number 1, i will ask later'."""
        route = self.router.route("remember the number 1, i will ask later")
        self.assertEqual(route.get("type"), "tool")
        self.assertEqual(route.get("tool"), "REMEMBER")
        args = route.get("arguments", {})
        self.assertEqual(args.get("key"), "number")
        self.assertEqual(args.get("value"), "1")

    def test_recall_queries(self):
        """Verifies deterministic recall for remembered facts."""
        default_memory.add_memory(memory_type="FACT", subject="user", key="number", value="1")

        # Test case 1: whats the number i told you
        r1 = self.router.route("whats the number i told you")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.get("type"), "final")
        self.assertIn("1", r1.get("answer", ""))

        # Test case 2: i told you to remember a number whats it?
        r2 = self.router.route("i told you to remember a number whats it?")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.get("type"), "final")
        self.assertIn("1", r2.get("answer", ""))

        # Test case 3: what i told you to remember
        r3 = self.router.route("what i told you to remember")
        self.assertIsNotNone(r3)
        self.assertEqual(r3.get("type"), "final")
        self.assertIn("1", r3.get("answer", ""))

        # Test case 4: what did i tell you to remember
        r4 = self.router.route("what did i tell you to remember")
        self.assertIsNotNone(r4)
        self.assertEqual(r4.get("type"), "final")
        self.assertIn("1", r4.get("answer", ""))

    def test_compound_open_and_write(self):
        """Verifies compound workflow for 'open text editor and write about yourself'."""
        route = self.router.route("open text editor and write about yourself")
        self.assertIsNotNone(route)
        self.assertEqual(route.get("type"), "plan")
        plan = route.get("plan")
        self.assertEqual(len(plan.steps), 4)
        self.assertEqual(plan.steps[0].tool_name, "OPEN_APP")
        self.assertEqual(plan.steps[0].arguments.get("app_name"), "text_editor")
        self.assertEqual(plan.steps[1].tool_name, "FOCUS_APP")
        self.assertEqual(plan.steps[2].tool_name, "TYPE_TEXT")

    def test_multitask_capability(self):
        """Verifies that asking about multi-task capabilities produces an affirmative, helpful answer."""
        route = self.router.route("can you do multiple tasks in one input?")
        self.assertIsNotNone(route)
        self.assertEqual(route.get("type"), "final")
        self.assertIn("Yes", route.get("answer", ""))

    def test_conversational_context_sanitization(self):
        """Ensures conversational queries do not inject noisy UNKNOWN world state blocks."""
        ctx = default_context_builder.build_system_context("tell me a joke")
        self.assertNotIn("WORLD STATE [UNKNOWN]", ctx)
        self.assertIn("Brain", ctx)

    def test_verify_step_open_app_does_not_choke(self):
        """Ensures verify_step_execution for OPEN_APP returns verified True when launch was dispatched."""
        from core.cognition import verify_step_execution
        ok, status, msg = verify_step_execution("OPEN_APP", {"app_name": "text_editor"}, {"success": True, "data": "launched"})
        self.assertTrue(ok)
        self.assertEqual(status, "VERIFIED")

    def test_headless_rag_search_routing(self):
        """Ensures search queries use headless DEEP_RESEARCH without hijacking active windows or media."""
        # Query 1: search for python 3.13
        r1 = self.router.route("search for python 3.13")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.get("type"), "tool")
        self.assertEqual(r1.get("tool"), "DEEP_RESEARCH")
        self.assertEqual(r1.get("arguments", {}).get("query"), "python 3.13")

        # Query 2: search like a rag model inquiry
        r2 = self.router.route("does it has internet access, can i search like a rag model with internet as database")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.get("type"), "final")
        self.assertIn("headless internet access", r2.get("answer", ""))

        # Query 3: search gta 6 and tell its bugs news
        r3 = self.router.route("search gta 6 and tell its bugs news")
        self.assertIsNotNone(r3)
        self.assertEqual(r3.get("type"), "tool")
        self.assertEqual(r3.get("tool"), "DEEP_RESEARCH")
        self.assertEqual(r3.get("arguments", {}).get("query"), "gta 6")

        # Query 4: brain search gta 6
        r4 = self.router.route("brain search gta 6")
        self.assertIsNotNone(r4)
        self.assertEqual(r4.get("type"), "tool")
        self.assertEqual(r4.get("tool"), "DEEP_RESEARCH")
        self.assertEqual(r4.get("arguments", {}).get("query"), "gta 6")


if __name__ == "__main__":
    unittest.main()
