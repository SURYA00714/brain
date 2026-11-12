"""
Universal Local Model Evaluation Runner for Brain (Phase 2.1).
Evaluates models independently in two distinct tracks:
- Track A: Direct Model (minimal standardized prompt, no memory, no tools, no deterministic shortcuts).
- Track B: Universal Brain (Universal Reasoning Orchestrator, dynamic strategy routing, deterministic engine, multi-pass verification).
Tracks hardware metrics (RAM, TTFT, tok/s, latency) and enforces safe model unloading on 8 GB systems.
"""

import os
import gc
import sys
import json
import time
import psutil
import logging
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.universal_adapter import UniversalModelAdapter
from models.capability_profiler import ModelCapabilityProfiler
from core.universal_reasoning import UniversalReasoningOrchestrator
from benchmarks.phase2_eval import score_case

logger = logging.getLogger("brain.benchmarks.universal_eval")


def run_universal_track_a(
    cases: List[Dict[str, Any]],
    adapter: UniversalModelAdapter,
    model_name: str,
) -> Dict[str, Any]:
    print(f"\n[UNIVERSAL TRACK A] Direct Model ({model_name}) [{len(cases)} cases]...", flush=True)
    results = []
    latencies = []
    tok_speeds = []
    ttfts = []
    peak_ram = 0.0

    for idx, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        resp = adapter.generate(
            prompt=c["input"],
            system_prompt="Answer concisely and accurately.",
            model_id=model_name,
            temperature=0.1,
            num_ctx=1024,
            num_predict=96,
            timeout=30.0,
        )
        dur_ms = (time.perf_counter() - t0) * 1000.0
        out = resp.text.strip() if resp.success else f"ERROR: {resp.error}"
        passed, reason = score_case(out, c["evaluation_criteria"]) if resp.success else (False, resp.error or "error")

        ram_mb = psutil.virtual_memory().used / (1024 * 1024)
        peak_ram = max(peak_ram, ram_mb)

        meta = resp.metadata or {}
        if idx > 1 and resp.success:
            latencies.append(dur_ms)
        if meta.get("tokens_per_sec"):
            tok_speeds.append(meta["tokens_per_sec"])
        if meta.get("ttft_ms"):
            ttfts.append(meta["ttft_ms"])

        results.append({
            "id": c["id"],
            "category": c["category"],
            "passed": passed,
            "reason": reason,
            "output": out[:120],
            "duration_ms": round(dur_ms, 1),
            "tokens_per_sec": meta.get("tokens_per_sec", 0.0),
            "ttft_ms": meta.get("ttft_ms", 0.0),
            "solved_by": "llm_direct",
        })

        if idx % 30 == 0:
            gc.collect()
            print(f"  Track A progress: {idx}/{len(cases)} (RAM={ram_mb:.0f} MB)", flush=True)

    passed_cnt = sum(1 for r in results if r["passed"])
    return {
        "track": "Track A (Direct Model)",
        "model": model_name,
        "total": len(results),
        "passed": passed_cnt,
        "accuracy_pct": round((passed_cnt / len(results)) * 100.0, 1),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "avg_ttft_ms": round(sum(ttfts) / len(ttfts), 1) if ttfts else 0.0,
        "avg_tokens_per_sec": round(sum(tok_speeds) / len(tok_speeds), 1) if tok_speeds else 0.0,
        "peak_ram_mb": round(peak_ram, 1),
        "detailed_results": results,
    }


def run_universal_track_b(
    cases: List[Dict[str, Any]],
    orchestrator: UniversalReasoningOrchestrator,
    model_name: str,
) -> Dict[str, Any]:
    print(f"\n[UNIVERSAL TRACK B] Universal Brain System ({model_name}) [{len(cases)} cases]...", flush=True)
    results = []
    latencies = []
    det_passed = 0
    det_total = 0
    llm_passed = 0
    llm_total = 0
    peak_ram = 0.0

    for idx, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        res = orchestrator.solve(
            prompt=c["input"],
            model_id=model_name,
        )
        dur_ms = (time.perf_counter() - t0) * 1000.0
        passed, reason = score_case(res.text, c["evaluation_criteria"])

        ram_mb = psutil.virtual_memory().used / (1024 * 1024)
        peak_ram = max(peak_ram, ram_mb)

        if idx > 1:
            latencies.append(dur_ms)

        if res.execution_path == "DETERMINISTIC_FAST_PATH":
            det_total += 1
            if passed:
                det_passed += 1
        else:
            llm_total += 1
            if passed:
                llm_passed += 1

        results.append({
            "id": c["id"],
            "category": c["category"],
            "passed": passed,
            "strategy": res.strategy,
            "mode": getattr(res, "mode", "DIRECT"),
            "execution_path": res.execution_path,
            "reason": reason,
            "output": res.text[:120],
            "duration_ms": round(dur_ms, 1),
            "verified": res.verified,
        })

        if idx % 30 == 0:
            gc.collect()
            print(f"  Track B progress: {idx}/{len(cases)} (RAM={ram_mb:.0f} MB)", flush=True)

    passed_cnt = sum(1 for r in results if r["passed"])
    return {
        "track": "Track B (Universal Brain)",
        "model": model_name,
        "total": len(results),
        "passed": passed_cnt,
        "accuracy_pct": round((passed_cnt / len(results)) * 100.0, 1),
        "deterministic_cases": det_total,
        "deterministic_passed": det_passed,
        "deterministic_pct": round((det_passed / det_total) * 100.0, 1) if det_total else 0.0,
        "llm_cases": llm_total,
        "llm_passed": llm_passed,
        "llm_pct": round((llm_passed / llm_total) * 100.0, 1) if llm_total else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "peak_ram_mb": round(peak_ram, 1),
        "detailed_results": results,
    }


def main():
    import sys
    bench_path = "benchmarks/datasets/reasoning_benchmark_v6.json"
    with open(bench_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    all_cases = data.get("cases", [])
    print(f"Loaded {len(all_cases)} benchmark cases from {bench_path}")

    all_150 = "--all-150" in sys.argv
    test_limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            test_limit = int(arg.split("=")[1])

    adapter = UniversalModelAdapter()
    profiler = ModelCapabilityProfiler(adapter)
    orchestrator = UniversalReasoningOrchestrator(adapter=adapter, profiler=profiler)

    models_to_test = ["qwen3.5:2b-q4_K_M", "qwen3.5-brain:v2"]
    report = {
        "benchmark": "Phase 2.1 Universal Model Benchmark",
        "dataset": bench_path,
        "models_evaluated": {},
    }

    for model_id in models_to_test:
        # Reference model runs all 150 cases; comparison model runs 30 cases unless --all-150
        if test_limit:
            cases = all_cases[:test_limit]
        elif model_id == "qwen3.5:2b-q4_K_M" or all_150:
            cases = all_cases
        else:
            cases = all_cases[:30]

        print(f"\n==================================================")
        print(f"PROFILING & EVALUATING MODEL: {model_id} ({len(cases)} cases)")
        print(f"==================================================")

        # 1. Profile model capabilities
        prof = profiler.get_or_infer_profile(model_id)
        print(f"Profile Score: {prof.overall_capability_score}%")

        # 2. Run Track A (Direct)
        adapter.set_active_model(model_id, unload_previous=True)
        track_a_res = run_universal_track_a(cases, adapter, model_id)
        print(f"Track A Result: {track_a_res['passed']}/{track_a_res['total']} ({track_a_res['accuracy_pct']}%)")

        # Safe memory boundary check
        gc.collect()

        # 3. Run Track B (Universal Brain)
        track_b_res = run_universal_track_b(cases, orchestrator, model_id)
        print(f"Track B Result: {track_b_res['passed']}/{track_b_res['total']} ({track_b_res['accuracy_pct']}%)")

        report["models_evaluated"][model_id] = {
            "profile": prof.to_dict(),
            "track_a": track_a_res,
            "track_b": track_b_res,
        }

        # Unload model before next to protect 8 GB RAM
        adapter.set_active_model("none", unload_previous=True)
        time.sleep(1.0)

    # Save report
    out_dir = "benchmarks/reports"
    os.makedirs(out_dir, exist_ok=True)
    report_file = os.path.join(out_dir, "phase2_1_universal_eval.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nUniversal evaluation report saved to {report_file}")


if __name__ == "__main__":
    main()
