"""
Automated Test Suite for Universal Website Search & Input Detection in Brain.
Covers all 14 required test scenarios using deterministic local HTML fixtures
without external internet or live website dependencies.
"""

import unittest
import os
from unittest.mock import patch
from tools.search_detection import (
    BrowserPageInspector,
    SearchFieldRanker,
    SearchVerificationEngine,
    UniversalSearchExecutor,
    default_search_executor
)
from tools.browser import browser_search
from tools.registry import default_registry


class TestUniversalBrowserSearch(unittest.TestCase):
    def setUp(self):
        self.inspector = BrowserPageInspector()
        self.ranker = SearchFieldRanker()
        self.verifier = SearchVerificationEngine()
        self.executor = UniversalSearchExecutor()

    # 1. Standard search input (<input type="search">)
    def test_01_standard_search_input(self):
        html = """
        <html><body>
            <h1>Welcome to Python Docs</h1>
            <input type="search" id="site-search" name="q" placeholder="Type here">
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        self.assertEqual(len(candidates), 1)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertIsNotNone(best)
        self.assertEqual(best.input_type, "search")
        self.assertEqual(best.selector, "#site-search")

    # 2. Search field with placeholder
    def test_02_search_field_with_placeholder(self):
        html = """
        <html><body>
            <input type="text" id="main-in" placeholder="Search Python tutorials and libraries">
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertIsNotNone(best)
        self.assertIn("search", best.placeholder.lower())
        self.assertGreater(best.score, 50.0)

    # 3. Search field with ARIA labels and roles
    def test_03_search_field_with_aria_labels(self):
        html = """
        <html><body>
            <div role="search">
                <input type="text" role="searchbox" aria-label="Search documentation" name="query">
            </div>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertIsNotNone(best)
        self.assertEqual(best.role, "searchbox")
        self.assertEqual(best.aria_label, "Search documentation")
        self.assertGreaterEqual(best.score, 100.0)

    # 4. Search button submission
    def test_04_search_button_submission(self):
        html = """
        <html><body>
            <form action="/search" method="get">
                <input type="search" name="q" id="search-bar">
                <button type="submit" id="search-btn">Search</button>
            </form>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertTrue(best.has_search_button)
        self.assertEqual(best.search_button_selector, "#search-btn")

        res = self.executor.execute_search("asyncio patterns", url="https://example.com", html_fixture=html, mock_mode=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["submission_method"], "button")
        self.assertTrue(res["verified"])

    # 5. Enter-key submission (when no button is present)
    def test_05_enter_key_submission(self):
        html = """
        <html><body>
            <form action="/search">
                <input type="search" name="q" placeholder="Search and press Enter">
            </form>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertFalse(best.has_search_button)

        res = self.executor.execute_search("web scrapers", url="https://example.com", html_fixture=html, mock_mode=True)
        self.assertEqual(res["submission_method"], "enter_key")
        self.assertEqual(res["status"], "SUCCESS")

    # 6. Website with multiple input fields (search vs email vs newsletter vs login)
    def test_06_multiple_inputs_filtering(self):
        html = """
        <html><body>
            <div id="login-form">
                <input type="text" name="username" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
            </div>
            <header>
                <input type="search" name="q" placeholder="Search catalog">
            </header>
            <footer>
                <input type="text" name="email" placeholder="Sign up for newsletter">
            </footer>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        # Password should be completely stripped by inspector
        self.assertFalse(any(c.input_type == "password" or "password" in c.name for c in candidates))
        
        # Ranker should cleanly pick the catalog search input
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(best.name, "q")
        self.assertEqual(best.input_type, "search")

    # 7. Website without a search field
    def test_07_website_without_search_field(self):
        html = """
        <html><body>
            <h1>About Us</h1>
            <p>We are a technology consultancy.</p>
            <input type="text" name="your_name" placeholder="Your Name">
            <input type="text" name="your_email" placeholder="Your Email">
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "INPUT_NOT_FOUND")
        self.assertIsNone(best)

        res = self.executor.execute_search("consultancy rates", url="https://agency.com", html_fixture=html, mock_mode=True)
        self.assertEqual(res["status"], "INPUT_NOT_FOUND")
        self.assertFalse(res["success"])
        self.assertFalse(res["input_detected"])

    # 8. Dynamically rendered search fields & contenteditable
    def test_08_contenteditable_and_dynamic_fields(self):
        html = """
        <html><body>
            <div contenteditable="true" role="searchbox" aria-label="Search posts" id="editable-search"></div>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        self.assertEqual(len(candidates), 1)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(best.selector, "#editable-search")
        self.assertEqual(best.role, "searchbox")

    # 9. Hidden and disabled inputs
    def test_09_hidden_and_disabled_inputs(self):
        html = """
        <html><body>
            <input type="search" name="hidden_q" style="display: none;" placeholder="Search hidden">
            <input type="search" name="disabled_q" disabled placeholder="Search disabled">
            <input type="search" name="readonly_q" readonly placeholder="Search readonly">
            <input type="search" name="active_search" placeholder="Search visible">
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "active_search")

    # 10. Ambiguous input fields
    def test_10_ambiguous_input_fields(self):
        html = """
        <html><body>
            <input type="search" name="search_articles" placeholder="Search articles">
            <input type="search" name="search_products" placeholder="Search products">
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        self.assertEqual(len(candidates), 2)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "AMBIGUOUS_INPUT")
        self.assertIsNone(best)

        res = self.executor.execute_search("gadgets", url="https://portal.com", html_fixture=html, mock_mode=True)
        self.assertEqual(res["status"], "AMBIGUOUS_INPUT")
        self.assertFalse(res["success"])

    # 11. Failed submissions
    def test_11_failed_submissions(self):
        # Empty query submission
        res = self.executor.execute_search("", url="https://example.com")
        self.assertEqual(res["status"], "SUBMISSION_FAILED")
        self.assertFalse(res["success"])
        self.assertIn("cannot be empty", res["evidence"])

    # 12. Search result verification
    def test_12_search_result_verification(self):
        # Case A: Success with URL query parameter
        ver_ok, status_ok, ev_ok = self.verifier.verify(
            query="quantum computing",
            initial_url="https://site.com",
            final_url="https://site.com/search?q=quantum+computing",
            initial_content="Home",
            final_content="Results for quantum computing"
        )
        self.assertTrue(ver_ok)
        self.assertEqual(status_ok, "SUCCESS")

        # Case B: Verification failed when nothing changed
        ver_fail, status_fail, ev_fail = self.verifier.verify(
            query="quantum computing",
            initial_url="https://site.com",
            final_url="https://site.com",
            initial_content="Home",
            final_content="Home"
        )
        self.assertFalse(ver_fail)
        self.assertEqual(status_fail, "VERIFICATION_FAILED")

    # 13. Iframes and shadow DOM accessibility fallback
    def test_13_iframe_and_accessible_container(self):
        html = """
        <html><body>
            <iframe src="/search_frame.html">
                <input type="search" aria-label="Search inside embedded frame" id="iframe-search">
            </iframe>
        </body></html>
        """
        candidates = self.inspector.inspect_html(html)
        self.assertGreaterEqual(len(candidates), 1)
        best, status = self.ranker.select_best_candidate(candidates)
        self.assertEqual(status, "SUCCESS")
        self.assertEqual(best.selector, "#iframe-search")

    # 14. Brain tool integration test & registry contract
    def test_14_brain_tool_integration(self):
        # Tool is registered in default_registry
        tool = default_registry.get("BROWSER_SEARCH")
        self.assertIsNotNone(tool)
        self.assertIn("query", tool.parameters)
        self.assertIn("url", tool.parameters)

        # Call browser_search with URL in mock mode
        with patch.dict(os.environ, {"BRAIN_MOCK_GUI": "1"}):
            res = browser_search(query="Python tutorials", url="https://docs.python.org")
            self.assertIsInstance(res, dict)
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("status"), "SUCCESS")
            self.assertEqual(res.get("website"), "docs.python.org")
            self.assertTrue(res.get("input_detected"))
            self.assertEqual(res.get("query_submitted"), "Python tutorials")
            self.assertTrue(res.get("verified"))
            self.assertIn("evidence", res)


if __name__ == "__main__":
    unittest.main()
