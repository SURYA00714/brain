import os
import sys
import time

# Ensure Brain root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["BRAIN_MOCK_GUI"] = "1"

from brain import run_planner_task
from tools.router import default_router

test_prompts = [
    ("1. Greeting", "hello"),
    ("2. Identity", "who are you"),
    ("3. Capabilities", "what can you do"),
    ("4. OS Info", "what operating system am i using"),
    ("5. Desktop Info", "what desktop am i using"),
    ("6. Running Apps", "what applications are running"),
    ("7. Preferred Browser", "what browser am i using"),
    ("8. Open App", "can you open brave"),
    ("9. Compound Search", "open brave and search marvel"),
    ("10. Compound Search & See", "open brave, search marvel, and tell me what you see"),
    ("11. Diagnostic / Reasoning", "my browser is crashing when i open tabs, what could be wrong?")
]

print("=" * 80)
print("BRAIN PHASE 13 REAL-WORLD INTERACTION VERIFICATION")
print("=" * 80)

results = []

for label, query in test_prompts:
    print(f"\n--- Running: [{label}] '{query}' ---")
    t0 = time.perf_counter()
    fast_match = default_router.route(query)
    route_time_ms = (time.perf_counter() - t0) * 1000.0

    t_exec_0 = time.perf_counter()
    # Execute planner task
    response = run_planner_task(query, quiet=True)
    total_time_ms = (time.perf_counter() - t_exec_0) * 1000.0

    route_type = "FAST_ROUTER" if fast_match else "COGNITIVE_MODEL"
    fast_detail = fast_match.get("type") if fast_match else "N/A"

    print(f"Router Match: {route_type} (type: {fast_detail}) in {route_time_ms:.2f}ms")
    print(f"Total Execution Time: {total_time_ms:.2f}ms")
    print(f"Response: {response[:160]}..." if len(response) > 160 else f"Response: {response}")

    results.append({
        "label": label,
        "query": query,
        "route_type": route_type,
        "detail": fast_detail,
        "total_ms": total_time_ms,
        "response": response
    })

print("\n" + "=" * 80)
print("PHASE 13 INTERACTION MATRIX SUMMARY")
print("=" * 80)
print(f"{'No. / Label':<28} | {'Route':<15} | {'Detail':<8} | {'Total ms':<10} | {'Status'}")
print("-" * 80)
for r in results:
    status = "OK" if r["response"] and "Brain Error" not in r["response"] else "FAIL"
    print(f"{r['label']:<28} | {r['route_type']:<15} | {r['detail']:<8} | {r['total_ms']:<10.2f} | {status}")
print("=" * 80)
