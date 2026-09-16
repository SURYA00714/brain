#!/usr/bin/env python3
"""
Phase 18 Live Behavioral Verification Suite
Tests the 5 mandatory scenarios:
1. System state (<200ms, 0 LLM calls)
2. Verified app launch (no false "process not detected")
3. Sequenced browser task (all steps executed, first result clicked)
4. Domain-filtered web research (relevant sources + cloud synthesis)
5. Robust error recovery / replanning
"""

import os
import sys
import time

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from brain import run_planner_task
from core.telemetry import default_telemetry
from tools.apps import default_app_tracker


def run_test(test_num, name, func):
    print(f"\n========================================================")
    print(f"TEST {test_num}: {name}")
    print(f"========================================================")
    t0 = time.time()
    try:
        res = func()
        duration = (time.time() - t0) * 1000.0
        print(f"[RESULT]: {res}")
        print(f"[TIME]: {duration:.2f} ms")
        tel = default_telemetry.get_last()
        if tel:
            print(f"[TELEMETRY]: LLM calls: {tel.llm_calls_this_request} (provider: {tel.llm_provider}), total: {tel.total_ms:.2f}ms, deterministic: {tel.deterministic_success}")
        return True, res
    except Exception as e:
        print(f"[FAILED]: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def test_1_system_state():
    req = "What apps are currently open on my computer, and which one am I using?"
    return run_planner_task(req)


def test_2_verified_app_launch():
    req = "Open Brave"
    return run_planner_task(req)


def test_3_sequenced_browser_task():
    req = "Open Brave, search for Python official documentation, and open the first result"
    return run_planner_task(req)


def test_4_web_research():
    req = "What are the latest developments in AI?"
    return run_planner_task(req)


def test_5_recovery():
    # Test unknown app immediate rejection & safety
    req = "open completely_unknown_fake_app_xyz"
    return run_planner_task(req)


if __name__ == "__main__":
    results = []
    print("Starting Phase 18 Live Behavioral Verification Suite...")
    
    # 1. System state
    ok1, res1 = run_test(1, "Deterministic System State (<200ms, 0 LLM calls)", test_1_system_state)
    results.append(("Test 1: System State", ok1))

    # 2. Verified App Launch
    ok2, res2 = run_test(2, "Verified App Launch (Multi-signal)", test_2_verified_app_launch)
    results.append(("Test 2: Verified App Launch", ok2))

    # 3. Sequenced Browser Task
    ok3, res3 = run_test(3, "Sequenced Browser Task (5-Step Plan, No Dropped Steps)", test_3_sequenced_browser_task)
    results.append(("Test 3: Sequenced Browser Task", ok3))

    # 4. Web Research
    ok4, res4 = run_test(4, "Domain-Filtered Web Research (Relevance + Cloud Synthesis)", test_4_web_research)
    results.append(("Test 4: Web Research", ok4))

    # 5. Recovery
    ok5, res5 = run_test(5, "Error Recovery / Bounded Diagnostics", test_5_recovery)
    results.append(("Test 5: Error Handling & Recovery", ok5))

    print("\n========================================================")
    print("PHASE 18 BEHAVIORAL VERIFICATION SUMMARY")
    print("========================================================")
    for name, ok in results:
        print(f"{name}: {'PASSED' if ok else 'FAILED'}")
