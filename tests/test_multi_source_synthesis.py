import unittest
from core.accuracy import AccuracyEngine

class TestMultiSourceSynthesis(unittest.TestCase):
    def test_synthesize_sources_with_agreement(self):
        docs = [
            {"source": "doc1.txt", "text": "Python 3.12 was released in October 2023. It introduces improved error messages."},
            {"source": "doc2.txt", "text": "Python 3.12 release date was October 2023 with performance enhancements."}
        ]
        res = AccuracyEngine.synthesize_multi_source("Python 3.12", docs)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["source_agreement"], 0.7)
        self.assertEqual(len(res["conflicts"]), 0)
        self.assertEqual(len(res["sources"]), 2)

    def test_synthesize_sources_with_conflict(self):
        docs = [
            {"source": "siteA.com", "text": "The event starts at 10 AM on Monday."},
            {"source": "siteB.com", "text": "The event starts at 2 PM on Monday."}
        ]
        res = AccuracyEngine.synthesize_multi_source("event start time", docs)
        self.assertTrue(res["success"])
        self.assertTrue(len(res["conflicts"]) > 0 or res["source_agreement"] < 1.0)

    def test_synthesize_empty_docs(self):
        res = AccuracyEngine.synthesize_multi_source("test", [])
        self.assertFalse(res["success"])
        self.assertEqual(res["findings"], [])

if __name__ == "__main__":
    unittest.main()
