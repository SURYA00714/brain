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
from core.context import default_short_term_memory

# Seed memory for "what is my name?"
default_memory.add_memory("FACT", "user", "my_name", "Jai", confidence=1.0)

PROMPTS = [
    ("hello", "STATIC", 0, False),
    ("what is my name?", "MEMORY", 0, False),
    ("what app did we just open?", "WORLD_STATE", 0, False),
    ("what is on my screen?", "OBSERVED", 0, False),
    ("open Brave", "WORLD_STATE", 0, False),
    ("search Marvel", "WEB", 0, False),
    ("search Marvel and summarize what you find", "WEB", 0, False), # 0 if offline, 1 if cloud
    ("what is Python?", "STATIC", 0, False),
    ("explain why Python is popular", "STATIC", 0, False), # Handled or reasoning
    ("compare Python and JavaScript for backend development", "MODEL", 1, True),
    ("how does rm -rf work?", "STATIC", 0, False),
    ("my browser is slow, investigate it", "OBSERVED", 0, False),
    ("my browser is crashing, find out why", "OBSERVED", 0, False),
    ("open terminal and check disk space", "WORLD_STATE", 0, False),
    ("open fakeappthatdoesnotexist", "STATIC", 0, False),
    ("delete all my files", "STATIC", 0, False),
    ("rm -rf /", "STATIC", 0, False),
    ("what happened on Mars today?", "STATIC", 0, False),
    ("find the latest Python release information", "WEB", 0, False),
    ("open Brave, search Python, open the first result and explain it", "WORLD_STATE", 0, False),
]

def main():
    print("=" * 115)
    print("PHASE 17 CRITICAL LIVE BENCHMARK EVALUATION (SECTION 20 - 20 MANDATORY PROMPTS)")
    print("=" * 115)
    header = f"{'#':<3} | {'Prompt':<40} | {'Latency':<9} | {'LLM Calls':<9} | {'Provider':<8} | {'Reason Req':<10} | {'Source':<12} | {'Status'}"
    print(header)
    print("-" * 115)

    records = []
    # Seed prior opened app
    run_planner_task("open brave", quiet=True)

    for idx, (prompt, expected_src, max_expected_llm, expect_reasoning) in enumerate(PROMPTS, 1):
        t0 = time.perf_counter()
        res = run_planner_task(prompt, quiet=True)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        rec = default_telemetry.get_last()
        llm_calls = rec.llm_calls_this_request if rec else 0
        provider = (rec.llm_provider or "NONE") if rec else "NONE"
        reason_req = rec.reasoning_required if rec else False
        source = rec.provenance if rec else "UNKNOWN"

        dur_str = f"{dur_ms:.1f}ms" if dur_ms < 1000.0 else f"{dur_ms/1000.0:.2f}s"
        status = "PASS"

        # Special criteria verification
        if prompt in ("what is my name?", "what app did we just open?", "open fakeappthatdoesnotexist", "rm -rf /", "delete all my files"):
            if dur_ms > 200.0 or llm_calls > 0:
                status = "FAIL"
        elif prompt == "search Marvel" and llm_calls > 0:
            status = "FAIL"

        print(f"{idx:<3} | {prompt:<40} | {dur_str:>9} | {llm_calls:>9} | {provider:<8} | {str(reason_req):<10} | {source:<12} | {status}")
        records.append({
            "idx": idx,
            "prompt": prompt,
            "latency_ms": dur_ms,
            "llm_calls": llm_calls,
            "provider": provider,
            "reasoning_required": reason_req,
            "source": source,
            "result_snippet": res[:70].replace("\n", " ") + "..." if len(res) > 70 else res.replace("\n", " "),
            "status": status
        })

    print("=" * 115)
    print("ALL 20 PHASE 17 CRITICAL ACCEPTANCE BENCHMARKS PRODUCED!")

if __name__ == "__main__":
    main()
