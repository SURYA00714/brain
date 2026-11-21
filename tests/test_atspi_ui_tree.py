import os
import unittest
from tools.ui_tree import (
    AccessibleNode,
    LinuxAccessibilityTree,
    default_ui_tree,
    inspect_accessible_tree,
    find_accessible_element,
    click_accessible_element,
    type_accessible_element,
)
from tools.registry import default_registry


class TestLinuxAccessibilityTree(unittest.TestCase):
    """Unit tests for Linux AT-SPI Accessibility Tree desktop inspection."""

    def test_accessible_node_dataclass(self):
        """Verifies AccessibleNode attributes, center coordinate computation, and serialization."""
        node = AccessibleNode(
            name="Search",
            role="entry",
            description="Search query input",
            x=100,
            y=200,
            width=300,
            height=50,
            app_name="Brave Browser",
            depth=1,
        )
        self.assertEqual(node.name, "Search")
        self.assertEqual(node.role, "entry")
        self.assertEqual(node.center_x, 250)  # 100 + 300 // 2
        self.assertEqual(node.center_y, 225)  # 200 + 50 // 2

        d = node.to_dict()
        self.assertEqual(d["name"], "Search")
        self.assertEqual(d["center_x"], 250)
        self.assertEqual(d["center_y"], 225)
        self.assertEqual(d["app_name"], "Brave Browser")

    def test_mock_environment_fallback(self):
        """Ensures deterministic fallback behavior when BRAIN_MOCK_GUI=1 is active."""
        orig_mock = os.environ.get("BRAIN_MOCK_GUI")
        try:
            os.environ["BRAIN_MOCK_GUI"] = "1"
            tree = LinuxAccessibilityTree()
            apps = tree.list_accessible_apps()
            self.assertTrue(len(apps) >= 1)
            self.assertEqual(apps[0]["app_name"], "Brave Browser")

            nodes = tree.inspect_tree(max_depth=3)
            self.assertTrue(len(nodes) >= 3)
            names = [n.name for n in nodes]
            self.assertIn("YouTube - Brave", names)
            self.assertIn("Search", names)
        finally:
            if orig_mock is not None:
                os.environ["BRAIN_MOCK_GUI"] = orig_mock
            else:
                os.environ.pop("BRAIN_MOCK_GUI", None)

    def test_find_element_priority(self):
        """Verifies interactive element prioritization during search."""
        orig_mock = os.environ.get("BRAIN_MOCK_GUI")
        try:
            os.environ["BRAIN_MOCK_GUI"] = "1"
            tree = LinuxAccessibilityTree()

            # Search by exact name
            found_play = tree.find_element(query="Play")
            self.assertIsNotNone(found_play)
            self.assertEqual(found_play.name, "Play")
            self.assertEqual(found_play.role, "push button")

            # Search by role
            found_entry = tree.find_element(query="", role="entry")
            self.assertIsNotNone(found_entry)
            self.assertEqual(found_entry.role, "entry")

            # Nonexistent element
            found_none = tree.find_element(query="NonExistentButtonXYZ999")
            self.assertIsNone(found_none)
        finally:
            if orig_mock is not None:
                os.environ["BRAIN_MOCK_GUI"] = orig_mock
            else:
                os.environ.pop("BRAIN_MOCK_GUI", None)

    def test_registry_tool_registration(self):
        """Verifies all 4 AT-SPI tools are properly registered in ToolRegistry."""
        expected_tools = [
            "INSPECT_ACCESSIBLE_TREE",
            "FIND_ACCESSIBLE_ELEMENT",
            "CLICK_ACCESSIBLE_ELEMENT",
            "TYPE_ACCESSIBLE_ELEMENT",
        ]
        for tool_name in expected_tools:
            tool = default_registry.get(tool_name)
            self.assertIsNotNone(tool, f"Expected {tool_name} to be in default_registry")
            self.assertIn("parameters", tool.to_dict())
            self.assertIn("description", tool.to_dict())

    def test_inspect_and_find_tool_execution(self):
        """Executes exported tool functions and validates standard dict response contract."""
        res_inspect = inspect_accessible_tree(max_depth=2, max_elements=20)
        self.assertTrue(res_inspect["success"])
        self.assertEqual(res_inspect["tool"], "INSPECT_ACCESSIBLE_TREE")
        self.assertIsInstance(res_inspect["elements"], list)

        # Nonexistent element check
        res_not_found = find_accessible_element(query="DefinitelyNonExistentButton987654321")
        self.assertFalse(res_not_found["success"])
        self.assertFalse(res_not_found["found"])


if __name__ == "__main__":
    unittest.main()
