"""
Comparative Evaluation Framework for Base vs Fine-Tuned Local Models (Phase 2.2 Stage 6).
Evaluates the 2x2 matrix:
  1. Base Model Direct
  2. Base Model + Universal Brain
  3. Fine-Tuned Model Direct
  4. Fine-Tuned Model + Universal Brain
Enforces safe sequential model unloading to protect 8 GB local hardware bounds.
"""

import os
import sys
import gc
import json
import time
import psutil
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.universal_adapter import UniversalModelAdapter
from models.capability_profiler import ModelCapabilityProfiler
from core.universal_reasoning import UniversalReasoningOrchestrator
from benchmarks.phase2_eval import score_case


def evaluate_quadrant(
    cases: List[Dict[str, Any]],
    model_id: str,
    use_universal_brain: bool,
    adapter: UniversalModelAdapter,
    orchestrator: UniversalReasoningOrchestrator,
) -> Dict[str, Any]:
    mode_label = "Universal Brain" if use_universal_brain else "Direct"
    print(f"\n--- Evaluating Quadrant: {model_id} ({mode_label}) [{len(cases)} cases] ---", flush=True)

    results = []
    latencies = []
    peak_ram = 0.0

    for idx, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        if use_universal_brain:
            res = orchestrator.solve(prompt=c["input"], model_id=model_id)
            out = res.text
            path = res.execution_path
            dur_ms = (time.perf_counter() - t0) * 1000.0
            passed, reason = score_case(out, c["evaluation_criteria"])
        else:
            resp = adapter.generate(
                prompt=c["input"],
                system_prompt="Answer concisely and accurately.",
                model_id=model_id,
                temperature=0.1,
                num_predict=96,
                timeout=30.0,
            )
            out = resp.text.strip() if resp.success else f"ERROR: {resp.error}"
            path = "LLM_DIRECT"
            dur_ms = (time.perf_counter() - t0) * 1000.0
            passed, reason = score_case(out, c["evaluation_criteria"]) if resp.success else (False, resp.error or "error")

        ram_mb = psutil.virtual_memory().used / (1024 * 1024)
        peak_ram = max(peak_ram, ram_mb)

        if idx > 1:
            latencies.append(dur_ms)

        results.append({
            "id": c["id"],
            "category": c["category"],
            "passed": passed,
            "duration_ms": round(dur_ms, 1),
            "execution_path": path,
            "output": out[:100],
        })

    passed_cnt = sum(1 for r in results if r["passed"])
    acc = round((passed_cnt / len(results)) * 100.0, 1)
    avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    return {
        "model_id": model_id,
        "mode": mode_label,
        "total": len(results),
        "passed": passed_cnt,
        "accuracy_pct": acc,
        "avg_latency_ms": avg_lat,
        "peak_ram_mb": round(peak_ram, 1),
        "detailed_results": results,
    }


def run_comparative_matrix(
    dataset_path: str,
    base_model: str = "qwen3.5:2b-q4_K_M",
    finetuned_model: str = "qwen3.5-brain:v2",
    sample_size: int = 20,
) -> Dict[str, Any]:
    with open(dataset_path) as f:
        data = json.load(f)
    cases = data.get("cases", [])[:sample_size]

    adapter = UniversalModelAdapter()
    profiler = ModelCapabilityProfiler(adapter)
    orchestrator = UniversalReasoningOrchestrator(adapter=adapter, profiler=profiler)

    matrix = {}

    # 1. Base Model Direct
    matrix["1_base_direct"] = evaluate_quadrant(cases, base_model, False, adapter, orchestrator)
    adapter.unload_model(base_model)
    gc.collect()

    # 2. Base Model + Universal Brain
    matrix["2_base_universal"] = evaluate_quadrant(cases, base_model, True, adapter, orchestrator)
    adapter.unload_model(base_model)
    gc.collect()

    # 3. Fine-tuned Model Direct
    matrix["3_finetuned_direct"] = evaluate_quadrant(cases, finetuned_model, False, adapter, orchestrator)
    adapter.unload_model(finetuned_model)
    gc.collect()

    # 4. Fine-tuned Model + Universal Brain
    matrix["4_finetuned_universal"] = evaluate_quadrant(cases, finetuned_model, True, adapter, orchestrator)
    adapter.unload_model(finetuned_model)
    gc.collect()

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_model": base_model,
        "finetuned_model": finetuned_model,
        "dataset": dataset_path,
        "sample_size": sample_size,
        "matrix": matrix,
    }


if __name__ == "__main__":
    matrix_report = run_comparative_matrix("benchmarks/datasets/generalization_benchmark_v7.json", sample_size=15)
    print("\n=== 2x2 COMPARATIVE EVALUATION MATRIX ===")
    for q_key, q_res in matrix_report["matrix"].items():
        print(f"[{q_key}] {q_res['model_id']} ({q_res['mode']}): Accuracy={q_res['accuracy_pct']}%, AvgLat={q_res['avg_latency_ms']}ms, PeakRAM={q_res['peak_ram_mb']}MB")

    out_file = "benchmarks/reports/comparative_matrix_report.json"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(matrix_report, f, indent=2)
    print(f"Report saved to {out_file}")
