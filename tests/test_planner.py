import unittest
from unittest.mock import patch, MagicMock
import json

from brain import parse_model_action, run_planner_task
from tools.registry import ToolRegistry, Tool, default_registry


def make_mock_response(text):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"response": text}
    return mock


class TestPlannerEngine(unittest.TestCase):

    def setUp(self):
        # Create an isolated test registry with mock execution functions
        self.test_registry = ToolRegistry()
        self.mock_web_search = MagicMock(return_value="Search results for Python")
        self.mock_list_files = MagicMock(return_value="Contents of Brain: [FILE] brain.py")
        self.mock_find_files = MagicMock(return_value="Found 1 matching item: brain.py")
        self.mock_read_file = MagicMock(return_value="--- Content of brain.py ---\nprint('hello')")

        self.test_registry.register(Tool("WEB_SEARCH", "Search web", {}, "LOW", self.mock_web_search))
        self.test_registry.register(Tool("LIST_FILES", "List files", {}, "LOW", self.mock_list_files))
        self.test_registry.register(Tool("FIND_FILES", "Find files", {}, "LOW", self.mock_find_files))
        self.test_registry.register(Tool("READ_TEXT_FILE", "Read text file", {}, "LOW", default_registry.get("READ_TEXT_FILE").func))

    # 1. Action Parser Tests
    def test_parse_model_action_valid_tool_json(self):
        json_str = '{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "Python 3.12"}}'
        action, err = parse_model_action(json_str)
        self.assertIsNone(err)
        self.assertEqual(action["type"], "tool")
        self.assertEqual(action["tool"], "WEB_SEARCH")
        self.assertEqual(action["arguments"], {"query": "Python 3.12"})

    def test_parse_model_action_valid_final_json(self):
        json_str = '{"type": "final", "answer": "The search is complete."}'
        action, err = parse_model_action(json_str)
        self.assertIsNone(err)
        self.assertEqual(action["type"], "final")
        self.assertEqual(action["answer"], "The search is complete.")

    def test_parse_model_action_embedded_json(self):
        text = 'Here is my action:\n```json\n{"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": "Brain"}}\n```'
        action, err = parse_model_action(text)
        self.assertIsNone(err)
        self.assertEqual(action["type"], "tool")
        self.assertEqual(action["tool"], "LIST_FILES")

    def test_parse_model_action_legacy_fallback(self):
        action, err = parse_model_action("OPEN_BRAVE")
        self.assertIsNone(err)
        self.assertEqual(action["type"], "tool")
        self.assertEqual(action["tool"], "OPEN_APP")
        self.assertEqual(action["arguments"], {"app_name": "brave"})

    # 2. Single-Step Task Test
    @patch("brain.requests.post")
    def test_planner_single_step_tool(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "Python"}}'),
            make_mock_response('{"type": "final", "answer": "Python is a programming language."}')
        ]

        final_ans = run_planner_task("What is Python?", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Python is a programming language.")
        self.mock_web_search.assert_called_once_with("Python")

    # 3. Two-Step Task Test
    @patch("brain.requests.post")
    def test_planner_two_step_task(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "FIND_FILES", "arguments": {"pattern": "*.py", "search_root": "Brain"}}'),
            make_mock_response('{"type": "tool", "tool": "READ_TEXT_FILE", "arguments": {"filepath": "brain.py"}}'),
            make_mock_response('{"type": "final", "answer": "I found brain.py and read its contents."}')
        ]

        final_ans = run_planner_task("Find brain.py and read it", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "I found brain.py and read its contents.")
        self.mock_find_files.assert_called_once_with("*.py", "Brain")

    # 4. Direct Final Answer Without Tool Test
    @patch("brain.requests.post")
    def test_planner_direct_final_answer(self, mock_brain_post):
        mock_brain_post.return_value = make_mock_response('{"type": "final", "answer": "Linux is an open-source OS kernel."}')

        final_ans = run_planner_task("What is Linux?", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Linux is an open-source OS kernel.")

    # 5. Unknown Tool Rejection Test
    @patch("brain.requests.post")
    def test_planner_unknown_tool_rejection(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "MALWARE_TOOL", "arguments": {}}'),
            make_mock_response('{"type": "final", "answer": "Handling unknown tool failure."}')
        ]

        final_ans = run_planner_task("Do unknown action", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Handling unknown tool failure.")

    # 6. Step Limit (MAX_STEPS = 10) Enforcement Test
    @patch("brain.requests.post")
    def test_planner_max_steps_enforced(self, mock_brain_post):
        responses = [
            make_mock_response(f'{{"type": "tool", "tool": "LIST_FILES", "arguments": {{"target_path": "Brain{i}"}}}}')
            for i in range(15)
        ]
        mock_brain_post.side_effect = responses

        final_ans = run_planner_task("Loop request", registry=self.test_registry, max_steps=5, quiet=True)
        self.assertIn("Maximum plan execution limit", final_ans)

    # 7. Infinite Loop Prevention on Identical Repeated Actions Test
    @patch("brain.requests.post")
    def test_planner_identical_repeated_action_blocked(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "repeat"}}'),
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "repeat"}}')
        ]

        final_ans = run_planner_task("Search repeat", registry=self.test_registry, quiet=True)
        self.assertIn("Repeated identical action", final_ans)

    # 8. Filesystem Safety Enforcement in Planner Loop Test
    @patch("brain.requests.post")
    def test_planner_unsafe_path_blocked(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "READ_TEXT_FILE", "arguments": {"filepath": "/etc/passwd"}}'),
            make_mock_response('{"type": "final", "answer": "I could not access that file due to safety controls."}')
        ]

        final_ans = run_planner_task("Read /etc/passwd", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "I could not access that file due to safety controls.")


if __name__ == "__main__":
    unittest.main()
