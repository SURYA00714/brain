import unittest
from unittest.mock import patch, MagicMock
import requests

from brain import ask_brain, clean_search_query, ALLOWED_INTENTS
from tools.apps import open_app, open_brave, APPROVED_APPS
from tools.search import perform_web_search, clean_url
from tools.files import list_files, find_files, read_text_file, create_folder, validate_safe_path


class TestBrainMainController(unittest.TestCase):

    # --- Phase 3B Filesystem Classification Tests ---

    @patch("brain.requests.post")
    def test_ask_brain_list_files_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "LIST_FILES: Downloads"}
        mock_post.return_value = mock_response

        intent, loc = ask_brain("list files in Downloads")
        self.assertEqual(intent, "LIST_FILES")
        self.assertEqual(loc, "Downloads")

    @patch("brain.requests.post")
    def test_ask_brain_find_files_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "FIND_FILES: *.py | Brain"}
        mock_post.return_value = mock_response

        intent, (pattern, loc) = ask_brain("find Python files in Brain")
        self.assertEqual(intent, "FIND_FILES")
        self.assertEqual(pattern, "*.py")
        self.assertEqual(loc, "Brain")

    @patch("brain.requests.post")
    def test_ask_brain_read_text_file_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "READ_TEXT_FILE: brain.py"}
        mock_post.return_value = mock_response

        intent, filepath = ask_brain("read brain.py")
        self.assertEqual(intent, "READ_TEXT_FILE")
        self.assertEqual(filepath, "brain.py")

    @patch("brain.requests.post")
    def test_ask_brain_create_folder_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "CREATE_FOLDER: brain_test | Downloads"}
        mock_post.return_value = mock_response

        intent, (name, parent) = ask_brain("create a folder called brain_test in Downloads")
        self.assertEqual(intent, "CREATE_FOLDER")
        self.assertEqual(name, "brain_test")
        self.assertEqual(parent, "Downloads")

    # --- Phase 3A Application Control & Safety Tests ---

    @patch("tools.apps.subprocess.Popen")
    def test_open_app_brave(self, mock_popen):
        result = open_app("brave")
        self.assertIn("opened successfully", result)

    @patch("tools.apps.subprocess.Popen")
    def test_open_app_terminal(self, mock_popen):
        result = open_app("terminal")
        self.assertIn("opened successfully", result)

    @patch("tools.apps.subprocess.Popen")
    def test_open_app_unapproved_rejection(self, mock_popen):
        result = open_app("malware_app")
        self.assertIn("not in the approved safety allowlist", result)
        mock_popen.assert_not_called()

    # --- Web Search & Chat Intent Tests ---

    @patch("brain.requests.post")
    def test_ask_brain_web_search_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "WEB_SEARCH: Python tutorials"}
        mock_post.return_value = mock_response

        intent, query = ask_brain("search the web for Python tutorials")
        self.assertEqual(intent, "WEB_SEARCH")
        self.assertEqual(query, "Python tutorials")

    @patch("brain.requests.post")
    def test_ask_brain_chat_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "CHAT"}
        mock_post.return_value = mock_response

        intent, query = ask_brain("what is Linux?")
        self.assertEqual(intent, "CHAT")

    # --- Empty Input Interaction Test ---

    @patch("brain.perform_web_search")
    @patch("brain.open_app")
    @patch("brain.ask_brain")
    @patch("builtins.input", side_effect=["", "   ", "exit"])
    def test_empty_input_does_not_call_qwen_or_tools(self, mock_input, mock_ask, mock_app, mock_search):
        from brain import run_brain
        run_brain()

        mock_ask.assert_not_called()
        mock_app.assert_not_called()
        mock_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
