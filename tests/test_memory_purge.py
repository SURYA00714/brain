import unittest
from core.memory import MemoryStore

class TestMemoryPurge(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryStore(":memory:")

    def tearDown(self):
        self.mem.close()

    def test_purge_by_key(self):
        ok, _ = self.mem.add_memory("PREFERENCE", "user", "favorite_color", "blue", verified=True)
        self.assertTrue(ok)
        ok, _ = self.mem.add_memory("PREFERENCE", "user", "editor", "nvim", verified=True)
        self.assertTrue(ok)
        self.assertEqual(len(self.mem.list_memories()), 2)

        deleted = self.mem.purge_memory(key="favorite_color")
        self.assertEqual(deleted, 1)
        remaining = self.mem.list_memories()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].key, "editor")

    def test_purge_by_subject(self):
        ok, _ = self.mem.add_memory("TASK", "project_alpha", "deadline", "friday", verified=True)
        self.assertTrue(ok)
        ok, _ = self.mem.add_memory("TASK", "project_alpha", "status", "active", verified=True)
        self.assertTrue(ok)
        ok, _ = self.mem.add_memory("FACT", "user", "name", "John", verified=True)
        self.assertTrue(ok)

        deleted = self.mem.purge_memory(subject="project_alpha")
        self.assertEqual(deleted, 2)
        remaining = self.mem.list_memories()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].subject, "user")

if __name__ == "__main__":
    unittest.main()
