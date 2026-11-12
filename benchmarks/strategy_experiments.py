"""
Strategy Effectiveness Experiments for Brain Phase 2.2.
Quantifies per-strategy accuracy, false rejection rate, latency overhead,
and model calls across reasoning tasks.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.universal_adapter import UniversalModelAdapter
from models.capability_profiler import ModelCapabilityProfiler
from core.universal_reasoning import UniversalReasoningOrchestrator, UniversalStrategy, ExecutionMode
from benchmarks.phase2_eval import score_case


def run_strategy_experiments(dataset_path: str, model_id: str = "qwen3.5:2b-q4_K_M") -> Dict[str, Any]:
    with open(dataset_path, "r") as f:
        data = json.load(f)
    cases = data.get("cases", [])

    adapter = UniversalModelAdapter()
    profiler = ModelCapabilityProfiler(adapter)
    orchestrator = UniversalReasoningOrchestrator(adapter=adapter, profiler=profiler)

    # Strategies to benchmark
    target_strategies = [
        UniversalStrategy.DIRECT_RESPONSE,
        UniversalStrategy.MATHEMATICAL_VERIFICATION,
        UniversalStrategy.CONSTRAINT_BASED_REASONING,
        UniversalStrategy.STEP_BY_STEP_DECOMPOSITION,
        UniversalStrategy.ALTERNATIVE_COMPARISON,
        UniversalStrategy.UNCERTAINTY_ANALYSIS,
    ]

    strategy_stats: Dict[str, Dict[str, Any]] = {
        strat.value: {
            "total_tested": 0,
            "passed": 0,
            "false_rejections": 0,
            "total_duration_ms": 0.0,
            "total_calls": 0,
        }
        for strat in target_strategies
    }

    # Evaluate dynamic selection across cases
    sample_cases = cases[:30]  # representative benchmark sample for bounded latency & memory
    print(f"\n[STRATEGY EXPERIMENT] Running across {len(sample_cases)} benchmark tasks on {model_id}...", flush=True)

    for idx, c in enumerate(sample_cases, 1):
        prompt = c["input"]
        criteria = c["evaluation_criteria"]

        # Run with dynamic orchestrator
        t0 = time.perf_counter()
        res = orchestrator.solve(prompt=prompt, model_id=model_id)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        passed, reason = score_case(res.text, criteria)

        strat_name = res.strategy
        if strat_name not in strategy_stats:
            strategy_stats[strat_name] = {
                "total_tested": 0,
                "passed": 0,
                "false_rejections": 0,
                "total_duration_ms": 0.0,
                "total_calls": 0,
            }

        s = strategy_stats[strat_name]
        s["total_tested"] += 1
        if passed:
            s["passed"] += 1
        else:
            # Check if false rejection (e.g. said cannot be verified or false contradiction)
            low_text = res.text.lower()
            if any(p in low_text for p in ("cannot be verified", "insufficient information", "not enough information", "contradiction detected")):
                s["false_rejections"] += 1

        s["total_duration_ms"] += dur_ms
        s["total_calls"] += 0 if res.execution_path == "DETERMINISTIC_FAST_PATH" else 1

        print(f"  [{idx}/{len(sample_cases)}] {c['id']} -> {res.strategy} ({res.mode}): {'PASS' if passed else 'FAIL'} in {dur_ms:.1f}ms", flush=True)

    summary: Dict[str, Any] = {}
    for strat, data in strategy_stats.items():
        if data["total_tested"] > 0:
            tot = data["total_tested"]
            acc = round((data["passed"] / tot) * 100.0, 1)
            fr_rate = round((data["false_rejections"] / tot) * 100.0, 1)
            avg_lat = round(data["total_duration_ms"] / tot, 1)
            avg_calls = round(data["total_calls"] / tot, 2)
            summary[strat] = {
                "tested": tot,
                "passed": data["passed"],
                "accuracy_pct": acc,
                "false_rejection_rate_pct": fr_rate,
                "avg_latency_ms": avg_lat,
                "avg_model_calls": avg_calls,
            }

    return {
        "model_id": model_id,
        "sample_size": len(sample_cases),
        "strategies": summary,
    }


if __name__ == "__main__":
    report = run_strategy_experiments("benchmarks/datasets/generalization_benchmark_v7.json")
    print("\n=== STRATEGY EFFECTIVENESS SUMMARY ===")
    print(json.dumps(report, indent=2))
    os.makedirs("benchmarks/reports", exist_ok=True)
    with open("benchmarks/reports/strategy_effectiveness_report.json", "w") as f:
        json.dump(report, f, indent=2)
