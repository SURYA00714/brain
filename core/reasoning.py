"""
Deep Reasoning Engine, Strategy Router, Multi-Pass Verifier, and Advanced Planner (Phase 1.9).
Prioritizes reasoning quality per second and per GB of RAM on 8 GB local hardware.
"""

import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.accuracy import AccuracyEngine
from core.constraints import extract_constraints_from_prompt, validate_constraints
from core.math_logic import detect_logical_contradictions, try_deterministic_math_or_logic
from models.gateway import ModelGateway, default_gateway


class ReasoningStrategy(Enum):
    DIRECT_RESPONSE = "DIRECT_RESPONSE"
    STEP_BY_STEP_SOLVING = "STEP_BY_STEP_SOLVING"
    DECOMPOSITION = "DECOMPOSITION"
    TOOL_ASSISTED_REASONING = "TOOL_ASSISTED_REASONING"
    EVIDENCE_BASED_REASONING = "EVIDENCE_BASED_REASONING"
    MEMORY_ASSISTED_REASONING = "MEMORY_ASSISTED_REASONING"
    CONSTRAINT_SOLVING = "CONSTRAINT_SOLVING"
    ALTERNATIVE_COMPARISON = "ALTERNATIVE_COMPARISON"
    UNCERTAINTY_ANALYSIS = "UNCERTAINTY_ANALYSIS"


def estimate_task_complexity(query: str) -> Tuple[str, int]:
    """
    Estimates task complexity (LOW | MEDIUM | HIGH) and adaptive token budget (num_predict).
    Avoids deep reasoning and oversized generation budgets for simple queries.
    """
    if not query:
        return "LOW", 128
    low = query.lower().strip()
    words = low.split()

    complex_markers = (
        "compare ", "tradeoff", "architecture", "step by step", "multi-step",
        "analyze", "algorithm", "contradiction", "if ", "suppose ", "prove ",
    )
    if len(words) > 25 or any(m in low for m in complex_markers) or low.count(" and ") >= 2:
        return "HIGH", 384
    if len(words) > 10 or any(k in low for k in ("why ", "how ", "explain ", "calculate ", "convert ")):
        return "MEDIUM", 256
    return "LOW", 128


def select_reasoning_strategy(
    query: str,
    has_memories: bool = False,
    requires_tools: bool = False,
    recent_turns: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Routes a query to the most appropriate reasoning strategy and adaptive token budget.
    """
    low = (query or "").lower().strip()
    complexity, num_predict = estimate_task_complexity(query)
    constraints = extract_constraints_from_prompt(query)

    # 1. Ambiguity / Uncertainty check
    if AccuracyEngine.detect_ambiguity(query, recent_turns=recent_turns):
        return {
            "strategy": ReasoningStrategy.UNCERTAINTY_ANALYSIS,
            "complexity": "LOW",
            "num_predict": 128,
            "needs_llm": False,
        }

    # 2. Evidence-based (live/external info)
    ext_need = AccuracyEngine.classify_external_info_need(query)
    if ext_need == "WEB":
        return {
            "strategy": ReasoningStrategy.EVIDENCE_BASED_REASONING,
            "complexity": complexity,
            "num_predict": num_predict,
            "needs_llm": False,
        }

    # 3. Tool-assisted reasoning
    if requires_tools or ext_need == "SYSTEM":
        return {
            "strategy": ReasoningStrategy.TOOL_ASSISTED_REASONING,
            "complexity": complexity,
            "num_predict": max(num_predict, 256),
            "needs_llm": True,
        }

    # 4. Memory-assisted reasoning
    if has_memories or ext_need == "MEMORY":
        return {
            "strategy": ReasoningStrategy.MEMORY_ASSISTED_REASONING,
            "complexity": complexity,
            "num_predict": num_predict,
            "needs_llm": True,
        }

    # 5. Strict constraint solving
    if constraints:
        return {
            "strategy": ReasoningStrategy.CONSTRAINT_SOLVING,
            "complexity": complexity,
            "num_predict": num_predict,
            "constraints": constraints,
            "needs_llm": True,
        }

    # 6. Alternative comparison
    if any(k in low for k in ("compare ", " vs ", "versus ", "better than", "tradeoff", "pros and cons")):
        return {
            "strategy": ReasoningStrategy.ALTERNATIVE_COMPARISON,
            "complexity": "HIGH",
            "num_predict": 320,
            "needs_llm": True,
        }

    # 7. Decomposition for multi-part problems
    if complexity == "HIGH" or low.count(" and ") >= 2 or ";" in low:
        return {
            "strategy": ReasoningStrategy.DECOMPOSITION,
            "complexity": "HIGH",
            "num_predict": 384,
            "needs_llm": True,
        }

    # 8. Step-by-step solving for medium math/logic
    if complexity == "MEDIUM" or any(k in low for k in ("premise", "calculate", "how many", "why ")):
        return {
            "strategy": ReasoningStrategy.STEP_BY_STEP_SOLVING,
            "complexity": complexity,
            "num_predict": 256,
            "needs_llm": True,
        }

    return {
        "strategy": ReasoningStrategy.DIRECT_RESPONSE,
        "complexity": "LOW",
        "num_predict": 128,
        "needs_llm": True,
    }


def verify_response_multipass(
    query: str,
    draft_answer: str,
    evidence: Optional[List[str]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lightweight deterministic verification of a draft response:
    1. Checks logical contradictions in sentences.
    2. Checks formatting/lexical constraints if present.
    3. Checks claims against provided evidence if present.
    4. Checks deterministic math if query is solvable deterministically.
    """
    issues: List[str] = []
    if not draft_answer or not draft_answer.strip():
        return {"verified": False, "issues": ["Empty response"], "confidence": 0.0}

    # 1. Contradiction check across sentences
    sentences = [s.strip() for s in re.split(r"[.\n]+", draft_answer) if s.strip()]
    contradictions = detect_logical_contradictions(sentences)
    if contradictions:
        issues.extend(contradictions)

    # 2. Constraint check
    if constraints:
        ok_c, c_errs = validate_constraints(draft_answer, constraints)
        if not ok_c:
            issues.extend(c_errs)

    # 3. Evidence grounding check
    if evidence:
        claim_res = AccuracyEngine.verify_claims(draft_answer, evidence)
        if not claim_res["grounded"] and claim_res["unverified_claims"]:
            issues.extend(claim_res["unverified_claims"])

    # 4. Deterministic math cross-check
    math_res = try_deterministic_math_or_logic(query)
    if math_res and math_res.get("solved"):
        expected = str(math_res["answer"]).split()[0]
        if expected not in draft_answer:
            issues.append(f"Deterministic math cross-check expected '{expected}' ({math_res['method']}).")

    return {
        "verified": len(issues) == 0,
        "issues": issues,
        "confidence": 1.0 if not issues else max(0.2, 1.0 - 0.3 * len(issues)),
    }


class DeepReasoningEngine:
    """
    Orchestrates deterministic fast paths, strategy routing, compact internal decomposition,
    and deterministic multi-pass verification.
    """

    def __init__(self, gateway: Optional[ModelGateway] = None):
        self.gateway = gateway or default_gateway
        self.last_trace: Optional[Dict[str, Any]] = None

    def solve(
        self,
        query: str,
        evidence: Optional[List[str]] = None,
        has_memories: bool = False,
        tier: str = "LOCAL",
    ) -> Dict[str, Any]:
        # 1. Deterministic math/logic fast path (<1ms, 0 LLM calls)
        det = try_deterministic_math_or_logic(query)
        if det and det.get("solved"):
            self.last_trace = {"strategy": "DETERMINISTIC_MATH_LOGIC", "model_calls": 0}
            return {
                "answer": det["answer"],
                "strategy": "DIRECT_RESPONSE",
                "method": det["method"],
                "verified": True,
                "model_calls": 0,
                "confidence": 1.0,
            }

        # 2. Contradiction check on input premises
        sentences = [s.strip() for s in re.split(r"[.\n]+", query) if s.strip()]
        in_contradictions = detect_logical_contradictions(sentences)

        route = select_reasoning_strategy(query, has_memories=has_memories)
        strategy: ReasoningStrategy = route["strategy"]
        num_predict = route["num_predict"]
        constraints = route.get("constraints")

        if strategy == ReasoningStrategy.UNCERTAINTY_ANALYSIS:
            clar = AccuracyEngine.detect_ambiguity(query)
            return {
                "answer": clar or "Please clarify your request.",
                "strategy": strategy.value,
                "verified": True,
                "model_calls": 0,
                "confidence": 1.0,
            }

        # 3. Compact prompt construction (never expose noisy internal chain-of-thought)
        ev_block = f"\nVerified Evidence:\n" + "\n".join(f"- {e}" for e in evidence[:3]) if evidence else ""
        contra_hint = (
            f"\nNote: Potential contradiction detected in input ({'; '.join(in_contradictions)}). Identify it clearly."
            if in_contradictions else ""
        )

        if strategy in (ReasoningStrategy.DECOMPOSITION, ReasoningStrategy.ALTERNATIVE_COMPARISON):
            prompt = (
                f"Solve concisely using compact reasoning.{ev_block}{contra_hint}\n"
                f"Problem: {query}\n"
                "Identify knowns, unknowns, solve each sub-part, and state ONLY the final verified answer clearly."
            )
        else:
            verify_clause = (
                "\nIf information is missing or cannot be verified, state that explicitly."
                if (evidence or AccuracyEngine.classify_external_info_need(query) in ("WEB", "SYSTEM"))
                else ""
            )
            prompt = (
                f"Answer accurately and concisely.{ev_block}{contra_hint}\n"
                f"Question: {query}{verify_clause}"
            )

        resp = self.gateway.generate(prompt=prompt, tier=tier, timeout=45.0, think=False, num_predict=num_predict)
        model_calls = 1
        if not resp.success or not resp.text:
            return {
                "answer": f"Unable to complete reasoning ({resp.error or 'model unavailable'}).",
                "strategy": strategy.value,
                "verified": False,
                "model_calls": model_calls,
                "confidence": 0.0,
            }

        draft = resp.text.strip()
        ver = verify_response_multipass(query, draft, evidence=evidence, constraints=constraints)

        # Bounded single repair pass ONLY if deterministic verification found fixable issues
        if not ver["verified"] and ver["issues"]:
            repair_prompt = (
                f"{prompt}\n\n"
                f"Draft answer had verification issues: {'; '.join(ver['issues'])}\n"
                "Fix these issues and output ONLY the corrected concise final answer."
            )
            resp2 = self.gateway.generate(prompt=repair_prompt, tier=tier, timeout=45.0, think=False, num_predict=num_predict)
            model_calls += 1
            if resp2.success and resp2.text:
                draft2 = resp2.text.strip()
                ver2 = verify_response_multipass(query, draft2, evidence=evidence, constraints=constraints)
                if ver2["confidence"] >= ver["confidence"]:
                    draft = draft2
                    ver = ver2

        self.last_trace = {"strategy": strategy.value, "model_calls": model_calls, "verification": ver}
        return {
            "answer": draft,
            "strategy": strategy.value,
            "verified": ver["verified"],
            "issues": ver["issues"],
            "model_calls": model_calls,
            "confidence": ver["confidence"],
        }


class AdvancedPlanner:
    """Evaluates and compares candidate planning strategies before execution."""

    @staticmethod
    def compare_strategies(goal: str, available_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        low = (goal or "").lower()
        tools_set = set(available_tools or [])
        candidates = []

        # Candidate A: Fast deterministic single-tool route
        if any(k in low for k in ("memory", "cpu", "disk", "time")) and " and " not in low:
            candidates.append({
                "name": "FAST_DETERMINISTIC",
                "preconditions": ["single_metric_query"],
                "resource_cost": "LOW",
                "failure_risk": 0.05,
                "estimated_steps": 1,
                "expected_outcome": "Sub-millisecond verified metric",
            })

        # Candidate B: Multi-step verified tool plan
        if any(k in low for k in ("open", "check", "create", "search", "screenshot", "file")):
            candidates.append({
                "name": "MULTI_STEP_VERIFIED_PLAN",
                "preconditions": ["registered_tools_available"],
                "resource_cost": "MEDIUM",
                "failure_risk": 0.15 if tools_set else 0.30,
                "estimated_steps": max(2, low.count(" and ") + 1),
                "expected_outcome": "Sequential tool execution with dependency verification",
            })

        # Candidate C: Web evidence + synthesis
        if any(k in low for k in ("search", "latest", "news", "find")):
            candidates.append({
                "name": "WEB_EVIDENCE_PLAN",
                "preconditions": ["network_available"],
                "resource_cost": "MEDIUM",
                "failure_risk": 0.25,
                "estimated_steps": 2,
                "expected_outcome": "Grounded web retrieval with relevance check",
            })

        if not candidates:
            candidates.append({
                "name": "STANDARD_PLANNING",
                "preconditions": [],
                "resource_cost": "MEDIUM",
                "failure_risk": 0.20,
                "estimated_steps": 2,
                "expected_outcome": "Structured plan validated against registry",
            })

        # Select lowest risk + lowest resource cost
        cost_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        best = min(candidates, key=lambda c: (c["failure_risk"], cost_rank.get(c["resource_cost"], 1), c["estimated_steps"]))
        return {"selected": best, "candidates": candidates}
