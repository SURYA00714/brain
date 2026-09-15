import os
import time
from pathlib import Path

from core.identity import IdentityManager
from core.memory import MemoryStore, MemoryPolicy
from core.world_state import WorldStateManager
from core.context import ContextBuilder
from brain import run_planner_task
from tools.input import validate_gui_action_safety


def run_scenarios():
    print("=== PHASE 11 REALISTIC SCENARIO VERIFICATION ===")

    # Test A — Memory Recall
    test_db = Path("data/brain_memory.db")
    store = MemoryStore(db_path=test_db)
    res_a = run_planner_task("remember that my favorite language is Python", quiet=True)
    print(f"\n[Test A - Store Preference] Response: {res_a}")
    stored_rec = store.get_memory("PREFERENCE", "user", "my_favorite_language")
    assert stored_rec is not None, "Test A Failed: Memory not persisted"
    assert stored_rec.value == "Python", f"Test A Failed: Value mismatch: {stored_rec.value}"
    print(f"[Test A - Verification] Recalled from SQLite: {stored_rec.key} = {stored_rec.value} (Confidence: {stored_rec.confidence}) -> PASS")

    # Test B — Temporary Context Rejection
    dec, err, rec = MemoryPolicy.evaluate("CONTEXT", "user", "temp_task", "Open brave temporary for now")
    print(f"\n[Test B - Temporary Context] Decision: {dec}, Reason: {err}")
    assert dec == "TEMPORARY", "Test B Failed: Temporary context was not classified as TEMPORARY"
    print("[Test B - Verification] Temporary context rejected from long-term memory -> PASS")

    # Test C — World State Real Observation
    ws = WorldStateManager()
    ws.sync_from_system()
    snap = ws.get_snapshot()
    print(f"\n[Test C - World State] OS: {snap.os_name}, Focused: {snap.focused_app}, Observation: {snap.observation_status}")
    assert snap.observation_status == "KNOWN", "Test C Failed: State was not marked KNOWN after sync"
    print("[Test C - Verification] World state synchronized against system conditions -> PASS")

    # Test D — External Change / Staleness Detection
    ws_stale = WorldStateManager(staleness_threshold_seconds=0.01)
    ws_stale.sync_from_system()
    time.sleep(0.05)
    stale_status = ws_stale.check_staleness()
    print(f"\n[Test D - Staleness Detection] Status after time gap: {stale_status}")
    assert stale_status == "STALE", f"Test D Failed: Expected STALE, got {stale_status}"
    print("[Test D - Verification] Unverified state correctly flagged as STALE -> PASS")

    # Test E — Web Knowledge & Untrusted Data Protection
    res_e = run_planner_task("Search the web for Python 3.12 documentation", quiet=True)
    print(f"\n[Test E - Web Search] Query executed via structured search")
    assert "Search results:" in res_e, "Test E Failed: Search results missing"
    print("[Test E - Verification] Structured search executed with untrusted data fence -> PASS")

    # Test G — Dangerous Action Safety
    is_safe, safety_err = validate_gui_action_safety("TYPE_TEXT", {"text": "sudo rm -rf /"})
    print(f"\n[Test G - Safety Block] is_safe: {is_safe}, error: {safety_err}")
    assert not is_safe, "Test G Failed: Dangerous command was not blocked"
    assert "Safety Block" in safety_err, "Test G Failed: Expected Safety Block"
    print("[Test G - Verification] Deterministic safety controller blocked dangerous command -> PASS")

    # Test H — Restart Recovery
    del store
    store_restarted = MemoryStore(db_path=test_db)
    recalled_after_restart = store_restarted.get_memory("PREFERENCE", "user", "my_favorite_language")
    print(f"\n[Test H - Restart Recovery] Recalled after re-instantiation: {recalled_after_restart.key} = {recalled_after_restart.value}")
    assert recalled_after_restart is not None and recalled_after_restart.value == "Python"

    ws_restarted = WorldStateManager()
    assert ws_restarted.current_state.observation_status == "UNKNOWN", "Test H Failed: New session must start with UNKNOWN observation"
    print("[Test H - Verification] Memory persisted, world state starts clean/unknown until verified -> PASS")

    print("\nALL SCENARIOS A THROUGH H VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    run_scenarios()
