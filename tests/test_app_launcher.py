import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.app_launcher import (
    parse_desktop_file,
    discover_apps,
    resolve_app,
    launch_app,
    list_apps,
    refresh_app_index,
    _launch_backend,
    SEARCH_DIRECTORIES
)
from tools.registry import default_registry
from tools.router import default_router
import brain


class TestAppLauncher(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"
        refresh_app_index()

    def tearDown(self):
        refresh_app_index()

    def test_01_application_discovery(self):
        """1. Test application discovery scans directories and finds apps."""
        apps = discover_apps()
        self.assertIsInstance(apps, dict)

    def test_02_valid_desktop_parsing(self):
        """2. Test valid .desktop file parsing extracts required fields."""
        with tempfile.NamedTemporaryFile("w", suffix=".desktop", delete=False) as f:
            f.write("""[Desktop Entry]
Type=Application
Name=Test Calculator
GenericName=Calculator Tool
Exec=test-calculator %u
Icon=calculator
Categories=Utility;
""")
            f_path = f.name

        try:
            parsed = parse_desktop_file(f_path)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["Name"], "Test Calculator")
            self.assertEqual(parsed["GenericName"], "Calculator Tool")
            self.assertEqual(parsed["Exec"], "test-calculator %u")
            self.assertEqual(parsed["Icon"], "calculator")
            self.assertFalse(parsed["NoDisplay"])
            self.assertFalse(parsed["Hidden"])
            self.assertFalse(parsed["Terminal"])
        finally:
            os.remove(f_path)

    def test_03_hidden_applications_excluded(self):
        """3. Test applications with Hidden=true are excluded."""
        with tempfile.NamedTemporaryFile("w", suffix=".desktop", delete=False) as f:
            f.write("""[Desktop Entry]
Type=Application
Name=Hidden App
Exec=hidden-app
Hidden=true
""")
            f_path = f.name

        try:
            parsed = parse_desktop_file(f_path)
            self.assertIsNone(parsed)
        finally:
            os.remove(f_path)

    def test_04_nodisplay_applications_excluded(self):
        """4. Test applications with NoDisplay=true are excluded."""
        with tempfile.NamedTemporaryFile("w", suffix=".desktop", delete=False) as f:
            f.write("""[Desktop Entry]
Type=Application
Name=Internal App
Exec=internal-app
NoDisplay=true
""")
            f_path = f.name

        try:
            parsed = parse_desktop_file(f_path)
            self.assertIsNone(parsed)
        finally:
            os.remove(f_path)

    def test_05_malformed_desktop_handled_safely(self):
        """5. Test malformed .desktop files are handled safely without crashing."""
        with tempfile.NamedTemporaryFile("w", suffix=".desktop", delete=False) as f:
            f.write("Random corrupt contents without Desktop Entry section = true\n")
            f_path = f.name

        try:
            parsed = parse_desktop_file(f_path)
            self.assertIsNone(parsed)
        finally:
            os.remove(f_path)

    def test_06_exact_application_resolution(self):
        """6. Test exact application resolution."""
        mock_apps = {
            "firefox.desktop": {
                "Name": "Firefox Web Browser",
                "GenericName": "Web Browser",
                "Exec": "firefox %u",
                "desktop_id": "firefox.desktop"
            },
            "calculator.desktop": {
                "Name": "Calculator",
                "GenericName": "Calculator",
                "Exec": "gnome-calculator",
                "desktop_id": "calculator.desktop"
            }
        }
        with patch("tools.app_launcher.discover_apps", return_value=mock_apps):
            res = resolve_app("Firefox Web Browser")
            self.assertIsNotNone(res)
            self.assertEqual(res["Name"], "Firefox Web Browser")

    def test_07_case_insensitive_resolution(self):
        """7. Test case-insensitive application resolution."""
        mock_apps = {
            "firefox.desktop": {
                "Name": "Firefox",
                "GenericName": "Web Browser",
                "Exec": "firefox %u",
                "desktop_id": "firefox.desktop"
            }
        }
        with patch("tools.app_launcher.discover_apps", return_value=mock_apps):
            res1 = resolve_app("firefox")
            res2 = resolve_app("FIREFOX")
            self.assertIsNotNone(res1)
            self.assertIsNotNone(res2)
            self.assertEqual(res1["Name"], "Firefox")
            self.assertEqual(res2["Name"], "Firefox")

    def test_08_unknown_application_rejected(self):
        """8. Test unknown application is cleanly rejected."""
        res = launch_app("NonExistentApplication12345")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"])

    def test_09_ambiguous_application_rejected(self):
        """9. Test ambiguous application resolution returns matches."""
        mock_apps = {
            "editor1.desktop": {
                "Name": "Text Editor One",
                "GenericName": "Editor",
                "Exec": "editor1",
                "desktop_id": "editor1.desktop"
            },
            "editor2.desktop": {
                "Name": "Text Editor Two",
                "GenericName": "Editor",
                "Exec": "editor2",
                "desktop_id": "editor2.desktop"
            }
        }
        with patch("tools.app_launcher.discover_apps", return_value=mock_apps):
            res = resolve_app("Editor")
            self.assertIsInstance(res, dict)
            self.assertTrue(res.get("ambiguous"))
            self.assertEqual(len(res.get("matches")), 2)

            launch_res = launch_app("Editor")
            self.assertFalse(launch_res["success"])
            self.assertEqual(launch_res["error"], "Multiple applications match")
            self.assertEqual(len(launch_res["matches"]), 2)

    def test_10_launch_backend_called_correctly(self):
        """10. Test launch backend is called correctly with mock backend."""
        mock_app = {
            "Name": "Demo App",
            "Exec": "demo-app",
            "filepath": "/usr/share/applications/demo-app.desktop",
            "desktop_id": "demo-app.desktop"
        }
        with patch("tools.app_launcher.resolve_app", return_value=mock_app):
            with patch("tools.app_launcher._launch_backend", return_value=True) as mock_backend:
                res = launch_app("Demo App")
                self.assertTrue(res["success"])
                mock_backend.assert_called_once_with(mock_app)

    def test_11_arbitrary_shell_command_rejected(self):
        """11. Test arbitrary shell commands are rejected by launcher."""
        commands = [
            "sudo rm -rf /",
            "bash -c 'ls'",
            "sh -c 'echo hi'",
            "python3 -c 'import os'",
            "open ~/Downloads/test.pdf"
        ]
        for cmd in commands:
            res = launch_app(cmd)
            self.assertFalse(res["success"], f"Command '{cmd}' should have been rejected.")

    def test_12_shell_true_never_used(self):
        """12. Test subprocess is never called with shell=True."""
        with patch("subprocess.Popen") as mock_popen:
            mock_app = {
                "Name": "Safe App",
                "Exec": "safe-app --option",
                "filepath": "/usr/share/applications/safe-app.desktop",
                "desktop_id": "safe-app.desktop"
            }
            # Temporarily turn off mock mode to check low-level Popen call flags
            with patch.dict(os.environ, {"BRAIN_MOCK_GUI": "0"}):
                with patch("shutil.which", return_value="/usr/bin/safe-app"):
                    _launch_backend(mock_app)
                    if mock_popen.called:
                        kwargs = mock_popen.call_args[1]
                        self.assertFalse(kwargs.get("shell", False))

    def test_13_open_app_registered(self):
        """13. Test OPEN_APP is registered in default_registry."""
        tool = default_registry.get("OPEN_APP")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "OPEN_APP")
        self.assertEqual(tool.risk_level, "MEDIUM")

    def test_14_list_apps_registered(self):
        """14. Test LIST_APPS is registered in default_registry."""
        tool = default_registry.get("LIST_APPS")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "LIST_APPS")
        self.assertEqual(tool.risk_level, "LOW")

    def test_15_deterministic_command_path_works(self):
        """15. Test deterministic FastRouter pre-routes open app and list apps commands."""
        # Test FastRouter for open app
        route_open = default_router.route("open Firefox")
        self.assertIsNotNone(route_open)
        self.assertEqual(route_open["type"], "tool")
        self.assertEqual(route_open["tool"], "OPEN_APP")
        self.assertEqual(route_open["arguments"].get("name"), "Firefox")

        # Test FastRouter for list apps
        route_list = default_router.route("list apps")
        self.assertIsNotNone(route_list)
        self.assertEqual(route_list["type"], "tool")
        self.assertEqual(route_list["tool"], "LIST_APPS")

    def test_16_regression_verification(self):
        """16. Test existing tool registry functionality works without regression."""
        time_tool = default_registry.get("TIME")
        self.assertIsNotNone(time_tool)
        res = default_registry.execute("TIME", {})
        self.assertTrue(res["success"])


if __name__ == "__main__":
    unittest.main()
