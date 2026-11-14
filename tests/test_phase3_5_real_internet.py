import unittest
from unittest.mock import patch, MagicMock
from tools.search import (
    is_safe_web_url,
    read_web_page,
    research_topic,
    clean_url
)
from tools.registry import default_registry
from tools.router import default_router
from core.cognition import default_cognition, verify_step_execution
from tools.plan import ExecutionStep
from brain import _raw_run_planner_task


class TestPhase35RealInternet(unittest.TestCase):
    """Test suite for Phase 3.5 — Effective Real-Life Internet Access & Web Research Loop."""

    def test_01_ssrf_and_url_safety_validation(self):
        # Localhost and loopback
        safe, err = is_safe_web_url("http://localhost:8080/secret")
        self.assertFalse(safe)
        self.assertIn("Security Block", err)

        safe, err = is_safe_web_url("http://127.0.0.1/admin")
        self.assertFalse(safe)
        self.assertIn("Security Block", err)

        # Private RFC-1918 IPs
        safe, err = is_safe_web_url("http://192.168.1.100/router")
        self.assertFalse(safe)
        self.assertIn("Security Block", err)

        safe, err = is_safe_web_url("http://10.0.0.1/metadata")
        self.assertFalse(safe)
        self.assertIn("Security Block", err)

        # Invalid schemes
        safe, err = is_safe_web_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Only HTTP and HTTPS", err)

        # Valid public URL
        safe, err = is_safe_web_url("https://www.python.org/downloads/")
        self.assertTrue(safe)
        self.assertIsNone(err)

    def test_02_read_web_page_mocked(self):
        mock_html = """
        <html>
            <head><title>Test Article Page</title></head>
            <body>
                <nav><a href="/home">Home</a></nav>
                <article>
                    <h1>Python 3.12 Announced</h1>
                    <p>Python 3.12 introduces more flexible f-strings and improved error messages.</p>
                </article>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.iter_content.return_value = [mock_html]

        with patch("requests.get", return_value=mock_resp):
            res = read_web_page("https://news.example.com/python312")
            self.assertTrue(res["success"])
            self.assertEqual(res["title"], "Test Article Page")
            self.assertIn("Python 3.12 Announced", res["content"])
            self.assertIn("flexible f-strings", res["content"])
            # Nav and footer stripped
            self.assertNotIn("Copyright 2026", res["content"])

    def test_03_deep_research_loop(self):
        mock_search_results = {
            "success": True,
            "query": "Mars rover update",
            "results": [
                {"title": "Perseverance Update", "url": "https://nasa.gov/mars", "snippet": "Perseverance discovered organic molecules in Jezero crater."}
            ]
        }
        mock_page_html = "<html><head><title>NASA Mars</title></head><body><p>Perseverance rover gathered samples in the Jezero crater delta region.</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.iter_content.return_value = [mock_page_html]

        with patch("tools.search.perform_web_search_structured", return_value=mock_search_results), \
             patch("requests.get", return_value=mock_resp):
            res = research_topic("Mars rover update", max_results=2, deep=True)
            self.assertTrue(res["success"])
            self.assertTrue(len(res["findings"]) >= 1)
            self.assertIn("https://nasa.gov/mars", res["sources"])

    def test_04_registry_has_internet_tools(self):
        tool_read = default_registry.get("READ_WEB_PAGE")
        self.assertIsNotNone(tool_read)
        self.assertEqual(tool_read.parameters, {"url": "string"})

        tool_research = default_registry.get("DEEP_RESEARCH")
        self.assertIsNotNone(tool_research)
        self.assertEqual(tool_research.parameters, {"query": "string"})

    def test_05_router_direct_url_and_research(self):
        r1 = default_router.route("read page https://docs.python.org/3/whatsnew/3.12.html")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.get("type"), "tool")
        self.assertEqual(r1.get("tool"), "READ_WEB_PAGE")
        self.assertEqual(r1.get("arguments", {}).get("url"), "https://docs.python.org/3/whatsnew/3.12.html")

        r2 = default_router.route("deep research Python 3.12 performance")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.get("type"), "tool")
        self.assertEqual(r2.get("tool"), "DEEP_RESEARCH")
        self.assertEqual(r2.get("arguments", {}).get("query"), "python 3.12 performance")

    def test_06_verify_step_execution_for_web_tools(self):
        valid, status, detail = verify_step_execution(
            "READ_WEB_PAGE",
            {"url": "https://python.org"},
            {"success": True, "content": "Python is a programming language that lets you work quickly."}
        )
        self.assertTrue(valid)
        self.assertEqual(status, "VERIFIED")

        valid2, status2, detail2 = verify_step_execution(
            "DEEP_RESEARCH",
            {"query": "python"},
            {"success": True, "findings": ["Finding 1: Python 3.12 is fast."]}
        )
        self.assertTrue(valid2)
        self.assertEqual(status2, "VERIFIED")

    def test_07_real_time_queries_route_to_research(self):
        # Queries that need real-time freshness route to live web research
        intent = default_cognition.understand_intent("What is the latest news about Python 3.12?")
        self.assertEqual(intent.get("intent"), "RESEARCH")

        intent2 = default_cognition.understand_intent("latest Python release date")
        self.assertEqual(intent2.get("intent"), "RESEARCH")

    def test_08_internet_capability_inquiries(self):
        # Direct capability questions confirm live internet and web search capability
        ans1 = _raw_run_planner_task("do you have live internet acces", quiet=True)
        self.assertIn("live internet access", ans1)
        self.assertIn("WEB_SEARCH", ans1)

        ans2 = _raw_run_planner_task("can you web search", quiet=True)
        self.assertIn("live internet access", ans2)
        self.assertIn("WEB_SEARCH", ans2)

    def test_09_backend_read_vs_ui_open_separation(self):
        # 1. User says "go to youtube.com" -> UI navigation plan (open brave + navigate)
        ui_res = default_router.route("go to youtube.com")
        self.assertIsNotNone(ui_res)
        self.assertEqual(ui_res.get("type"), "plan")
        plan_steps = ui_res["plan"].steps
        tool_names = [s.tool_name for s in plan_steps if s.action_type == "tool"]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("BROWSER_NAVIGATE", tool_names)

        # 2. User says "READ_WEB_PAGE wikipedia" -> Backend tool READ_WEB_PAGE (headless)
        be_res1 = default_router.route("READ_WEB_PAGE wikipedia")
        self.assertIsNotNone(be_res1)
        self.assertEqual(be_res1.get("type"), "tool")
        self.assertEqual(be_res1.get("tool"), "READ_WEB_PAGE")
        self.assertEqual(be_res1.get("arguments", {}).get("url"), "https://www.wikipedia.org")

        # 3. User says "read wikipedia" -> Backend tool READ_WEB_PAGE
        be_res2 = default_router.route("read wikipedia")
        self.assertIsNotNone(be_res2)
        self.assertEqual(be_res2.get("type"), "tool")
        self.assertEqual(be_res2.get("tool"), "READ_WEB_PAGE")
        self.assertEqual(be_res2.get("arguments", {}).get("url"), "https://www.wikipedia.org")

        # 4. User says "read website github.com" -> Backend tool READ_WEB_PAGE
        be_res3 = default_router.route("read website github.com")
        self.assertIsNotNone(be_res3)
        self.assertEqual(be_res3.get("type"), "tool")
        self.assertEqual(be_res3.get("tool"), "READ_WEB_PAGE")
        self.assertEqual(be_res3.get("arguments", {}).get("url"), "https://github.com")



if __name__ == "__main__":
    unittest.main()
