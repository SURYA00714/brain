import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.gateway import default_gateway, ModelResponse
from core.telemetry import default_telemetry
from core.memory import default_memory
from brain import run_planner_task


def run_live_verification():
    print("=" * 75)
    print("PHASE 17.2 — REAL CLOUD BRAIN LIVE VERIFICATION")
    print("=" * 75)

    # 1. Provider Status
    status = default_gateway.get_cloud_status()
    print("\n[1] Cloud Provider Status Check:")
    print(status["report"])
    print("-" * 75)

    records = []

    def record_and_report(test_name, query, req_type="REASONING"):
        print(f"\n---> Running: '{query}' ({test_name})")
        t0 = time.perf_counter()
        ans = run_planner_task(query)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        tel = default_telemetry.get_last()
        rec = {
            "test": test_name,
            "query": query,
            "reasoning": tel.reasoning_required if tel else False,
            "provider": tel.llm_provider if tel else "NONE",
            "llm_calls": tel.llm_calls_this_request if tel else 0,
            "cloud_attempted": tel.cloud_attempted if tel else False,
            "fallback_used": tel.fallback_used if tel else False,
            "provenance": tel.provenance if tel else "STATIC",
            "latency_ms": elapsed_ms,
            "answer_preview": (ans[:140] + "...") if len(ans) > 140 else ans
        }
        records.append(rec)
        print(f"     Provider: {rec['provider']} | Calls: {rec['llm_calls']} | Cloud: {rec['cloud_attempted']} | Provenance: {rec['provenance']} | Latency: {rec['latency_ms']:.1f} ms")
        print(f"     Answer: {rec['answer_preview']}")
        return ans

    # 2. Real Cloud Reasoning (Groq)
    record_and_report("Reasoning 1 (Groq)", "explain why Python is popular")
    record_and_report("Reasoning 2 (Groq)", "compare Python and JavaScript for backend development")

    # 3. Search + Cloud Synthesis
    record_and_report("Search + Synthesis", "search Marvel and summarize what you find")
    record_and_report("Current Info (Mars)", "what happened on Mars today?")

    # 4. Deterministic Fast Paths (MUST be 0 LLM calls)
    record_and_report("Static Definition", "what is Python?", req_type="STATIC")
    default_memory.add_memory("FACT", "user", "name", "Jai")
    record_and_report("Memory Lookup", "what is my name?", req_type="MEMORY")
    record_and_report("Safety Guard 1", "rm -rf /", req_type="SAFETY")
    record_and_report("Safety Guard 2", "delete all my files", req_type="SAFETY")
    record_and_report("Educational rm -rf", "how does rm -rf work?", req_type="STATIC")

    # 5. Gemini Provider Verification (Deep tier)
    print("\n---> Running Gemini Deep Reasoning Test via ModelGateway (tier='DEEP'):")
    t0 = time.perf_counter()
    gemini_resp = default_gateway.generate("explain the difference between a process and a thread in 2 concise sentences", tier="DEEP")
    gemini_latency = (time.perf_counter() - t0) * 1000.0
    rec_gemini = {
        "test": "Gemini Deep Tier",
        "query": "explain the difference between a process and a thread",
        "reasoning": True,
        "provider": gemini_resp.provider,
        "llm_calls": 1 if gemini_resp.success else 0,
        "cloud_attempted": gemini_resp.cloud_attempted,
        "fallback_used": gemini_resp.fallback_used,
        "provenance": "MODEL",
        "latency_ms": gemini_latency,
        "answer_preview": gemini_resp.text[:140] + "..." if len(gemini_resp.text) > 140 else gemini_resp.text
    }
    records.append(rec_gemini)
    print(f"     Provider: {rec_gemini['provider']} | Calls: {rec_gemini['llm_calls']} | Cloud: {rec_gemini['cloud_attempted']} | Provenance: {rec_gemini['provenance']} | Latency: {rec_gemini['latency_ms']:.1f} ms")
    print(f"     Answer: {rec_gemini['answer_preview']}")

    # 6. Conversational Reasoning Follow-up
    print("\n---> Running Sequential Conversational Follow-up:")
    record_and_report("Conversation Turn 1", "compare Python and JavaScript for backend development")
    record_and_report("Conversation Turn 2", "which one would be simpler for a small API?")

    # 7. Print Comprehensive Summary Table
    print("\n" + "=" * 100)
    print("PHASE 17.2 COMPREHENSIVE TELEMETRY AUDIT TABLE")
    print("=" * 100)
    print(f"{'Test':<22} | {'Reasoning':<9} | {'Provider':<9} | {'Calls':<5} | {'Cloud':<6} | {'Provenance':<18} | {'Latency':<10}")
    print("-" * 100)
    for r in records:
        print(f"{r['test']:<22} | {str(r['reasoning']):<9} | {r['provider']:<9} | {r['llm_calls']:<5} | {str(r['cloud_attempted']):<6} | {r['provenance']:<18} | {r['latency_ms']:>7.1f} ms")
    print("=" * 100)


if __name__ == "__main__":
    run_live_verification()
