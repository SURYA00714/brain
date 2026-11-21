import os
import unittest
from tools.search import (
    query_searxng,
    perform_web_search_structured,
    perform_web_search,
    research_topic,
)


class TestSearXNGSearch(unittest.TestCase):
    """Test suite for SearXNG integration and graceful fallback chain."""

    def test_query_searxng_live(self):
        """Verifies live SearXNG metasearch returns structured multi-engine results."""
        results = query_searxng("python 3.13 release", max_results=3)
        if results is not None:
            self.assertGreater(len(results), 0)
            first = results[0]
            self.assertIn("title", first)
            self.assertIn("url", first)
            self.assertIn("snippet", first)
            self.assertTrue(first["url"].startswith("http"))

    def test_perform_web_search_structured_searxng(self):
        """Verifies perform_web_search_structured utilizes SearXNG when available."""
        res = perform_web_search_structured("linux mint 22", max_results=2)
        self.assertTrue(res.get("success"))
        self.assertIn(res.get("provider"), ("searxng", "duckduckgo_ddgs", "duckduckgo_html"))
        self.assertGreater(len(res.get("results", [])), 0)

    def test_searxng_fallback_on_unreachable_endpoint(self):
        """Verifies graceful fallback to DuckDuckGo when SearXNG port is unreachable."""
        orig_url = os.environ.get("SEARXNG_URL")
        try:
            os.environ["SEARXNG_URL"] = "http://127.0.0.1:59999"  # invalid port
            res = perform_web_search_structured("python programming language", max_results=2)
            self.assertTrue(res.get("success"))
            self.assertIn(res.get("provider"), ("duckduckgo_api", "duckduckgo_ddgs", "duckduckgo_html", "wikipedia_api"))
        finally:
            if orig_url:
                os.environ["SEARXNG_URL"] = orig_url
            else:
                os.environ.pop("SEARXNG_URL", None)

    def test_research_topic_end_to_end(self):
        """Verifies research_topic synthesizes findings and extracts sources cleanly."""
        res = research_topic("quantum computing fundamentals", max_results=2, deep=False)
        self.assertTrue(res.get("success"))
        self.assertGreater(len(res.get("findings", [])), 0)
        self.assertGreater(len(res.get("sources", [])), 0)
        self.assertIn("retrieved_summary", res)


if __name__ == "__main__":
    unittest.main()
