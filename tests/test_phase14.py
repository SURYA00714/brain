import os
import unittest
from unittest.mock import patch, MagicMock

os.environ["BRAIN_MOCK_GUI"] = "1"

from core.context import ShortTermMemory, default_short_term_memory
from core.cognition import CognitiveEngine, CognitiveLevel, EpistemicStatus, default_cognition
from brain import run_planner_task
from tools.router import default_router


class TestPhase14CognitiveArchitecture(unittest.TestCase):
    def setUp(self):
        default_short_term_memory.clear()

    def tearDown(self):
        default_short_term_memory.clear()

    # --------------------------------------------------------------------------
    # 1. SHORT-TERM CONTEXT & PRONOUN RESOLUTION
    # --------------------------------------------------------------------------
    def test_01_short_term_memory_pronoun_close_it(self):
        """'close it' resolves to the most recently active or referenced app."""
        mem = ShortTermMemory()
        mem.add_turn(
            user_text="open brave",
            agent_response="Brave is open.",
            referenced_app="brave"
        )
        resolved = mem.resolve_references("close it")
        self.assertEqual(resolved, "close brave")

        # Also test "quit it" and "please close it"
        self.assertEqual(mem.resolve_references("please close it"), "close brave")
        self.assertEqual(mem.resolve_references("quit it"), "close brave")

    def test_02_short_term_memory_pronoun_search_that(self):
        """'search that' resolves to the most recently discussed query or topic."""
        mem = ShortTermMemory()
        mem.add_turn(
            user_text="tell me about Marvel Comics",
            agent_response="Marvel is a comic publisher.",
            referenced_query="Marvel Comics"
        )
        resolved = mem.resolve_references("search that")
        self.assertEqual(resolved, "search the web for Marvel Comics")

    def test_03_short_term_memory_sliding_window(self):
        """Short-term memory respects bounded capacity (max_turns)."""
        mem = ShortTermMemory(max_turns=3)
        for i in range(5):
            mem.add_turn(f"user_{i}", f"agent_{i}")
        self.assertEqual(len(mem.turns), 3)
        self.assertEqual(mem.turns[0].user_text, "user_2")
        self.assertEqual(mem.turns[-1].user_text, "user_4")

    # --------------------------------------------------------------------------
    # 2. INTENT UNDERSTANDING & COGNITIVE LEVELS
    # --------------------------------------------------------------------------
    def test_04_intent_understanding_levels(self):
        """CognitiveEngine accurately classifies intent and assigns appropriate reasoning level."""
        engine = CognitiveEngine()

        # Conversation -> Level 0
        i_hello = engine.understand_intent("hello")
        self.assertEqual(i_hello["intent"], "CONVERSATION")
        self.assertEqual(i_hello["level"], CognitiveLevel.LEVEL_0_DETERMINISTIC)

        # Static concept -> Information, Level 1
        i_tcp = engine.understand_intent("what is TCP?")
        self.assertEqual(i_tcp["intent"], "INFORMATION")
        self.assertEqual(i_tcp["level"], CognitiveLevel.LEVEL_1_SIMPLE)

        # Freshness / research -> Research, Level 2
        i_py = engine.understand_intent("what is the latest Python release?")
        self.assertEqual(i_py["intent"], "RESEARCH")
        self.assertEqual(i_py["level"], CognitiveLevel.LEVEL_2_NORMAL)

        # Troubleshooting -> Level 2
        i_crash = engine.understand_intent("my browser is crashing when I open tabs")
        self.assertEqual(i_crash["intent"], "TROUBLESHOOTING")
        self.assertEqual(i_crash["level"], CognitiveLevel.LEVEL_2_NORMAL)

        # PC action -> Level 0
        i_act = engine.understand_intent("open calculator")
        self.assertEqual(i_act["intent"], "PC_ACTION")
        self.assertEqual(i_act["level"], CognitiveLevel.LEVEL_0_DETERMINISTIC)

    # --------------------------------------------------------------------------
    # 3. GROUNDED STATIC KNOWLEDGE VS WEB RESEARCH
    # --------------------------------------------------------------------------
    def test_05_static_knowledge_grounding_no_external_call(self):
        """Known fundamental concepts are answered immediately from grounded knowledge."""
        engine = CognitiveEngine()
        ans = engine.handle_static_information("what is python")
        self.assertIsNotNone(ans)
        self.assertIn("programming language", ans.lower())

        ans_tcp = engine.handle_static_information("what is TCP?")
        self.assertIsNotNone(ans_tcp)
        self.assertIn("transmission control protocol", ans_tcp.lower())

    def test_06_web_research_intelligence_grounding(self):
        """Research intent gathers fresh web data and produces structured, grounded findings."""
        engine = CognitiveEngine()
        mock_research_data = {
            "success": True,
            "query": "latest Python release",
            "findings": [
                "Python 3.12: The latest stable release of Python includes performance improvements.",
                "Python Release Schedule: Python 3.13 is in pre-release development."
            ],
            "sources": ["https://www.python.org/downloads/"]
        }
        with patch("core.cognition.research_topic", return_value=mock_research_data), \
             patch.object(engine.gateway.providers["groq"], "is_available", return_value=False), \
             patch.object(engine.gateway.providers["gemini"], "is_available", return_value=False):
            res = engine.execute_web_research("what is the latest Python release?")
            self.assertEqual(res["epistemic_status"], EpistemicStatus.RETRIEVED)
            self.assertIn("Python 3.12", res["text"])
            self.assertIn("https://www.python.org/downloads/", res["sources"])

    # --------------------------------------------------------------------------
    # 4. EPISTEMIC HONESTY & AMBIGUITY HANDLING
    # --------------------------------------------------------------------------
    def test_07_epistemic_honesty_unknown_topics(self):
        """Brain truthfully states lack of knowledge on unverified or impossible queries."""
        engine = CognitiveEngine()
        ans = engine.process_reasoning_query("What happened on Mars today?")
        self.assertIn("could not verify", ans.lower())

    def test_08_ambiguous_request_triggers_clarification(self):
        """Ambiguous request without prior conversational referent asks for clarification."""
        engine = CognitiveEngine()
        i = engine.understand_intent("fix this")
        self.assertEqual(i["intent"], "AMBIGUOUS")
        self.assertIn("clarification", i)
        self.assertIn("Could you clarify", i["clarification"])

    # --------------------------------------------------------------------------
    # 5. AUTONOMOUS GOAL PLANNING
    # --------------------------------------------------------------------------
    def test_09_autonomous_goal_decomposition(self):
        """High-level user goal compiles into a minimal, verifiable ExecutionPlan."""
        engine = CognitiveEngine()
        goal = "Open Brave and find the latest news about Python. Summarize the important changes."
        plan = engine.plan_autonomous_goal(goal)
        self.assertIsNotNone(plan)
        step_tools = [s.tool_name for s in plan.steps]
        self.assertEqual(step_tools, ["OPEN_APP", "FOCUS_APP", "BROWSER_SEARCH_FOREGROUND", "ANALYZE_SCREEN"])

    # --------------------------------------------------------------------------
    # 6. END-TO-END PIPELINE & CONTEXT CONTINUITY
    # --------------------------------------------------------------------------
    def test_10_end_to_end_contextual_pronoun_workflow(self):
        """End-to-end multi-turn interaction correctly carries context across commands."""
        # Turn 1: Open Brave
        ans1 = run_planner_task("can you open brave", quiet=True)
        self.assertIn("Brave is open", ans1)
        self.assertEqual(default_short_term_memory.get_last_app(), "brave")

        # Turn 2: Close it (resolves to close brave)
        ans2 = run_planner_task("close it", quiet=True)
        self.assertIn("closed", ans2.lower())

    def test_11_static_information_via_run_planner_task(self):
        """'What is Python?' is answered directly via CognitiveEngine static knowledge."""
        ans = run_planner_task("what is python", quiet=True)
        self.assertIn("programming language", ans.lower())

    def test_12_preference_recall_via_run_planner_task(self):
        """Stored user preferences can be recalled deterministically."""
        from core.memory import default_memory
        default_memory.add_memory(
            memory_type="PREFERENCE",
            subject="user",
            key="communication_style",
            value="concise answers"
        )
        ans = run_planner_task("what do you remember about my preference?", quiet=True)
        self.assertIn("concise answers", ans.lower())

    def test_13_safety_gate_blocks_dangerous_operations(self):
        """Dangerous system destruction requests are blocked unconditionally by SafetyGate."""
        from tools.input import validate_gui_action_safety
        is_safe, err = validate_gui_action_safety("TYPE_TEXT", {"text": "rm -rf /"})
        self.assertFalse(is_safe)
        self.assertIn("Safety Block:", err)


if __name__ == "__main__":
    unittest.main()
