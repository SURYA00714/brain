"""
Phase 2.0 Dual-Track Evaluation & Model Comparison Runner.
- Track A: Unmodified Base Model (qwen3.5:2b-q4_K_M), NO deterministic tools/math/memory/verification.
- Track B: Brain System (Phase 2.0 Reasoning Engine + deterministic math/logic/contradiction/uncertainty).
- Model Comparison: Sequential 30-case comparison of qwen3.5:2b-q4_K_M vs qwen3.5-brain:2b-q4_K_M
  with explicit model unload between runs to avoid RAM thrashing on 8 GB hardware.
"""

import gc
import json
import os
import re
import sys
import time
import psutil
import requests
from datetime import datetime
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.gateway import OllamaProvider
from core.reasoning import DeepReasoningEngine
from core.math_logic import detect_logical_contradictions


def score_case(output: str, criteria: Dict[str, Any]) -> Tuple[bool, str]:
    if not output or not isinstance(output, str):
        return False, "Empty output"
    low = output.lower()
    for f_kw in criteria.get("forbidden", []):
        if f_kw.lower() in low:
            return False, f"Contained forbidden '{f_kw}'"
    for req in criteria.get("required_all", []):
        if req.lower() not in low:
            return False, f"Missing required '{req}'"
    req_any = criteria.get("required_any", [])
    if req_any:
        matched = any(r.lower() in low for r in req_any)
        if not matched:
            return False, f"Expected one of {req_any}, got '{output[:80]}'"
    return True, "Matched expected criteria"


def unload_ollama_model(model_name: str, base_url: str = "http://localhost:11434") -> None:
    try:
        requests.post(f"{base_url}/api/chat", json={"model": model_name, "messages": [], "keep_alive": 0}, timeout=5.0)
    except Exception:
        pass


def run_track_a(cases: List[Dict[str, Any]], model_name: str = "qwen3.5:2b-q4_K_M") -> Dict[str, Any]:
    print(f"\n=== TRACK A: BASE MODEL ({model_name}) [{len(cases)} cases] ===", flush=True)
    provider = OllamaProvider(model=model_name)
    results = []
    latencies = []
    ttfts = []
    tok_speeds = []
    peak_ram = 0.0

    for idx, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        resp = provider.generate(
            prompt=c["input"],
            system_prompt="Answer concisely and accurately.",
            timeout=30.0,
            think=False,
            num_ctx=1024,
            num_predict=96,
        )
        dur_ms = (time.perf_counter() - t0) * 1000.0
        out = resp.text.strip() if resp.success else f"ERROR: {resp.error}"
        passed, reason = score_case(out, c["evaluation_criteria"]) if resp.success else (False, resp.error or "error")
        ram_mb = psutil.virtual_memory().used / (1024 * 1024)
        peak_ram = max(peak_ram, ram_mb)
        meta = resp.metadata or {}
        if idx > 1:
            latencies.append(dur_ms)
        if meta.get("ttft_ms"):
            ttfts.append(meta["ttft_ms"])
        if meta.get("tokens_per_sec"):
            tok_speeds.append(meta["tokens_per_sec"])

        results.append({
            "id": c["id"],
            "category": c["category"],
            "passed": passed,
            "reason": reason,
            "output": out,
            "duration_ms": round(dur_ms, 2),
            "ttft_ms": meta.get("ttft_ms", 0.0),
            "tokens_per_sec": meta.get("tokens_per_sec", 0.0),
            "human_review_required": c.get("human_review_required", False),
            "solved_by": "llm",
        })
        if idx % 25 == 0:
            gc.collect()
            print(f"  Track A progress: {idx}/{len(cases)} (RAM={ram_mb:.0f} MB)", flush=True)
        time.sleep(0.02)

    passed_cnt = sum(1 for r in results if r["passed"])
    return {
        "track": "Track A (Base Model)",
        "model": model_name,
        "total": len(results),
        "passed": passed_cnt,
        "accuracy_pct": round((passed_cnt / len(results)) * 100.0, 1),
        "cold_start_ms": results[0]["duration_ms"] if results else 0.0,
        "avg_warm_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "avg_ttft_ms": round(sum(ttfts) / len(ttfts), 2) if ttfts else 0.0,
        "avg_tokens_per_sec": round(sum(tok_speeds) / len(tok_speeds), 2) if tok_speeds else 0.0,
        "peak_ram_mb": round(peak_ram, 1),
        "detailed_results": results,
    }


def run_track_b(cases: List[Dict[str, Any]], model_name: str = "qwen3.5:2b-q4_K_M") -> Dict[str, Any]:
    print(f"\n=== TRACK B: BRAIN SYSTEM ({model_name}) [{len(cases)} cases] ===", flush=True)
    eng = DeepReasoningEngine()
    results = []
    latencies = []
    det_count = 0
    llm_count = 0
    peak_ram = 0.0

    for idx, c in enumerate(cases, 1):
        t0 = time.perf_counter()
        solved_by = "llm"
        out = ""
        model_calls = 0

        # Contradiction detection fast path if formatted as Statement 1 / Statement 2
        if c["category"] == "Contradiction Detection" and "Statement 1:" in c["input"]:
            stmts = [s.strip() for s in re.findall(r"Statement \d+:\s*([^.]+)", c["input"])]
            contras = detect_logical_contradictions(stmts)
            out = f"Yes, contradiction detected: {'; '.join(contras)}" if contras else "No contradiction detected."
            solved_by = "deterministic_python"
            det_count += 1
        else:
            res = eng.solve(c["input"], tier="LOCAL")
            out = res.get("answer", "")
            model_calls = res.get("model_calls", 0)
            if model_calls == 0:
                solved_by = "deterministic_python"
                det_count += 1
            else:
                llm_count += 1

        dur_ms = (time.perf_counter() - t0) * 1000.0
        passed, reason = score_case(out, c["evaluation_criteria"])
        ram_mb = psutil.virtual_memory().used / (1024 * 1024)
        peak_ram = max(peak_ram, ram_mb)
        if idx > 1:
            latencies.append(dur_ms)

        results.append({
            "id": c["id"],
            "category": c["category"],
            "passed": passed,
            "reason": reason,
            "output": out,
            "duration_ms": round(dur_ms, 2),
            "model_calls": model_calls,
            "solved_by": solved_by,
            "human_review_required": c.get("human_review_required", False),
        })
        if idx % 25 == 0:
            gc.collect()
            print(f"  Track B progress: {idx}/{len(cases)} (RAM={ram_mb:.0f} MB)", flush=True)
        time.sleep(0.02)

    passed_cnt = sum(1 for r in results if r["passed"])
    det_passed = sum(1 for r in results if r["passed"] and r["solved_by"] == "deterministic_python")
    llm_passed = sum(1 for r in results if r["passed"] and r["solved_by"] == "llm")
    return {
        "track": "Track B (Brain System)",
        "model": model_name,
        "total": len(results),
        "passed": passed_cnt,
        "accuracy_pct": round((passed_cnt / len(results)) * 100.0, 1),
        "deterministic_cases": det_count,
        "deterministic_passed": det_passed,
        "llm_cases": llm_count,
        "llm_passed": llm_passed,
        "llm_only_accuracy_pct": round((llm_passed / llm_count) * 100.0, 1) if llm_count else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "peak_ram_mb": round(peak_ram, 1),
        "detailed_results": results,
    }


def main():
    with open("benchmarks/datasets/reasoning_benchmark_v6.json", "r", encoding="utf-8") as f:
        ds = json.load(f)
    cases = ds["cases"]

    track_a = run_track_a(cases, "qwen3.5:2b-q4_K_M")
    track_b = run_track_b(cases, "qwen3.5:2b-q4_K_M")

    # Stage 3: Controlled 30-case sequential comparison (2 per category)
    subset = []
    seen_cats: Dict[str, int] = {}
    for c in cases:
        cat = c["category"]
        if seen_cats.get(cat, 0) < 2:
            subset.append(c)
            seen_cats[cat] = seen_cats.get(cat, 0) + 1

    unload_ollama_model("qwen3.5:2b-q4_K_M")
    time.sleep(1.0)
    cmp_qwen_base = run_track_a(subset, "qwen3.5:2b-q4_K_M")
    unload_ollama_model("qwen3.5:2b-q4_K_M")
    time.sleep(1.0)
    cmp_qwen_brain = run_track_a(subset, "qwen3.5-brain:2b-q4_K_M")
    unload_ollama_model("qwen3.5-brain:2b-q4_K_M")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = f"benchmarks/reports/phase2_eval_raw_{ts}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "track_a": track_a,
            "track_b": track_b,
            "model_comparison_30_cases": {
                "qwen3.5:2b-q4_K_M": {k: v for k, v in cmp_qwen_base.items() if k != "detailed_results"},
                "qwen3.5-brain:2b-q4_K_M": {k: v for k, v in cmp_qwen_brain.items() if k != "detailed_results"},
            },
        }, f, indent=2)

    print(f"\nSaved Phase 2.0 raw evaluation to: {raw_path}")
    print(f"Track A (Base Model): {track_a['accuracy_pct']}% ({track_a['passed']}/{track_a['total']}) | {track_a['avg_tokens_per_sec']} tok/s | Peak RAM {track_a['peak_ram_mb']} MB")
    print(f"Track B (Brain System): {track_b['accuracy_pct']}% ({track_b['passed']}/{track_b['total']}) | Det: {track_b['deterministic_passed']}/{track_b['deterministic_cases']} | LLM-only: {track_b['llm_passed']}/{track_b['llm_cases']} ({track_b['llm_only_accuracy_pct']}%)")
    print(f"30-case Model Comparison: qwen3.5:2b={cmp_qwen_base['accuracy_pct']}% ({cmp_qwen_base['avg_tokens_per_sec']} tok/s) vs qwen3.5-brain:2b={cmp_qwen_brain['accuracy_pct']}% ({cmp_qwen_brain['avg_tokens_per_sec']} tok/s)")


if __name__ == "__main__":
    main()
