import os
import shutil
import unittest
from pathlib import Path
from tools.files import (
    list_files, find_files, read_text_file, create_folder,
    create_file, copy_file, move_file, rename_file, file_info, delete_file
)
from tools.router import FastRouter
from tools.registry import default_registry

TEST_DIR = Path("/home/jai/Downloads/Brain/scratch/test_filesystem_sandbox")

class TestSafeFilesystem(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"
        TEST_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR, ignore_errors=True)

    def test_create_and_inspect_file(self):
        res = create_file("sample_test.txt", parent_root="Downloads")
        self.assertTrue(res["success"])
        self.assertEqual(res["tool"], "CREATE_FILE")

        info = file_info("Downloads/sample_test.txt")
        self.assertTrue(info["success"])
        self.assertEqual(info["tool"], "FILE_INFO")
        delete_file("Downloads/sample_test.txt", confirmed=True)

    def test_copy_move_rename_file(self):
        create_file("test_a.txt", parent_root="Downloads")
        
        # Copy
        cp = copy_file("Downloads/test_a.txt", "Downloads/test_a_copy.txt")
        self.assertTrue(cp["success"])
        self.assertEqual(cp["tool"], "COPY_FILE")

        # Rename
        ren = rename_file("Downloads/test_a_copy.txt", "test_a_renamed.txt")
        self.assertTrue(ren["success"])

        # Move
        mv = move_file("Downloads/test_a_renamed.txt", "Brain")
        self.assertTrue(mv["success"])

        # Clean up created test files in Brain & Downloads
        delete_file("Downloads/test_a.txt", confirmed=True)
        delete_file("Brain/test_a_renamed.txt", confirmed=True)

    def test_path_traversal_rejection(self):
        # Attempting path traversal outside safe directories
        res_cf = create_file("../../../etc/shadow", parent_root="Downloads")
        self.assertFalse(res_cf["success"])

        res_del = delete_file("/etc/passwd", confirmed=True)
        self.assertFalse(res_del["success"])
        self.assertIn("Access Denied", res_del["error"])

    def test_registry_integration(self):
        registered_tools = [t["name"] for t in default_registry.list_tools()]
        expected = [
            "LIST_FILES", "FIND_FILES", "READ_TEXT_FILE", "CREATE_FOLDER",
            "LIST_DIRECTORY", "CREATE_FILE", "COPY_FILE", "MOVE_FILE",
            "RENAME_FILE", "SEARCH_FILES", "FILE_INFO", "DELETE_FILE"
        ]
        for t in expected:
            self.assertIn(t, registered_tools, f"Tool {t} not found in ToolRegistry.")

    def test_fast_router_zero_llm(self):
        router = FastRouter()
        queries = [
            ("list downloads", "LIST_FILES"),
            ("create folder test_dir", "CREATE_FOLDER"),
            ("create file notes.txt", "CREATE_FILE"),
            ("copy file_a.txt to file_b.txt", "COPY_FILE"),
            ("move report.pdf to Documents", "MOVE_FILE"),
            ("rename old.txt to new.txt", "RENAME_FILE"),
            ("delete file junk.tmp", "DELETE_FILE")
        ]
        for text, expected_tool in queries:
            res = router.route(text)
            self.assertIsNotNone(res, f"Failed to route: {text}")
            self.assertEqual(res.get("type"), "tool")
            self.assertEqual(res.get("tool"), expected_tool)

if __name__ == "__main__":
    unittest.main()
