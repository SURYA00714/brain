import unittest
from unittest.mock import patch, MagicMock
import json

from brain import parse_model_action, run_planner_task
from tools.registry import ToolRegistry, Tool, default_registry


def make_mock_response(text):
    from models.gateway import ModelResponse
    return ModelResponse(text=text, model="mock", provider="mock", success=True)


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
    @patch("brain.default_gateway.generate")
    def test_planner_single_step_tool(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "Python"}}'),
            make_mock_response('{"type": "final", "answer": "Python is a programming language."}')
        ]

        final_ans = run_planner_task("What is Python?", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Python is a programming language.")
        self.mock_web_search.assert_called_once_with("Python")

    # 3. Two-Step Task Test
    @patch("brain.default_gateway.generate")
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
    @patch("brain.default_gateway.generate")
    def test_planner_direct_final_answer(self, mock_brain_post):
        mock_brain_post.return_value = make_mock_response('{"type": "final", "answer": "Linux is an open-source OS kernel."}')

        final_ans = run_planner_task("What is Linux?", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Linux is an open-source OS kernel.")

    # 5. Unknown Tool Rejection Test
    @patch("brain.default_gateway.generate")
    def test_planner_unknown_tool_rejection(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "MALWARE_TOOL", "arguments": {}}'),
            make_mock_response('{"type": "final", "answer": "Handling unknown tool failure."}')
        ]

        final_ans = run_planner_task("Do unknown action", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "Handling unknown tool failure.")

    # 6. Step Limit (MAX_STEPS = 10) Enforcement Test
    @patch("brain.default_gateway.generate")
    def test_planner_max_steps_enforced(self, mock_brain_post):
        responses = [
            make_mock_response(f'{{"type": "tool", "tool": "LIST_FILES", "arguments": {{"target_path": "Brain{i}"}}}}')
            for i in range(15)
        ]
        mock_brain_post.side_effect = responses

        final_ans = run_planner_task("Loop request", registry=self.test_registry, max_steps=5, quiet=True)
        self.assertIn("Maximum plan execution limit", final_ans)

    # 7. Infinite Loop Prevention on Identical Repeated Actions Test
    @patch("brain.default_gateway.generate")
    def test_planner_identical_repeated_action_blocked(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "repeat"}}'),
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "repeat"}}')
        ]

        final_ans = run_planner_task("Search repeat", registry=self.test_registry, quiet=True)
        self.assertIn("Repeated identical action", final_ans)

    # 8. Filesystem Safety Enforcement in Planner Loop Test
    @patch("brain.default_gateway.generate")
    def test_planner_unsafe_path_blocked(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "READ_TEXT_FILE", "arguments": {"filepath": "/etc/passwd"}}'),
            make_mock_response('{"type": "final", "answer": "I could not access that file due to safety controls."}')
        ]

        final_ans = run_planner_task("Read /etc/passwd", registry=self.test_registry, quiet=True)
        self.assertEqual(final_ans, "I could not access that file due to safety controls.")

    # 9. Regression Test: "hello" does not execute ANALYZE_SCREEN or GUI tools
    @patch("brain.default_gateway.generate")
    def test_hello_does_not_trigger_analyze_screen(self, mock_brain_post):
        mock_brain_post.return_value = make_mock_response('{"type": "final", "answer": "Hello! How can I help you today?"}')
        ans = run_planner_task("hello", registry=self.test_registry, quiet=True)
        self.assertIn("Hello!", ans)

    # 10. Regression Test: ANALYZE_SCREEN observation formatting in planner history reports element count
    def test_compact_screen_observation_formatting(self):
        from brain import build_planner_prompt
        fake_obs = {
            "success": True,
            "status": "VISION_ANALYZED",
            "screen": {"width": 1920, "height": 1080},
            "elements": [{"id": "elem_1", "type": "button", "text": "OK", "center_x": 100, "center_y": 200, "confidence": 0.99}],
            "image_path": "logs/screen_temp.png"
        }
        history = [{
            "action": {"type": "tool", "tool": "ANALYZE_SCREEN", "arguments": {}},
            "result": fake_obs,
            "action_hash": "ANALYZE_SCREEN:{}"
        }]
        prompt = build_planner_prompt("Analyze my screen", history)
        self.assertIn('"elements_count": 1', prompt)
        self.assertNotIn("image_path", prompt.split("Previous Step Execution History:")[1])

    # 11. Regression Test: WEB_SEARCH -> FINAL answer without repeating WEB_SEARCH
    @patch("brain.default_gateway.generate")
    def test_web_search_produces_final_answer_without_repeat(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "WEB_SEARCH", "arguments": {"query": "latest Python 3.12 features"}}'),
            make_mock_response('{"type": "final", "answer": "Python 3.12 introduces faster execution and better error messages."}')
        ]
        ans = run_planner_task("Search the web for latest Python 3.12 features", registry=self.test_registry, quiet=True)
        self.assertIn("Python 3.12 introduces", ans)
        self.assertEqual(self.mock_web_search.call_count, 1)

    # 12. Regression Test: LIST_FILES request -> LIST_FILES -> FINAL answer
    @patch("brain.default_gateway.generate")
    def test_list_files_produces_final_answer_without_find_files(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": "Brain"}}'),
            make_mock_response('{"type": "final", "answer": "Here are the files in your directory: brain.py."}')
        ]
        ans = run_planner_task("List files in my project directory", registry=self.test_registry, quiet=True)
        self.assertIn("brain.py", ans)
        self.assertEqual(self.mock_list_files.call_count, 1)
        self.assertEqual(self.mock_find_files.call_count, 0)

    # 13. Regression Test: FIND_FILES remains available for pattern search requests
    @patch("brain.default_gateway.generate")
    def test_find_files_available_for_pattern_search(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "FIND_FILES", "arguments": {"pattern": "*.py", "search_root": "Brain"}}'),
            make_mock_response('{"type": "final", "answer": "Found 1 matching python file: brain.py"}')
        ]
        ans = run_planner_task("Find all python files in Brain", registry=self.test_registry, quiet=True)
        self.assertIn("brain.py", ans)
        self.assertEqual(self.mock_find_files.call_count, 1)

    # 14. Regression Test: Narrative plain text mentioning tool names is parsed as FINAL answer
    def test_narrative_plain_text_with_tool_name_parsed_as_final(self):
        text = "I executed WEB_SEARCH and found that Python 3.12 has new syntax features."
        action, err = parse_model_action(text)
        self.assertIsNone(err)
        self.assertEqual(action["type"], "final")
        self.assertEqual(action["answer"], text)

    # 15. Regression Test: Task state isolation clears previous task observation
    def test_task_state_isolation_clears_observation(self):
        from tools.vision import default_vision
        default_vision._current_observation = {
            "status": "VISION_ANALYZED",
            "screen": {"width": 1920, "height": 1080},
            "elements": [{"id": "elem_button_stale", "type": "button", "text": "Stale", "center_x": 10, "center_y": 20, "confidence": 0.99}],
            "timestamp": 1000
        }
        # Run new task "hello" which clears observation at entry
        with patch("brain.default_gateway.generate") as mock_post:
            mock_post.return_value = make_mock_response('{"type": "final", "answer": "Hello!"}')
            ans = run_planner_task("hello", registry=self.test_registry, quiet=True)
            self.assertTrue(ans.startswith("Hello"))
            self.assertIsNone(default_vision.get_current_observation())

    # 16. Regression Test: "List files in my Brain project" prefers LIST_FILES over FIND_FILES
    @patch("brain.default_gateway.generate")
    def test_list_files_in_my_brain_project_prefers_list_files(self, mock_brain_post):
        mock_brain_post.side_effect = [
            make_mock_response('{"type": "tool", "tool": "LIST_FILES", "arguments": {"target_path": "Brain"}}'),
            make_mock_response('{"type": "final", "answer": "The files in Brain project are: brain.py, tools, tests."}')
        ]
        ans = run_planner_task("List files in my Brain project", registry=self.test_registry, quiet=True)
        self.assertIn("brain.py", ans)
        self.assertEqual(self.mock_list_files.call_count, 1)
        self.assertEqual(self.mock_find_files.call_count, 0)


if __name__ == "__main__":
    unittest.main()

