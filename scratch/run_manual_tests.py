import time
from brain import run_planner_task
from core.telemetry import default_telemetry

tests = [
    "Hello",
    "What is on my screen?",
    "Search the web for how to boil an egg",
    "rm -rf /",
    "Find python files in Brain"
]

print("=== Starting Manual Tests ===")
for test in tests:
    print(f"\n[Test Request]: {test}")
    start = time.perf_counter()
    try:
        ans = run_planner_task(test, quiet=True)
    except Exception as e:
        ans = f"ERROR: {e}"
    duration = time.perf_counter() - start
    print(f"[Response]: {ans}")
    tel = default_telemetry.get_last()
    if tel:
        print(f"[Metrics]: Provider={tel.llm_provider}, Duration={tel.total_ms:.1f}ms, LLM Calls={tel.llm_calls_this_request}, Fallback={tel.fallback_used}, Reasoning Required={tel.reasoning_required}")
    print(f"[Total Latency]: {duration*1000:.1f}ms")

print("\n=== Done ===")
