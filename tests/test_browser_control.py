import os
import unittest
from tools.browser import (
    browser_open, browser_navigate, browser_back, browser_forward,
    browser_reload, browser_title, browser_url, browser_find_text,
    browser_extract_text, browser_click, browser_fill, browser_press,
    browser_select, browser_scroll_page, browser_wait, browser_close_tab,
    browser_switch_tab, browser_list_tabs, browser_download
)
from tools.router import FastRouter
from tools.registry import default_registry

class TestBrowserControl(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_browser_navigation_and_tabs(self):
        b_open = browser_open("https://example.com")
        self.assertTrue(b_open["success"])

        b_nav = browser_navigate("https://python.org")
        self.assertTrue(b_nav["success"])

        b_back = browser_back()
        self.assertTrue(b_back["success"])

        b_fwd = browser_forward()
        self.assertTrue(b_fwd["success"])

        b_rel = browser_reload()
        self.assertTrue(b_rel["success"])

        b_close_t = browser_close_tab()
        self.assertTrue(b_close_t["success"])

        b_sw_t = browser_switch_tab(2)
        self.assertTrue(b_sw_t["success"])

        b_lst_t = browser_list_tabs()
        self.assertTrue(b_lst_t["success"])
        self.assertGreater(b_lst_t["count"], 0)

    def test_browser_inspection_and_dom_interaction(self):
        t = browser_title()
        self.assertTrue(t["success"])
        self.assertIn("title", t)

        u = browser_url()
        self.assertTrue(u["success"])

        ft = browser_find_text("Python")
        self.assertTrue(ft["success"])

        ext = browser_extract_text("body")
        self.assertTrue(ext["success"])
        self.assertIn("[UNTRUSTED_WEBPAGE_DATA]", ext["data"])

        cl = browser_click("#submit-btn")
        self.assertTrue(cl["success"])

        fl = browser_fill("#search-input", "Playwright testing")
        self.assertTrue(fl["success"])

        pr = browser_press("enter")
        self.assertTrue(pr["success"])

        sel = browser_select("#lang-dropdown", "English")
        self.assertTrue(sel["success"])

        sc = browser_scroll_page("down", 500)
        self.assertTrue(sc["success"])

        wt = browser_wait(0.5)
        self.assertTrue(wt["success"])

    def test_registry_integration(self):
        registered_tools = [t["name"] for t in default_registry.list_tools()]
        expected = [
            "BROWSER_OPEN", "BROWSER_NAVIGATE", "BROWSER_BACK", "BROWSER_FORWARD",
            "BROWSER_RELOAD", "BROWSER_TITLE", "BROWSER_URL", "BROWSER_FIND_TEXT",
            "BROWSER_EXTRACT_TEXT", "BROWSER_CLICK", "BROWSER_FILL", "BROWSER_PRESS",
            "BROWSER_SELECT", "BROWSER_SCROLL", "BROWSER_WAIT", "BROWSER_CLOSE_TAB",
            "BROWSER_SWITCH_TAB", "BROWSER_LIST_TABS", "BROWSER_DOWNLOAD"
        ]
        for t in expected:
            self.assertIn(t, registered_tools, f"Tool {t} not found in ToolRegistry.")

    def test_fast_router_zero_llm(self):
        router = FastRouter()
        queries = [
            ("go back", "BROWSER_BACK"),
            ("go forward", "BROWSER_FORWARD"),
            ("reload page", "BROWSER_RELOAD"),
            ("get page title", "BROWSER_TITLE"),
            ("get page url", "BROWSER_URL"),
            ("close tab", "BROWSER_CLOSE_TAB"),
            ("list tabs", "BROWSER_LIST_TABS"),
            ("scroll down", "BROWSER_SCROLL"),
            ("download https://example.com/file.pdf", "BROWSER_DOWNLOAD")
        ]
        for text, expected_tool in queries:
            res = router.route(text)
            self.assertIsNotNone(res, f"Failed to route: {text}")
            self.assertEqual(res.get("type"), "tool")
            self.assertEqual(res.get("tool"), expected_tool)

if __name__ == "__main__":
    unittest.main()
