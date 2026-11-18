"""
Unit tests for Phase 1 Intelligence Upgrade: Cognitive Intent & Context Disambiguation.
Tests:
1. Grounded self-knowledge queries ('HOW TO START YOU(BRAIN) IN TERMINAL').
2. Terminal error log / bash failure transcript diagnosis ('command not found').
3. Disambiguation between how-to inquiries vs imperative OS tool actions.
"""

import unittest
from unittest.mock import MagicMock, patch

from core.app_backend import BrainAppCore
from core.cognition import default_cognition
from core.context import default_short_term_memory
from tools.router import default_router


class TestCognitiveIntentIntelligence(unittest.TestCase):

    def setUp(self):
        default_short_term_memory.clear()
        self.core = BrainAppCore(default_model="qwen3.5-brain:v2")

    def tearDown(self):
        default_short_term_memory.clear()

    def test_start_brain_in_terminal_self_knowledge(self):
        """User asking how to start Brain in terminal receives grounded operational knowledge, not tool execution."""
        queries = [
            "HOW TO START YOU(BRAIN) IN TERMINAL",
            "how to start you in terminal",
            "how do i run brain",
            "how to launch brain",
        ]
        for q in queries:
            res = self.core.execute_task(q)
            self.assertEqual(res["execution_path"], "GROUNDED_KNOWLEDGE", f"Failed for {q}")
            self.assertEqual(res["strategy"], "SYSTEM_SELF_KNOWLEDGE")
            self.assertIn("brain", res["text"].lower())
            self.assertIn("brain-app", res["text"].lower())

    def test_pasted_terminal_error_log_diagnosis(self):
        """Pasted shell errors are diagnosed rather than executed as random tools or hallucinated."""
        pasted_log = (
            "jai@JAI-s:~$ BRAIN\n"
            "BRAIN: command not found\n"
            "jai@JAI-s:~$  brain status\n"
            "Command 'brain' not found, did you mean:\n"
            "  command 'rain' from deb bsdgames (2.17-30)\n"
            "Try: sudo apt install <deb name>"
        )
        res = self.core.execute_task(pasted_log)
        self.assertEqual(res["execution_path"], "SYSTEM_DIAGNOSTIC")
        self.assertEqual(res["strategy"], "DIAGNOSTIC_ANALYSIS")
        self.assertIn("not found in your current shell's PATH", res["text"])
        self.assertIn("~/.local/bin", res["text"])

    def test_inquiry_vs_imperative_disambiguation(self):
        """Questions containing tool words ('terminal', 'open') do not blindly trigger tool execution."""
        inquiries = [
            "what is terminal",
            "how to open terminal",
            "can you explain what a browser is",
        ]
        for inq in inquiries:
            with patch.object(self.core.orchestrator, "solve") as mock_solve:
                mock_res = MagicMock()
                mock_res.text = f"Explanation of {inq}"
                mock_res.strategy = "DIRECT_RESPONSE"
                mock_res.mode = "DIRECT"
                mock_res.execution_path = "LLM_DIRECT"
                mock_res.model_id = "qwen3.5-brain:v2"
                mock_res.verified = True
                mock_res.confidence = 0.9
                mock_res.tokens_per_sec = 25.0
                mock_res.metadata = {}
                mock_solve.return_value = mock_res

                res = self.core.execute_task(inq)
                self.assertNotEqual(res["execution_path"], "AUTONOMOUS_TOOL_EXECUTION", f"Inquiry '{inq}' was wrongly executed as tool")

    @patch("core.app_backend.run_planner_task")
    def test_imperative_command_still_triggers_tools(self, mock_planner):
        """Imperative commands ('open brave', 'turn off bluetooth') properly trigger execution."""
        mock_planner.return_value = "Opened Brave successfully."
        res = self.core.execute_task("open brave")
        self.assertEqual(res["execution_path"], "AUTONOMOUS_TOOL_EXECUTION")
        self.assertEqual(res["strategy"], "TOOL_ASSISTED_EXECUTION")


if __name__ == "__main__":
    unittest.main()
