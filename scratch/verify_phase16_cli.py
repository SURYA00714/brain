import os
import sys
import time
from pathlib import Path

# Ensure Brain root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure mock GUI mode for headless test runs
os.environ["BRAIN_MOCK_GUI"] = "1"

from brain import run_planner_task
from core.telemetry import default_telemetry
from core.memory import default_memory

# Seed memory for "what is my name?"
default_memory.add_memory("FACT", "user", "my_name", "Jai", confidence=1.0)

PROMPTS = [
    ("hello", True),
    ("hi", True),
    ("what time is it?", True),
    ("open terminal", True),
    ("focus terminal", True),
    ("close terminal", True),
    ("open text editor", True),
    ("close text editor", True),
    ("open file manager", True),
    ("close file manager", True),
    ("open brave", True),
    ("close brave", True),
    ("what is on my screen right now?", True),
    ("tell me what you see", True),
    ("what app did we just open?", True),
    ("what was the last thing we talked about?", True),
    ("what is my name?", True),
    ("open fakeappthatdoesnotexist", True),
    ("delete all my files", True),
    ("wipe the disk", True),
    ("how does rm -rf work?", False), # Educational query: safe to explain
    ("open terminal and check free disk space", True),
    ("search Marvel and summarize what you find", True),
    ("why did my browser freeze?", False), # Diagnostic reasoning
    ("what happened on Mars today?", True), # Epistemic safety guard
]

def main():
    print("=" * 95)
    print("PHASE 16 LIVE BENCHMARK EVALUATION (25 MANDATORY PROMPTS)")
    print("=" * 95)
    print(f"{'#':<3} | {'Prompt':<42} | {'Time (ms)':<10} | {'LLM Calls':<10} | {'Provider':<10} | {'Deterministic OK?'}")
    print("-" * 95)

    failures = 0
    results = []

    for idx, (prompt, expect_zero_llm) in enumerate(PROMPTS, 1):
        t0 = time.perf_counter()
        res = run_planner_task(prompt, quiet=True)
        t_elapsed = (time.perf_counter() - t0) * 1000.0

        rec = default_telemetry.get_last()
        llm_calls = rec.llm_calls_this_request if rec else 0
        provider = (rec.llm_provider or "none") if rec else "none"

        is_zero_ok = (llm_calls == 0) if expect_zero_llm else True
        status_symbol = "PASS" if is_zero_ok else "FAIL"
        if not is_zero_ok:
            failures += 1

        print(f"{idx:<3} | {prompt:<42} | {t_elapsed:>8.2f}ms | {llm_calls:>9} | {provider:<10} | {status_symbol}")
        results.append({
            "idx": idx,
            "prompt": prompt,
            "time_ms": t_elapsed,
            "llm_calls": llm_calls,
            "provider": provider,
            "response": res[:80] + "..." if len(res) > 80 else res,
            "pass": is_zero_ok
        })

    print("=" * 95)
    print(f"Total evaluated: {len(PROMPTS)} | Deterministic compliance failures: {failures}")
    if failures == 0:
        print("ALL 25 PHASE 16 BENCHMARK PROMPTS PASSED STRICT TELEMETRY AUDIT!")
    else:
        print(f"WARNING: {failures} prompt(s) violated zero-LLM contract!")

if __name__ == "__main__":
    main()
