import os
import unittest
import tempfile
from pathlib import Path

from tools.files import (
    validate_safe_path,
    list_files,
    find_files,
    read_text_file,
    create_folder,
    ALLOWED_TEXT_EXTENSIONS
)


class TestFilesystemTools(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory structure simulating an approved safe root
        self.temp_dir = tempfile.TemporaryDirectory()
        self.safe_root = Path(self.temp_dir.name).resolve()
        self.safe_roots = [self.safe_root]

        # Create subdirectories and sample files
        self.sub_dir = self.safe_root / "subdir"
        self.sub_dir.mkdir()

        self.sample_text_file = self.safe_root / "sample.txt"
        self.sample_text_file.write_text("Hello from Brain unit tests!", encoding="utf-8")

        self.python_file = self.sub_dir / "code.py"
        self.python_file.write_text("print('test')", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. list_files() works
    def test_list_files_success(self):
        result = list_files(target_path=str(self.safe_root), safe_roots=self.safe_roots)
        self.assertIn("sample.txt", result)
        self.assertIn("subdir", result)

    # 2. find_files() works
    def test_find_files_success(self):
        result = find_files(pattern_or_query="*.py", search_root=str(self.safe_root), safe_roots=self.safe_roots)
        self.assertIn("code.py", result)

    # 3. read_text_file() works
    def test_read_text_file_success(self):
        result = read_text_file(filepath=str(self.sample_text_file), safe_roots=self.safe_roots)
        self.assertIn("Hello from Brain unit tests!", result)

    # 4. create_folder() works
    def test_create_folder_success(self):
        result = create_folder(folder_name="new_test_folder", parent_root=str(self.safe_root), safe_roots=self.safe_roots)
        self.assertIn("created successfully", result)
        created_path = self.safe_root / "new_test_folder"
        self.assertTrue(created_path.is_dir())

    # 5. Nonexistent path handled
    def test_nonexistent_path_handled(self):
        nonexistent = self.safe_root / "does_not_exist.txt"
        result = read_text_file(filepath=str(nonexistent), safe_roots=self.safe_roots)
        self.assertIn("does not exist", result)

    # 6. Path traversal rejected
    def test_path_traversal_rejected(self):
        traversal_path = str(self.safe_root / ".." / ".." / "etc" / "passwd")
        val, err = validate_safe_path(traversal_path, safe_roots=self.safe_roots)
        self.assertIsNone(val)
        self.assertIn("Access Denied", err)

    # 7. Absolute path outside safe roots rejected
    def test_outside_path_rejected(self):
        val, err = validate_safe_path("/etc/passwd", safe_roots=self.safe_roots)
        self.assertIsNone(val)
        self.assertIn("Access Denied", err)

    # 8. Symlink escape rejected
    def test_symlink_escape_rejected(self):
        outside_target = Path("/etc")
        symlink_path = self.safe_root / "evil_symlink"
        try:
            os.symlink(outside_target, symlink_path)
            val, err = validate_safe_path(symlink_path, safe_roots=self.safe_roots)
            self.assertIsNone(val)
            self.assertIn("Access Denied", err)
        except OSError:
            pass  # Skip if system permissions prevent symlink creation

    # 9. Oversized text file rejected (>1 MB)
    def test_oversized_file_rejected(self):
        large_file = self.safe_root / "large.txt"
        # Write 1.1 MB file
        large_file.write_bytes(b"A" * (1 * 1024 * 1024 + 100))
        result = read_text_file(filepath=str(large_file), max_size=1 * 1024 * 1024, safe_roots=self.safe_roots)
        self.assertIn("exceeds the maximum 1 MB limit", result)

    # 10. Binary file rejected
    def test_binary_file_rejected(self):
        bin_file = self.safe_root / "image.png"
        bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\xff\xfe")
        result = read_text_file(filepath=str(bin_file), safe_roots=self.safe_roots)
        self.assertIn("not in the allowed text file types", result)

    # 11. Unsupported file extension rejected
    def test_unsupported_extension_rejected(self):
        exe_file = self.safe_root / "script.sh"
        exe_file.write_text("echo hello", encoding="utf-8")
        result = read_text_file(filepath=str(exe_file), safe_roots=self.safe_roots)
        self.assertIn("not in the allowed text file types", result)

    # 12. Invalid folder name rejected
    def test_invalid_folder_name_rejected(self):
        result = create_folder(folder_name="../sub", parent_root=str(self.safe_root), safe_roots=self.safe_roots)
        self.assertIn("Invalid folder name", result)


if __name__ == "__main__":
    unittest.main()
