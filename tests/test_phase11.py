import os
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.identity import IdentityManager
from core.memory import MemoryStore, MemoryPolicy, MemoryRecord
from core.world_state import WorldStateManager, WorldState
from core.context import ContextBuilder
from tools.registry import default_registry
from tools.router import default_router


class TestPhase11Continuity(unittest.TestCase):
    """Test suite for Phase 11 Identity, Persistent Memory, World State, and Continuity."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_memory.db"
        self.identity_path = Path(self.temp_dir.name) / "test_identity.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- 1. IDENTITY SYSTEM TESTS ---

    def test_identity_defaults_and_load(self):
        mgr = IdentityManager(config_path=self.identity_path)
        self.assertEqual(mgr.name, "Brain")
        self.assertEqual(mgr.version, "11.0")
        self.assertIn("operating layer", mgr.persona.lower())
        snippet = mgr.get_identity_prompt_snippet()
        self.assertIn("Brain", snippet)
        self.assertIn("Communication Style", snippet)

    def test_identity_preference_updates(self):
        mgr = IdentityManager(config_path=self.identity_path)
        mgr.set_user_preference("favorite_editor", "nano", persist=True)
        self.assertEqual(mgr.get_user_preference("favorite_editor"), "nano")

        # Reload from disk and verify persistence
        mgr2 = IdentityManager(config_path=self.identity_path)
        self.assertEqual(mgr2.get_user_preference("favorite_editor"), "nano")

    # --- 2. MEMORY POLICY & QUALITY CONTROL TESTS ---

    def test_memory_policy_valid_remember(self):
        decision, err, rec = MemoryPolicy.evaluate("PREFERENCE", "user", "preferred_language", "Python")
        self.assertEqual(decision, "REMEMBER")
        self.assertIsNone(err)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.key, "preferred_language")
        self.assertEqual(rec.value, "Python")

    def test_memory_policy_reject_invalid_type(self):
        decision, err, rec = MemoryPolicy.evaluate("UNKNOWN_TYPE", "user", "key", "value")
        self.assertEqual(decision, "IGNORE")
        self.assertIn("Invalid memory type", err)

    def test_memory_policy_reject_sensitive_api_keys(self):
        # Groq key rejection
        dec1, err1, _ = MemoryPolicy.evaluate("FACT", "user", "api_key", "gsk_1234567890abcdefghijklmnopqrstuvwxyz")
        self.assertEqual(dec1, "IGNORE")
        self.assertIn("Privacy Policy Violation", err1)

        # Google Gemini key rejection
        dec2, err2, _ = MemoryPolicy.evaluate("FACT", "user", "token", "AIzaSyD1234567890abcdefghijklmnopqrstuvw")
        self.assertEqual(dec2, "IGNORE")
        self.assertIn("Privacy Policy Violation", err2)

        # Password rejection
        dec3, err3, _ = MemoryPolicy.evaluate("FACT", "user", "password", "password: supersecret123")
        self.assertEqual(dec3, "IGNORE")
        self.assertIn("Privacy Policy Violation", err3)

    def test_memory_policy_reject_command_injection(self):
        dec, err, _ = MemoryPolicy.evaluate("FACT", "user", "hack", "rm -rf /; sudo reboot")
        self.assertEqual(dec, "IGNORE")
        self.assertIn("Security Policy Violation", err)

    def test_memory_policy_temporary_context(self):
        dec, err, _ = MemoryPolicy.evaluate("CONTEXT", "user", "goal", "Open Brave just for now temporary")
        self.assertEqual(dec, "TEMPORARY")
        self.assertIn("temporary context", err)

    def test_memory_policy_length_limit(self):
        oversized = "a" * 501
        dec, err, _ = MemoryPolicy.evaluate("FACT", "user", "big_note", oversized)
        self.assertEqual(dec, "IGNORE")
        self.assertIn("exceeds maximum allowed length", err)

    # --- 3. PERSISTENT MEMORY STORE TESTS ---

    def test_memory_store_crud_and_dedup(self):
        store = MemoryStore(db_path=self.db_path)
        ok, err = store.add_memory("PREFERENCE", "user", "theme", "dark")
        self.assertTrue(ok)
        self.assertIsNone(err)

        rec = store.get_memory("PREFERENCE", "user", "theme")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.value, "dark")

        # Deduplication / Update test: update theme to "high-contrast"
        ok2, _ = store.add_memory("PREFERENCE", "user", "theme", "high-contrast")
        self.assertTrue(ok2)

        rec2 = store.get_memory("PREFERENCE", "user", "theme")
        self.assertEqual(rec2.value, "high-contrast")

        # Persistence across fresh connection test
        store.close()
        store2 = MemoryStore(db_path=self.db_path)
        rec3 = store2.get_memory("PREFERENCE", "user", "theme")
        self.assertEqual(rec3.value, "high-contrast")
        store2.close()

    def test_memory_store_search_relevance(self):
        store = MemoryStore(db_path=self.db_path)
        store.add_memory("PREFERENCE", "user", "preferred_editor", "Visual Studio Code")
        store.add_memory("PREFERENCE", "user", "preferred_browser", "Brave Browser")
        store.add_memory("FACT", "user", "favorite_language", "Python 3.12")

        matches = store.search_memories("browser", limit=3)
        self.assertTrue(len(matches) >= 1)
        self.assertEqual(matches[0].key, "preferred_browser")

        matches_py = store.search_memories("python programming", limit=3)
        self.assertTrue(len(matches_py) >= 1)
        self.assertEqual(matches_py[0].key, "favorite_language")
        store.close()

    def test_memory_store_task_events(self):
        store = MemoryStore(db_path=self.db_path)
        store.record_event("TASK", "List files in Brain", status="SUCCESS")
        store.record_event("PLAN", "Open Brave and search", status="COMPLETED")

        events = store.get_recent_events(limit=5)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "PLAN")
        self.assertEqual(events[1]["event_type"], "TASK")
        store.close()

    # --- 4. WORLD STATE TESTS ---

    def test_world_state_sync_and_staleness(self):
        mgr = WorldStateManager(staleness_threshold_seconds=1.0)
        state = mgr.sync_from_system()
        self.assertIsNotNone(state.os_name)
        self.assertEqual(state.observation_status, "KNOWN")

        # Check staleness detection after time passage
        time.sleep(1.1)
        self.assertEqual(mgr.check_staleness(), "STALE")

        # Resync restores KNOWN
        mgr.sync_from_system()
        self.assertEqual(mgr.check_staleness(), "KNOWN")

    def test_world_state_action_outcome_recording(self):
        mgr = WorldStateManager()
        mgr.record_action_outcome("OPEN_APP", {"app_name": "brave"}, {"success": True, "data": "Brave is open."}, verified=True)
        snip = mgr.get_state_prompt_snippet()
        self.assertIn("OPEN_APP", snip)
        self.assertIn("Brave is open", snip)

    # --- 5. CONTEXT BUILDER TESTS ---

    def test_context_builder_synthesis(self):
        store = MemoryStore(db_path=self.db_path)
        store.add_memory("PREFERENCE", "user", "favorite_tool", "ripgrep")
        id_mgr = IdentityManager(config_path=self.identity_path)
        ws_mgr = WorldStateManager()

        builder = ContextBuilder(identity_mgr=id_mgr, memory_store=store, world_state_mgr=ws_mgr)
        context = builder.build_system_context("Can you find something using my favorite_tool?")

        self.assertIn("Brain", context)
        self.assertIn("WORLD STATE", context)
        self.assertIn("RELEVANT MEMORIES:", context)
        self.assertIn("favorite_tool: ripgrep", context)
        store.close()

    # --- 6. TOOL REGISTRY & FASTROUTER INTEGRATION ---

    def test_remember_tool_registered(self):
        tool = default_registry.get("REMEMBER")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "REMEMBER")

        res = default_registry.execute("REMEMBER", {
            "memory_type": "PREFERENCE",
            "key": "test_pref",
            "value": "active"
        })
        self.assertTrue(res["success"])
        self.assertIn("Remembered preference", str(res["data"]))

    def test_fast_router_remember_routing(self):
        match = default_router.route("remember that my browser is Brave")
        self.assertIsNotNone(match)
        self.assertEqual(match["type"], "tool")
        self.assertEqual(match["tool"], "REMEMBER")
        self.assertEqual(match["arguments"]["key"], "my_browser")
        self.assertEqual(match["arguments"]["value"], "Brave")


if __name__ == "__main__":
    unittest.main()
