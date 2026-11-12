import time
import unittest
from core.memory import MemoryStore, MEMORY_CATEGORY_MAP


class TestMemoryIntelligence(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(db_path=":memory:")

    def tearDown(self):
        self.store.close()

    def test_five_memory_categories_supported(self):
        self.assertEqual(MEMORY_CATEGORY_MAP["FACT"], "LONG_TERM")
        self.assertEqual(MEMORY_CATEGORY_MAP["TASK"], "EPISODIC")
        self.assertEqual(MEMORY_CATEGORY_MAP["PROCEDURAL"], "PROCEDURAL")
        self.assertEqual(MEMORY_CATEGORY_MAP["FAILURE"], "FAILURE")
        self.assertEqual(MEMORY_CATEGORY_MAP["CONTEXT"], "SHORT_TERM")

        ok_proc, _ = self.store.record_procedural_workflow("check health", ["MEMORY_STATUS", "CPU_STATUS"])
        self.assertTrue(ok_proc)
        ok_fail, _ = self.store.record_failure_memory("timeout on search", "switch to foreground", tool_name="BROWSER_SEARCH")
        self.assertTrue(ok_fail)

        procs = self.store.list_memories(memory_type="PROCEDURAL")
        fails = self.store.list_memories(memory_type="FAILURE")
        self.assertEqual(len(procs), 1)
        self.assertEqual(len(fails), 1)

    def test_unverified_permanent_fact_rejected(self):
        ok, reason = self.store.add_memory("FACT", "user", "city", "UnknownGuess", verified=False)
        self.assertFalse(ok)
        self.assertIn("Unverified", reason)

    def test_conflict_detection_and_user_correction(self):
        ok1, _ = self.store.add_memory("PREFERENCE", "user", "preferred_browser", "Brave")
        self.assertTrue(ok1)

        # Conflict when allow_overwrite=False
        ok2, err2 = self.store.add_memory("PREFERENCE", "user", "preferred_browser", "Firefox", allow_overwrite=False)
        self.assertFalse(ok2)
        self.assertIn("Conflicting memory", err2)

        # User correction updates cleanly
        ok3, _ = self.store.correct_memory("PREFERENCE", "user", "preferred_browser", "Firefox")
        self.assertTrue(ok3)
        rec = self.store.get_memory("PREFERENCE", "user", "preferred_browser")
        self.assertEqual(rec.value, "Firefox")

    def test_relevance_ranking_and_no_irrelevant_injection(self):
        self.store.add_memory("FACT", "user", "os", "Linux Mint")
        self.store.add_memory("FACT", "user", "city", "Bangalore")
        self.store.add_memory("PREFERENCE", "user", "preferred_browser", "Brave")

        res = self.store.search_memories("What city do I live in?")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].key, "city")
        self.assertEqual(res[0].value, "Bangalore")

        # Completely unrelated query returns empty
        unrelated = self.store.search_memories("quantum physics neutrino mass")
        self.assertEqual(unrelated, [])

    def test_freshness_ttl_excludes_stale_memories(self):
        ok, _ = self.store.add_memory("FACT", "session", "temp_note", "old value", ttl_seconds=0.01)
        self.assertTrue(ok)
        time.sleep(0.03)
        res = self.store.search_memories("temp_note old value", exclude_stale=True)
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
