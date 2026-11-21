import os
import unittest
from tools.ui_driver import DesktopUIDriver, default_ui_driver
from tools.ui_tree import AccessibleNode, LinuxAccessibilityTree
from tools.router import default_router
from core.cognition import verify_step_execution


class MockAccessibilityTree:
    """Mock AT-SPI tree for deterministic testing without requiring live desktop widgets."""

    def __init__(self):
        self.nodes = [
            AccessibleNode(
                name="Search",
                role="entry",
                x=100,
                y=100,
                width=200,
                height=30,
                app_name="Brave Browser",
                bus_name=":1.99",
                path="/org/a11y/atspi/accessible/1"
            ),
            AccessibleNode(
                name="Submit",
                role="push button",
                x=320,
                y=100,
                width=80,
                height=30,
                app_name="Brave Browser",
                bus_name=":1.99",
                path="/org/a11y/atspi/accessible/2"
            ),
            AccessibleNode(
                name="Close",
                role="push button",
                x=800,
                y=10,
                width=20,
                height=20,
                app_name="xfce4-terminal",
                bus_name=":1.100",
                path="/org/a11y/atspi/accessible/3"
            )
        ]

    def find_element(self, query: str, role=None, app_name=None):
        q_low = query.lower()
        for n in self.nodes:
            if q_low in n.name.lower():
                if role and role.lower() not in n.role.lower():
                    continue
                if app_name and app_name.lower() not in n.app_name.lower():
                    continue
                return n
        return None

    def inspect_tree(self, app_name=None, max_depth=2):
        if app_name:
            return [n for n in self.nodes if app_name.lower() in n.app_name.lower()]
        return self.nodes

    def get_a11y_bus(self):
        return None


class TestUIDriverATSPI(unittest.TestCase):
    """Test suite for Phase 5 Autonomous Desktop UI Interaction."""

    def setUp(self):
        self.mock_tree = MockAccessibilityTree()
        self.driver = DesktopUIDriver(ui_tree=self.mock_tree)

    def test_click_element_found(self):
        """Verifies click_element resolves coordinate geometry and executes cleanly."""
        res = self.driver.click_element("Submit", role="push button", app_name="Brave")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("tool"), "CLICK_UI_ELEMENT")
        elem = res.get("element", {})
        self.assertEqual(elem.get("name"), "Submit")
        self.assertEqual(elem.get("center_x"), 360)  # 320 + 80 // 2

    def test_click_element_not_found(self):
        """Verifies click_element returns informative failure when element doesn't exist."""
        res = self.driver.click_element("NonExistentButton999")
        self.assertFalse(res.get("success"))
        self.assertIn("not found", res.get("error", "").lower())

    def test_type_in_element(self):
        """Verifies type_in_element targets the input field and delivers text."""
        res = self.driver.type_in_element("Search", text="gta 6 release", app_name="Brave")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("tool"), "TYPE_UI_ELEMENT")
        self.assertEqual(res.get("text"), "gta 6 release")

    def test_wait_for_element_success(self):
        """Verifies wait_for_element detects element presence without hanging."""
        res = self.driver.wait_for_element("Close", timeout_sec=1.0)
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("found"))

    def test_wait_for_element_timeout(self):
        """Verifies wait_for_element respects timeout for missing element."""
        res = self.driver.wait_for_element("MissingWidget", timeout_sec=0.2)
        self.assertFalse(res.get("success"))
        self.assertFalse(res.get("found"))

    def test_inspect_app_ui(self):
        """Verifies inspect_app_ui returns structured node elements."""
        res = self.driver.inspect_app_ui("Brave Browser", max_depth=1)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("count"), 2)

    def test_router_click_ui_command(self):
        """Verifies router recognizes 'click submit button on brave'."""
        route = default_router.route("click submit button on brave")
        self.assertIsNotNone(route)
        self.assertEqual(route.get("type"), "tool")
        self.assertEqual(route.get("tool"), "CLICK_UI_ELEMENT")
        args = route.get("arguments", {})
        self.assertEqual(args.get("query"), "submit")
        self.assertEqual(args.get("app_name"), "brave")

    def test_router_type_ui_command(self):
        """Verifies router recognizes 'type hello into search on brave'."""
        route = default_router.route("type hello into search on brave")
        self.assertIsNotNone(route)
        self.assertEqual(route.get("type"), "tool")
        self.assertEqual(route.get("tool"), "TYPE_UI_ELEMENT")
        args = route.get("arguments", {})
        self.assertEqual(args.get("text"), "hello")
        self.assertEqual(args.get("query"), "search")
        self.assertEqual(args.get("app_name"), "brave")

    def test_verify_step_execution_ui_click(self):
        """Verifies cognition verification for CLICK_UI_ELEMENT."""
        ok, status, msg = verify_step_execution(
            "CLICK_UI_ELEMENT",
            {"query": "Submit"},
            {"success": True, "method": "atspi_native_action", "data": {"element": {"name": "Submit"}}}
        )
        self.assertTrue(ok)
        self.assertEqual(status, "VERIFIED")


if __name__ == "__main__":
    unittest.main()
