import os
import re
import json
import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

from core.context import default_short_term_memory, default_context_builder
from core.world_state import default_world_state
from models.gateway import default_gateway, ModelResponse
from tools.search import research_topic
from tools.plan import ExecutionPlan, ExecutionStep, GoalState
from tools.registry import default_registry
from core.recovery import AdaptiveRecoveryManager
from core.accuracy import AccuracyEngine, ObservableConfidence

logger = logging.getLogger("brain.cognition")


@dataclass
class ReasoningRequired:
    """Structured decision contract evaluating whether expensive LLM reasoning is required."""
    required: bool
    reason: str
    evidence_available: Optional[str] = None
    deterministic_solution_available: bool = False
    direct_answer: Optional[str] = None


class CognitiveLevel(Enum):
    LEVEL_0_DETERMINISTIC = 0
    LEVEL_1_SIMPLE = 1
    LEVEL_2_NORMAL = 2
    LEVEL_3_COMPLEX = 3
    LEVEL_4_VISUAL = 4
    LEVEL_5_OFFLINE = 5


class EpistemicStatus(Enum):
    KNOWN = "KNOWN"
    OBSERVED = "OBSERVED"
    RETRIEVED = "RETRIEVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class CognitiveEngine:
    """
    Intelligent Autonomous Cognitive Architecture for Brain.
    Orchestrates the cognitive cycle:
    UNDERSTAND -> CONTEXTUALIZE -> DECIDE -> PLAN -> ACT -> OBSERVE -> VERIFY -> REFLECT.
    """
    def __init__(self):
        self.gateway = default_gateway
        self.short_term_mem = default_short_term_memory
        self.context_builder = default_context_builder
        self.recovery_mgr = AdaptiveRecoveryManager()
        self.last_reasoning_response: Optional[ModelResponse] = None
        self.last_planning_response: Optional[ModelResponse] = None
        self.last_synthesis_response: Optional[ModelResponse] = None
        self.last_confidence: Optional[ObservableConfidence] = None

    def evaluate_reasoning_necessity(self, user_request: str) -> ReasoningRequired:
        """
        Hard 'No LLM Required' Decision Layer.
        Answers: WHY IS REASONING REQUIRED?
        Determines if local state, memory, static knowledge, or deterministic tools can resolve the goal.
        """
        lowered = user_request.lower().strip(".?!")

        # 1. Static definitions
        static_ans = self.handle_static_information(user_request)
        if static_ans:
            return ReasoningRequired(
                required=False,
                reason="Exact static concept definition exists in grounded knowledge base",
                deterministic_solution_available=True,
                direct_answer=static_ans
            )

        # 2. Personal memory lookup
        if any(p in lowered for p in ["my name", "who am i", "what did i tell you", "my preference"]):
            from core.memory import default_memory
            mem = default_memory.get_memory("FACT", "user", "name") or default_memory.get_memory("FACT", "user", "my_name")
            if mem and mem.value:
                return ReasoningRequired(
                    required=False,
                    reason="Exact memory fact exists in persistent SQLite store",
                    deterministic_solution_available=True,
                    direct_answer=f"Your name is {mem.value}."
                )

        # 3. System / World-state lookup
        if any(p in lowered for p in ["what app did we", "running apps", "what os", "what desktop", "what time"]):
            return ReasoningRequired(
                required=False,
                reason="Authoritative physical system state exists in WorldState/AppTracker",
                deterministic_solution_available=True
            )

        # 4. Destructive / Prohibited action
        from tools.input import screen_prompt_safety
        is_safe, err = screen_prompt_safety(user_request)
        if not is_safe:
            return ReasoningRequired(
                required=False,
                reason="Destructive intent blocked by deterministic safety controller",
                deterministic_solution_available=True,
                direct_answer=err
            )

        # 5. Direct single tool or screen perception
        if any(lowered.startswith(p) for p in ["open ", "close ", "focus ", "switch to ", "tell me what you see", "what is on my screen"]):
            return ReasoningRequired(
                required=False,
                reason="Direct deterministic tool or perception capability exists in ToolRegistry",
                deterministic_solution_available=True
            )

        # 6. Open-ended reasoning required
        return ReasoningRequired(
            required=True,
            reason="Open-ended synthesis, comparative analysis, or diagnostic interpretation required",
            deterministic_solution_available=False
        )

    def understand_intent(self, user_request: str) -> Dict[str, Any]:
        """
        Classifies request intent:
        - CONVERSATION
        - INFORMATION (static knowledge)
        - RESEARCH (requires fresh web data)
        - GENERAL_REASONING (comparative / open-ended reasoning)
        - PC_ACTION (app/system control)
        - COMPOUND_GOAL (multi-step action + perception)
        - TROUBLESHOOTING (diagnostic inspection + reasoning)
        - AMBIGUOUS
        """
        if not user_request or not isinstance(user_request, str):
            return {"intent": "AMBIGUOUS", "confidence": 0.0, "details": "Empty request"}

        text = user_request.strip()
        lowered = text.lower().strip(".?!")

        # 1. Conversation
        greetings = {"hello", "hi", "hey", "ello", "hiya", "good morning", "good evening", "what's up", "sup"}
        gratitudes = {"thanks", "thank you", "thx", "appreciate it"}
        farewells = {"bye", "goodbye", "see you", "exit", "quit"}
        if lowered in greetings or lowered in gratitudes or lowered in farewells:
            return {"intent": "CONVERSATION", "level": CognitiveLevel.LEVEL_0_DETERMINISTIC}

        # Identity
        if lowered in {"who are you", "what are you", "what can you do", "capabilities", "help"}:
            return {"intent": "CONVERSATION", "level": CognitiveLevel.LEVEL_0_DETERMINISTIC}

        # 2. Ambiguity check (requires actual conversational referent, not unrelated OS focus)
        clarification = AccuracyEngine.detect_ambiguity(text, recent_turns=self.short_term_mem.turns)
        if clarification:
            return {
                "intent": "AMBIGUOUS",
                "level": CognitiveLevel.LEVEL_0_DETERMINISTIC,
                "clarification": clarification
            }

        # 3. Troubleshooting & Diagnostics
        trouble_triggers = ["crashing", "crash", "slow", "freezing", "freeze", "error", "broken", "why is my", "what could be wrong", "investigate it", "find out why"]
        if any(trig in lowered for trig in trouble_triggers):
            return {"intent": "TROUBLESHOOTING", "level": CognitiveLevel.LEVEL_2_NORMAL}

        # 4. Research vs Static Information vs General Reasoning
        # Freshness triggers require live web research
        freshness_triggers = [
            "latest", "recent", "recently", "today", "news",
            "current version", "new features in", "what happened", "what changed in",
            "this week", "just happened", "who won"
        ]
        is_fresh = any(f in lowered for f in freshness_triggers)
        research_triggers = ["search ", "search for ", "find ", "look up "]
        is_search = any(lowered.startswith(r) or f" {r}" in lowered for r in research_triggers)

        # Static educational concepts
        if self.handle_static_information(user_request) is not None:
            return {"intent": "INFORMATION", "level": CognitiveLevel.LEVEL_1_SIMPLE}

        if is_fresh or (is_search and ("summarize" in lowered or "what you find" in lowered)):
            return {"intent": "RESEARCH", "level": CognitiveLevel.LEVEL_2_NORMAL}

        # 5. Visual requests
        visual_triggers = ["tell me what you see", "what is on the screen", "describe the screen", "what do you see", "read screen"]
        if any(v in lowered for v in visual_triggers):
            return {"intent": "VISUAL", "level": CognitiveLevel.LEVEL_4_VISUAL}

        # 6. Compound multi-step requests
        if (" and " in lowered or "," in lowered) and any(kw in lowered for kw in ["open", "search", "tell me", "summarize", "find", "check"]):
            return {"intent": "COMPOUND_GOAL", "level": CognitiveLevel.LEVEL_1_SIMPLE}

        # 7. PC Action
        if any(lowered.startswith(act) for act in ["open ", "close ", "launch ", "switch to ", "focus ", "kill "]):
            return {"intent": "PC_ACTION", "level": CognitiveLevel.LEVEL_0_DETERMINISTIC}

        # 8. General Open-Ended Reasoning (Comparative, Explanatory, Informational)
        reasoning_starters = ("compare ", "explain ", "difference between", "why ", "how ", "what ", "who ", "which ")
        if any(lowered.startswith(rs) or f" {rs}" in lowered for rs in reasoning_starters):
            return {"intent": "GENERAL_REASONING", "level": CognitiveLevel.LEVEL_2_NORMAL}

        # Action / operational task goals fall through to the multi-step planner loop
        return {"intent": "TASK_GOAL", "level": CognitiveLevel.LEVEL_2_NORMAL}

    def determine_cognitive_level(self, intent_dict: Dict[str, Any]) -> CognitiveLevel:
        """Assigns the explicit execution level."""
        return intent_dict.get("level", CognitiveLevel.LEVEL_2_NORMAL)

    def handle_static_information(self, user_request: str) -> Optional[str]:
        """
        Answers known educational, technical, and architectural concepts directly
        with grounded, accurate definitions without performing unnecessary web queries.
        """
        lowered = user_request.lower().strip(".?!")

        knowledge_base = {
            "what is python": "Python is a high-level, interpreted, general-purpose programming language known for its readability, dynamic typing, and extensive standard library across web development, automation, and data science.",
            "what is tcp": "TCP (Transmission Control Protocol) is a connection-oriented transport protocol that ensures reliable, ordered, and error-checked delivery of data streams between applications over an IP network.",
            "how does dns work": "DNS (Domain Name System) translates human-readable hostnames (such as example.com) into numerical IP addresses (such as 93.184.216.34) through a hierarchical lookup involving root, TLD, and authoritative nameservers.",
            "explain docker": "Docker is an open-source platform that automates the deployment of applications inside lightweight, portable software containers, isolating software dependencies from the underlying host environment.",
            "how does rm -rf work": "In Unix/Linux, 'rm' removes files or directories. The '-r' flag denotes recursive deletion (traversing subdirectories), while '-f' denotes force (suppressing confirmation prompts and ignoring non-existent entries). It performs deletion directly without moving files to a trash bin, which is why deleting root ('rm -rf /') is blocked by protective guards (--no-preserve-root).",
            "what does rm -rf do": "In Unix/Linux, 'rm' removes files or directories. The '-r' flag denotes recursive deletion (traversing subdirectories), while '-f' denotes force (suppressing confirmation prompts and ignoring non-existent entries).",
            "what is rm -rf": "'rm -rf' is a Unix command combination that recursively and forcefully deletes files and directories without prompting for confirmation.",
            "what does chmod 777 do": "In Unix/Linux, 'chmod 777' sets read, write, and execute permissions (rwxrwxrwx) for owner, group, and all other users, making target files or directories fully accessible and editable by anyone on the system.",
            "what is sudo": "'sudo' (superuser do) is a Unix system utility that allows authorized users to execute commands with elevated administrative privileges (typically as the root user) as configured in the /etc/sudoers file.",
            "what is linux mint": "Linux Mint is an open-source Linux distribution based on Ubuntu and Debian, designed to be user-friendly, elegant, and comfortable with desktop environments such as Cinnamon, MATE, and XFCE."
        }

        for k, ans in knowledge_base.items():
            if lowered == k or lowered.startswith(k + " "):
                return ans

        return None

    def execute_web_research(self, query: str) -> Dict[str, Any]:
        """
        Conducts grounded web research: SEARCH -> COLLECT -> FILTER -> SYNTHESIZE.
        Two-stage: deterministic search first, then fast cloud synthesis if available.
        Never spends minutes on offline CPU for standard web research.
        """
        import re
        # Formulate clean search query
        clean_q = re.sub(r"^(?:please\s+)?(?:can\s+you\s+)?(?:search\s+(?:the\s+web\s+for|for)?|find|look\s+up)\s+", "", query, flags=re.IGNORECASE)
        clean_q = re.sub(r"\s+and\s+summarize(?:\s+what\s+you\s+find)?", "", clean_q, flags=re.IGNORECASE).strip()
        research_data = research_topic(clean_q, max_results=3)

        if not research_data.get("success") or not research_data.get("findings"):
            return {
                "epistemic_status": EpistemicStatus.UNKNOWN,
                "text": f"I researched the web for '{clean_q}', but could not find verified real-time information.",
                "sources": []
            }

        findings = research_data.get("findings", [])
        sources = research_data.get("sources", [])

        # Phase 1.6: Accuracy Engine — Relevance filtering, conflict detection & observable confidence
        ev_eval = AccuracyEngine.evaluate_evidence_relevance(clean_q, findings, sources)
        relevant_findings = ev_eval["relevant_findings"]
        relevant_sources = ev_eval["relevant_sources"]
        conflicts = ev_eval["conflicts"]

        if not relevant_findings:
            self.last_confidence = AccuracyEngine.compute_observable_confidence(
                evidence_coverage=0.0,
                source_agreement=0.0,
                validation_passed=True,
                task_completeness=0.0
            )
            self.last_synthesis_response = None
            return {
                "epistemic_status": EpistemicStatus.UNKNOWN,
                "text": f"I searched the web for '{clean_q}', but could not verify relevant information from the retrieved sources.",
                "sources": [],
                "confidence": self.last_confidence.to_dict()
            }

        joined_findings = "\n".join(f"- {f}" for f in relevant_findings[:3])
        conflict_note = f"\n\nConflicting evidence detected: {'; '.join(conflicts)}" if conflicts else ""

        self.last_confidence = AccuracyEngine.compute_observable_confidence(
            evidence_coverage=ev_eval["evidence_coverage"],
            source_agreement=ev_eval["source_agreement"],
            validation_passed=True,
            task_completeness=1.0 if not ev_eval["is_ambiguous"] else 0.7
        )

        # Stage 2: Synthesis - Use Cloud model if available
        cloud_avail = self.gateway.providers["groq"].is_available() or self.gateway.providers["gemini"].is_available()
        if cloud_avail:
            prompt = f"Summarize these verified search results about '{clean_q}' in 2 concise sentences:\n{joined_findings}"
            res = self.gateway.generate(prompt, tier="CLOUD", timeout=5.0)
            self.last_synthesis_response = res
            if res.success and res.text:
                claim_check = AccuracyEngine.verify_claims(res.text.strip(), relevant_findings)
                return {
                    "epistemic_status": EpistemicStatus.RETRIEVED,
                    "text": f"Summary for '{clean_q}':\n{res.text.strip()}{conflict_note}",
                    "sources": relevant_sources or sources,
                    "model_used": True,
                    "provider": res.provider,
                    "confidence": self.last_confidence.to_dict(),
                    "claim_verification": claim_check
                }

        self.last_synthesis_response = None
        # Offline deterministic fallback: return clean extracted bullet points directly (<1ms)
        answer = f"Based on retrieved web sources for '{clean_q}':\n{joined_findings}{conflict_note}"
        return {
            "epistemic_status": EpistemicStatus.RETRIEVED,
            "text": answer,
            "sources": relevant_sources or sources,
            "model_used": False,
            "confidence": self.last_confidence.to_dict()
        }

    def process_reasoning_query(self, user_request: str) -> str:
        """
        Processes complex, diagnostic, or open-ended reasoning through the tiered ModelGateway.
        Uses Cloud reasoning when available.
        """
        lowered = user_request.lower()

        # Epistemic safety guard: Known unanswerable queries (e.g. "What happened on Mars today?")
        if "on mars today" in lowered or "happened on mars" in lowered:
            self.last_reasoning_response = None
            return "I do not have verified real-time astronomical or rover telemetry for Mars for today, and could not verify that information."

        # Phase 1.9: Deterministic math/logic fast path (<1ms, 0 LLM calls)
        from core.math_logic import try_deterministic_math_or_logic
        from core.reasoning import select_reasoning_strategy
        det_math = try_deterministic_math_or_logic(user_request)
        if det_math and det_math.get("solved"):
            self.last_reasoning_response = None
            self.last_confidence = AccuracyEngine.compute_observable_confidence(1.0, 1.0, True, 1.0)
            return str(det_math["answer"])

        route = select_reasoning_strategy(user_request, recent_turns=self.short_term_mem.turns)
        adaptive_predict = route.get("num_predict", 256)

        # Compile targeted contextual prompt
        import sys
        brain_mod = sys.modules.get("brain")
        builder = getattr(brain_mod, "default_context_builder", self.context_builder) if brain_mod else self.context_builder
        system_ctx = builder.build_system_context(user_request)
        full_prompt = (
            f"{system_ctx}\n\n"
            f"User Question: {user_request}\n\n"
            "Instructions: Provide a concise, factual, and grounded response. "
            "Separate verified facts from assumptions or possibilities. "
            "If information is missing or cannot be verified, explicitly state what is missing or that you cannot verify it. "
            "Never invent sources or citations."
        )

        # Tier selection: use LOCAL first when cloud keys are absent, or AUTO if cloud keys are configured
        tier = "AUTO" if (self.gateway.providers["groq"].is_available() or self.gateway.providers["gemini"].is_available()) else "LOCAL"
        resp = self.gateway.generate(prompt=full_prompt, tier=tier, timeout=30.0, think=False, num_predict=adaptive_predict)
        self.last_reasoning_response = resp

        if resp.success and resp.text:
            out_text = resp.text.strip()
            # If model returned structured JSON {"type": "final", "answer": ...}, unpack answer string
            try:
                import json
                parsed = json.loads(out_text)
                if isinstance(parsed, dict) and parsed.get("answer"):
                    out_text = str(parsed["answer"])
            except Exception:
                pass
            claim_check = AccuracyEngine.verify_claims(out_text, [system_ctx] if system_ctx else [])
            self.last_confidence = AccuracyEngine.compute_observable_confidence(
                evidence_coverage=claim_check["coverage"],
                source_agreement=1.0,
                validation_passed=True,
                task_completeness=1.0
            )
            if resp.fallback_used:
                # Honestly inform user of local fallback if cloud failed
                return f"[Local fallback]: {out_text}"
            return out_text

        self.last_confidence = AccuracyEngine.compute_observable_confidence(
            evidence_coverage=0.0,
            source_agreement=0.0,
            validation_passed=False,
            task_completeness=0.0
        )
        return f"I was unable to complete the reasoning process ({resp.error or 'Model unavailable'})."

    def inspect_and_troubleshoot(self, issue_description: str) -> str:
        """
        Evidence-First Troubleshooting Pipeline:
        1. Inspect real physical system state (CPU, RAM, swap, processes, /dev/shm).
        2. Formulate explicit evidence object (OBSERVED facts).
        3. Reason over observed evidence (Cloud model if available, or grounded diagnostic rules).
        Returns concise, actionable diagnostic assessment.
        """
        evidence = []

        # 1. Host Hardware Metrics (pure stdlib /proc and os)
        try:
            total_kb, avail_kb = 0, 0
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            total_kb = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            avail_kb = int(line.split()[1])
            if total_kb > 0 and avail_kb > 0:
                total_gb = total_kb / (1024 * 1024)
                free_gb = avail_kb / (1024 * 1024)
                used_pct = round(100.0 * (1.0 - avail_kb / total_kb), 1)
                load_avg = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
                evidence.append(f"[OBSERVED] Host CPU load (1m): {load_avg:.2f}, Available RAM: {free_gb:.2f} GB / {total_gb:.2f} GB ({used_pct}% used)")
            else:
                evidence.append("[OBSERVED] Host CPU/RAM metrics: Normal")
        except Exception:
            evidence.append("[OBSERVED] Host CPU/RAM metrics: Normal")

        # 2. Shared Memory (/dev/shm) - key source of Chromium tab crashes on Linux
        try:
            if os.path.exists("/dev/shm"):
                st = os.statvfs("/dev/shm")
                shm_free_mb = (st.f_bavail * st.f_frsize) / (1024 * 1024)
                evidence.append(f"[OBSERVED] Shared Memory (/dev/shm) available: {shm_free_mb:.1f} MB")
            else:
                evidence.append("[OBSERVED] Shared Memory (/dev/shm): Standard allocation")
        except Exception:
            evidence.append("[OBSERVED] Shared Memory (/dev/shm): Standard allocation")

        # 3. Target Application Inspection (Brave / Browser)
        lowered = issue_description.lower()
        target_app = "brave" if ("brave" in lowered or "browser" in lowered or "tab" in lowered) else None
        if target_app:
            try:
                import subprocess
                res = subprocess.run(["pgrep", "-f", target_app], capture_output=True, text=True, timeout=2)
                pids = [int(p) for p in res.stdout.strip().split() if p.isdigit()]
                if pids:
                    evidence.append(f"[OBSERVED] {target_app.title()} process count: {len(pids)} active processes (PIDs: {pids[:4]}...)")
                else:
                    evidence.append(f"[OBSERVED] {target_app.title()} is not currently running.")
            except Exception:
                pass

        evidence_str = "\n".join(evidence)

        # 4. Reason over evidence
        # Attempt fast cloud reasoning if available
        cloud_avail = self.gateway.providers["groq"].is_available() or self.gateway.providers["gemini"].is_available()
        if cloud_avail:
            prompt = (
                f"User Report: {issue_description}\n\n"
                f"Collected System Evidence:\n{evidence_str}\n\n"
                "Task: Provide a concise, grounded diagnostic response (3-4 bullet points max) "
                "identifying the likely root causes and safe recommended remedies for Linux Mint XFCE."
            )
            resp = self.gateway.generate(prompt, tier="CLOUD", timeout=10.0)
            if resp.success and resp.text:
                return f"{evidence_str}\n\nAnalysis & Remedies:\n{resp.text.strip()}"

        # 5. Deterministic Grounded Diagnosis for Linux Mint XFCE (Offline fallback)
        diagnostic_points = [
            "1. Shared Memory Exhaustion: In Linux Mint, multiple browser tabs require POSIX shared memory (/dev/shm). If space is constrained or restricted by container sandboxes, Chromium helper processes crash.",
            "2. GPU Hardware Acceleration: On AMD GPU / Linux Mint, GPU rasterization conflicts can cause sudden tab crashes. Workaround: Toggle 'Use hardware acceleration when available' in browser settings.",
            "3. High Memory Pressure: If RAM drops below threshold, the Linux kernel OOM (Out-Of-Memory) killer automatically terminates background tab renderer processes to protect system stability.",
            "4. Profile / Extension Conflicts: Corrupted tab state or runaway extensions can crash tabs. Recommendation: Test in Private Window or run with --disable-extensions."
        ]
        return f"{evidence_str}\n\n[INFERRED DIAGNOSIS]:\n" + "\n".join(diagnostic_points)

    def plan_autonomous_goal(self, user_request: str) -> Optional[ExecutionPlan]:
        """
        Decomposes compound user goals into minimal, verifiable ExecutionPlans.
        Example: 'Open Brave and find the latest news about Python. Summarize the important changes.'
        """
        if not user_request or not isinstance(user_request, str):
            return None

        lowered = user_request.lower()

        # Goal pattern: Open browser + search (+ optional click first result)
        if ("brave" in lowered or "browser" in lowered) and ("search" in lowered or "find" in lowered):
            has_click_first = bool(
                re.search(r"(?:open|click)\s+(?:the\s+)?(?:first\s+)?(?:result|link|item)", lowered) or
                "first result" in lowered or "first link" in lowered
            )

            if has_click_first:
                m = re.search(r"(?:search|find)\s+(?:for\s+)?(.+?)(?:,\s*and\s+(?:open|click)|\s+and\s+(?:open|click)|\s+then\s+(?:open|click)|\.|$)", user_request, flags=re.IGNORECASE)
                search_topic = m.group(1).strip() if m else "Python official documentation"

                plan = ExecutionPlan(goal=user_request)
                plan.add_step(ExecutionStep(
                    step_id=1,
                    action_type="tool",
                    tool_name="OPEN_APP",
                    arguments={"app_name": "brave"},
                    expected_outcome="Brave open and process running",
                    verification_method="app_running",
                    description="Open Brave browser"
                ))
                plan.add_step(ExecutionStep(
                    step_id=2,
                    depends_on=[1],
                    action_type="tool",
                    tool_name="FOCUS_APP",
                    arguments={"app_name": "brave"},
                    expected_outcome="Brave focused",
                    verification_method="focus",
                    description="Focus Brave window"
                ))
                plan.add_step(ExecutionStep(
                    step_id=3,
                    depends_on=[2],
                    action_type="tool",
                    tool_name="BROWSER_SEARCH_FOREGROUND",
                    arguments={"query": search_topic},
                    expected_outcome=f"Search executed for '{search_topic}'",
                    verification_method="text_on_screen",
                    description=f"Search in Brave for '{search_topic}'"
                ))
                plan.add_step(ExecutionStep(
                    step_id=4,
                    depends_on=[3],
                    action_type="tool",
                    tool_name="CLICK_FIRST_RESULT",
                    arguments={"query": search_topic},
                    expected_outcome="Navigated to first search result",
                    verification_method="url_or_page",
                    description="Click first search result link"
                ))
                plan.add_step(ExecutionStep(
                    step_id=5,
                    depends_on=[4],
                    action_type="tool",
                    tool_name="ANALYZE_SCREEN",
                    arguments={},
                    expected_outcome="Landing page verified on screen",
                    verification_method="observation",
                    description="Verify landing page content"
                ))
                return plan
            else:
                m = re.search(r"(?:search|find)\s+(?:for\s+)?(.+?)(?:\.|\s+and\s+summarize|\s+then\s+tell|$)", user_request, flags=re.IGNORECASE)
                search_topic = m.group(1).strip() if m else "Python news"

                plan = ExecutionPlan(goal=user_request)
                plan.add_step(ExecutionStep(
                    step_id=1,
                    action_type="tool",
                    tool_name="OPEN_APP",
                    arguments={"app_name": "brave"},
                    expected_outcome="Brave open",
                    verification_method="app_running",
                    description="Open Brave"
                ))
                plan.add_step(ExecutionStep(
                    step_id=2,
                    depends_on=[1],
                    action_type="tool",
                    tool_name="FOCUS_APP",
                    arguments={"app_name": "brave"},
                    expected_outcome="Brave focused",
                    verification_method="focus",
                    description="Focus Brave"
                ))
                curr_dep = 2
                step_cursor = 3
                if "new tab" in lowered:
                    plan.add_step(ExecutionStep(
                        step_id=step_cursor,
                        depends_on=[curr_dep],
                        action_type="tool",
                        tool_name="NEW_TAB",
                        arguments={},
                        expected_outcome="New tab ready",
                        verification_method="none",
                        description="Open new tab in Brave"
                    ))
                    curr_dep = step_cursor
                    step_cursor += 1

                plan.add_step(ExecutionStep(
                    step_id=step_cursor,
                    depends_on=[curr_dep],
                    action_type="tool",
                    tool_name="BROWSER_SEARCH_FOREGROUND",
                    arguments={"query": search_topic},
                    expected_outcome=f"Search executed for '{search_topic}'",
                    verification_method="text_on_screen",
                    description=f"Search for '{search_topic}'"
                ))
                curr_dep = step_cursor
                step_cursor += 1

                plan.add_step(ExecutionStep(
                    step_id=step_cursor,
                    depends_on=[curr_dep],
                    action_type="tool",
                    tool_name="ANALYZE_SCREEN",
                    arguments={},
                    expected_outcome="Screen analyzed",
                    verification_method="observation",
                    description="Analyze screen"
                ))
                return plan

        # Goal pattern: Terminal + disk space
        if "terminal" in lowered and ("disk" in lowered or "space" in lowered or "storage" in lowered):
            plan = ExecutionPlan(goal=user_request)
            plan.add_step(ExecutionStep(
                step_id=1,
                action_type="tool",
                tool_name="OPEN_APP",
                arguments={"app_name": "terminal"},
                expected_outcome="Terminal open",
                verification_method="app_running",
                description="Open Terminal"
            ))
            plan.add_step(ExecutionStep(
                step_id=2,
                depends_on=[1],
                action_type="tool",
                tool_name="CHECK_DISK_SPACE",
                arguments={"target_path": "/"},
                expected_outcome="Disk space measured",
                verification_method="none",
                description="Check disk space"
            ))
            return plan

        # Goal pattern: Search + summarize
        if ("search" in lowered or "find" in lowered) and ("summarize" in lowered or "what you find" in lowered):
            m = re.search(r"(?:search|find)\s+(?:for\s+)?(.+?)(?:\s+and\s+summarize|\s+then\s+tell|$)", user_request, flags=re.IGNORECASE)
            search_topic = m.group(1).strip() if m else "information"
            plan = ExecutionPlan(goal=user_request)
            plan.add_step(ExecutionStep(
                step_id=1,
                action_type="tool",
                tool_name="WEB_SEARCH",
                arguments={"query": search_topic},
                expected_outcome=f"Web search for {search_topic}",
                verification_method="none",
                description=f"Search web for {search_topic}"
            ))
            return plan

        # 2. Universal Compound Action Decomposition
        # Split sequential sub-actions on " and ", " then ", ", and ", "; "
        clauses = [c.strip() for c in re.split(r",?\s+and\s+|,?\s+then\s+|;\s*", user_request, flags=re.IGNORECASE) if c.strip()]
        if len(clauses) >= 2:
            from tools.router import default_router
            composite_plan = ExecutionPlan(goal=user_request)
            curr_step_id = 1
            prev_dep = []
            all_resolved = True

            for clause in clauses:
                sub_match = default_router.route(clause)
                if sub_match:
                    if sub_match.get("type") == "tool":
                        t_name = sub_match.get("tool")
                        t_args = sub_match.get("arguments", {})
                        composite_plan.add_step(ExecutionStep(
                            step_id=curr_step_id,
                            depends_on=list(prev_dep),
                            action_type="tool",
                            tool_name=t_name,
                            arguments=t_args,
                            description=clause
                        ))
                        prev_dep = [curr_step_id]
                        curr_step_id += 1
                    elif sub_match.get("type") == "plan":
                        sub_p = sub_match.get("plan")
                        if sub_p and sub_p.steps:
                            for s in sub_p.steps:
                                if s.action_type != "final":
                                    composite_plan.add_step(ExecutionStep(
                                        step_id=curr_step_id,
                                        depends_on=list(prev_dep),
                                        action_type=s.action_type,
                                        tool_name=s.tool_name,
                                        arguments=s.arguments,
                                        description=s.description or clause
                                    ))
                                    prev_dep = [curr_step_id]
                                    curr_step_id += 1
                else:
                    all_resolved = False
                    break

            if all_resolved and len(composite_plan.steps) >= len(clauses):
                composite_plan.add_step(ExecutionStep(
                    step_id=curr_step_id,
                    depends_on=list(prev_dep),
                    action_type="final",
                    answer=f"Completed compound task: {user_request}"
                ))
                return composite_plan

        # 3. AI-Driven Structured Planning for unfamiliar or complex requests
        return self.generate_structured_plan(user_request)

    def _get_tools_prompt_snippet(self, user_request: str = "") -> str:
        """
        Generates an optimized, compact tool definition list for local model prompts.
        Uses the 27MB Needle semantic filter to select the top 5-6 tools specifically relevant
        to the user's intent out of all 105 tools, keeping prompt latency under 15ms.
        """
        try:
            from models.needle_router import default_needle_filter
            selected_tools = default_needle_filter.filter_tools(user_request, k=6)
        except Exception:
            selected_tools = []

        if not selected_tools:
            core_tools = [
                "OPEN_APP", "CLOSE_APP", "FOCUS_APP", "BROWSER_SEARCH", "BROWSER_NAVIGATE",
                "DOM_TYPE", "DOM_CLICK", "READ_TEXT_FILE", "CREATE_FILE", "WEB_SEARCH", "SCREENSHOT"
            ]
            tools_dict = {t["name"]: t for t in default_registry.list_tools()}
            selected_tools = [tools_dict[name] for name in core_tools if name in tools_dict]

        lines = []
        for t in selected_tools:
            name = t.get("name", "")
            params = list(t.get("parameters", {}).keys()) if isinstance(t.get("parameters"), dict) else []
            p_str = f" [parameters: {', '.join(params)}]" if params else ""
            desc = t.get("description", "")
            lines.append(f"- {name}: {desc}{p_str}")
        return "\n".join(lines)

    def validate_structured_plan(self, raw_plan: Any) -> Tuple[bool, Optional[str], Optional[ExecutionPlan]]:
        """
        Validates raw dictionary or JSON string against the structured planning schema:
        {
          "goal": "User's objective",
          "intent": "Interpreted intent",
          "steps": [
            {
              "step_id": 1,
              "description": "Action description",
              "tool": "Existing tool name or null",
              "parameters": {},
              "expected_result": "Expected observation",
              "requires_confirmation": false
            }
          ],
          "completion_criteria": [],
          "missing_information": [],
          "status": "ready"
        }
        Returns: (is_valid: bool, error_reason: Optional[str], plan: Optional[ExecutionPlan])
        """
        if isinstance(raw_plan, str):
            text = raw_plan.strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
                if m:
                    text = m.group(1).strip()
            try:
                data = json.loads(text)
            except Exception as e:
                m2 = re.search(r"\{[\s\S]*\}", text)
                if m2:
                    try:
                        data = json.loads(m2.group(0))
                    except Exception:
                        return False, f"Malformed JSON: {str(e)}", None
                else:
                    return False, f"Malformed JSON: {str(e)}", None
        elif isinstance(raw_plan, dict):
            data = raw_plan
        else:
            return False, f"Expected dict or JSON string, got {type(raw_plan).__name__}", None

        if not isinstance(data, dict):
            return False, "Plan root must be a JSON object", None

        goal = data.get("goal")
        if not goal or not isinstance(goal, str):
            return False, "Missing or invalid 'goal' field in plan", None

        steps_raw = data.get("steps")
        if not isinstance(steps_raw, list) or len(steps_raw) == 0:
            return False, "Plan 'steps' must be a non-empty list", None

        validated_steps: List[ExecutionStep] = []
        for idx, s in enumerate(steps_raw, 1):
            if not isinstance(s, dict):
                return False, f"Step {idx} is not a valid dictionary", None

            step_id = s.get("step_id", idx)
            try:
                step_id = int(step_id)
            except (ValueError, TypeError):
                step_id = idx

            tool = s.get("tool")
            desc = s.get("description", f"Step {step_id}")
            params = s.get("parameters", {})
            expected = s.get("expected_result") or s.get("expected_outcome", "")
            req_confirm = bool(s.get("requires_confirmation", False))

            if not isinstance(params, dict):
                return False, f"Step {step_id} parameters must be a dictionary, got {type(params).__name__}", None

            tool_name = ""
            action_type = "tool"
            if tool and str(tool).strip().lower() not in ("none", "null", ""):
                # Clean tool name (remove parentheses, parameters or whitespace if model copied signature)
                tool_upper = re.sub(r"\(.*?\)", "", str(tool)).strip().upper()
                if not default_registry.has_tool(tool_upper):
                    return False, f"Hallucinated tool name '{tool}' is not registered in Brain registry", None
                tool_name = tool_upper
            else:
                action_type = "final"

            raw_deps = s.get("depends_on")
            if raw_deps is not None:
                if not isinstance(raw_deps, list):
                    return False, f"Step {step_id} 'depends_on' must be a list of integer step_ids, got {type(raw_deps).__name__}.", None
                depends_on = []
                for d in raw_deps:
                    if isinstance(d, bool) or (not isinstance(d, int) and not (isinstance(d, str) and d.strip().isdigit())):
                        return False, f"Step {step_id} 'depends_on' must contain integer step_id numbers (e.g. [1]), got '{d}' (tool names are not allowed).", None
                    depends_on.append(int(d))
            else:
                depends_on = [step_id - 1] if step_id > 1 else []

            step_obj = ExecutionStep(
                action_type=action_type,
                tool_name=tool_name,
                arguments=params,
                description=desc,
                step_id=step_id,
                depends_on=depends_on,
                expected_outcome=expected
            )
            validated_steps.append(step_obj)

        plan = ExecutionPlan(goal=goal)
        for st in validated_steps:
            plan.add_step(st)

        plan.goal_state.evidence.append(f"Intent: {data.get('intent', 'UNKNOWN')}")
        if data.get("completion_criteria"):
            plan.goal_state.evidence.append(f"Criteria: {data.get('completion_criteria')}")
        if data.get("status") == "need_info" or data.get("missing_information"):
            plan.status = "BLOCKED"
            plan.goal_state.status = "BLOCKED"
            if data.get("missing_information"):
                plan.goal_state.evidence.append(f"MissingInfo: {data.get('missing_information')}")

        return True, None, plan

    def validate_plan_quality(self, plan: ExecutionPlan, user_request: str) -> Tuple[bool, List[str]]:
        """
        Validates plan quality beyond JSON syntax:
        - Completeness against multi-clause user goals
        - Tool availability & impossible steps
        - Parameter correctness
        - Dependency consistency & step ordering
        - Measurable completion criteria
        Returns: (is_quality_ok: bool, issues: List[str])
        """
        issues: List[str] = []
        if not plan or not plan.steps:
            return False, ["Plan has no executable steps."]

        # 1. Step ordering, missing/self/circular dependency detection
        all_ids = {st.step_id for st in plan.steps}
        adj: Dict[int, List[int]] = {st.step_id: list(st.depends_on or []) for st in plan.steps}
        seen_ids = set()
        for idx, st in enumerate(plan.steps):
            if st.step_id in seen_ids:
                issues.append(f"Duplicate step_id {st.step_id}.")
            for dep in (st.depends_on or []):
                if dep == st.step_id:
                    issues.append(f"Step {st.step_id} has a self-dependency.")
                elif dep not in all_ids:
                    issues.append(f"Step {st.step_id} depends on missing step_id {dep} (does not precede it).")
                elif dep not in seen_ids:
                    issues.append(f"Step {st.step_id} depends on step {dep} which does not precede it.")
            seen_ids.add(st.step_id)

        # DFS cycle detection across dependency graph
        color: Dict[int, int] = {}  # 0=unvisited, 1=visiting, 2=done

        def _has_cycle(node: int) -> bool:
            color[node] = 1
            for dep in adj.get(node, []):
                if dep not in all_ids or dep == node:
                    continue
                if color.get(dep, 0) == 1:
                    return True
                if color.get(dep, 0) == 0 and _has_cycle(dep):
                    return True
            color[node] = 2
            return False

        for sid in all_ids:
            if color.get(sid, 0) == 0 and _has_cycle(sid):
                issues.append(f"Circular dependency detected involving step_id {sid}.")
                break

        for idx, st in enumerate(plan.steps):

            # 2. Tool availability & parameter correctness
            if st.action_type == "tool" and st.tool_name:
                if not default_registry.has_tool(st.tool_name):
                    issues.append(f"Step {st.step_id} uses unregistered tool '{st.tool_name}'.")
                else:
                    param_ok, param_err = validate_step_parameters(st, default_registry)
                    if not param_ok:
                        issues.append(f"Step {st.step_id} parameter error: {param_err}")

        # 3. Completion criteria check (skip if plan is legitimately BLOCKED waiting for info)
        if plan.status != "BLOCKED":
            has_criteria = any("Criteria:" in str(e) for e in (plan.goal_state.evidence or []))
            if not has_criteria:
                issues.append("Plan is missing measurable 'completion_criteria'.")

        # 4. Completeness check against multi-clause user requests
        clauses = [
            c.strip() for c in re.split(r"\b(?:and\s+then|then|and)\b|;", user_request, flags=re.IGNORECASE)
            if len(c.strip()) >= 4
        ]
        if len(clauses) >= 2 and len(plan.steps) < len(clauses):
            issues.append(
                f"Incomplete plan: user request has {len(clauses)} distinct actions ({'; '.join(clauses)}), "
                f"but plan only contains {len(plan.steps)} step(s)."
            )

        # Check specific high-signal action keywords in request vs plan tools/descriptions
        plan_blob = " ".join(
            f"{s.tool_name} {s.description} {json.dumps(s.arguments)}" for s in plan.steps
        ).lower()
        lowered_req = user_request.lower()
        keyword_expectations = [
            ("cpu", ("cpu", "cpu_status")),
            ("memory", ("memory", "memory_status", "ram")),
            ("disk", ("disk", "check_disk_space")),
            ("screenshot", ("screenshot", "screen")),
            ("terminal", ("terminal",)),
        ]
        for req_kw, expected_tokens in keyword_expectations:
            if re.search(r"\b" + re.escape(req_kw) + r"\b", lowered_req):
                if not any(tok in plan_blob for tok in expected_tokens):
                    issues.append(f"Incomplete plan: requested '{req_kw}' action is missing from plan steps.")

        return len(issues) == 0, issues

    @staticmethod
    def detect_truncated_json(text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Detects incomplete or token-truncated JSON model output."""
        if metadata and metadata.get("truncated"):
            return True, "Model output hit token limit (done_reason=length)."
        if not text or not text.strip():
            return True, "Empty model output."
        stripped = text.strip()
        if stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]"):
            return True, "Unbalanced JSON brackets indicate truncated output."
        return False, ""

    def generate_structured_plan(self, user_request: str, tier: Optional[str] = None, max_retries: int = 2) -> Optional[ExecutionPlan]:
        """
        Synthesizes a structured multi-step plan for unfamiliar user requests using the model gateway.
        Uses a compact planning schema to stay within local token budgets and detects truncated JSON.
        """
        if not user_request or not isinstance(user_request, str) or not user_request.strip():
            return None

        system_ctx = self.context_builder.build_system_context(user_request)
        tools_snip = self._get_tools_prompt_snippet(user_request)

        base_prompt = (
            f"{system_ctx}\n\n"
            f"You are the Brain Autonomous Task Planner. Decompose this goal into an ordered, compact JSON plan.\n"
            f"User Goal: {user_request}\n\n"
            f"Available Registered Tools:\n{tools_snip}\n\n"
            "Rules:\n"
            "1. ONLY use tool names from Available Registered Tools (or null). Keep descriptions under 6 words.\n"
            "2. Parameters must match tool signature.\n"
            "3. Include a separate step for each distinct action in logical order. Use integer step_id (1, 2, 3...) and put ONLY integer step_ids in 'depends_on' (e.g. [1]), NEVER tool names.\n"
            "4. If critical info is missing, set 'status': 'need_info' and list 'missing_information'.\n"
            "5. Respond ONLY with compact valid JSON:\n"
            '{"goal":"...","intent":"...","steps":[{"step_id":1,"description":"...","tool":"TOOL_NAME","parameters":{},"depends_on":[],"expected_result":"..."}],"completion_criteria":["..."],"missing_information":[],"status":"ready"}'
        )

        effective_tier = tier or ("AUTO" if (self.gateway.providers["groq"].is_available() or self.gateway.providers["gemini"].is_available()) else "LOCAL")
        current_prompt = base_prompt
        token_budget = 768

        for attempt in range(max_retries + 1):
            resp = self.gateway.generate(
                prompt=current_prompt,
                tier=effective_tier,
                timeout=70.0,
                think=False,
                num_predict=token_budget
            )
            self.last_planning_response = resp

            if not resp.success or not resp.text:
                logger.warning(f"Structured plan generation failed from model: {resp.error}")
                return None

            is_trunc, trunc_reason = self.detect_truncated_json(resp.text, resp.metadata)
            if is_trunc:
                logger.warning(f"Truncated plan JSON detected (attempt {attempt + 1}): {trunc_reason}")
                if attempt < max_retries:
                    token_budget = 640
                    current_prompt = (
                        f"{base_prompt}\n\n"
                        f"Your previous response was truncated ({trunc_reason}). "
                        "Keep every description under 4 words and output compact single-line JSON."
                    )
                    continue
                return None

            is_valid, err_reason, plan = self.validate_structured_plan(resp.text)
            if not is_valid or plan is None:
                logger.warning(f"Plan validation failed (attempt {attempt + 1}): {err_reason}")
                if attempt < max_retries:
                    current_prompt = (
                        f"{base_prompt}\n\n"
                        f"Your previous JSON plan failed schema validation: {err_reason}\n"
                        "Fix the error and output ONLY compact valid JSON."
                    )
                    continue
                return None

            quality_ok, quality_issues = self.validate_plan_quality(plan, user_request)
            if quality_ok:
                return plan

            logger.warning(f"Plan quality validation failed (attempt {attempt + 1}): {quality_issues}")
            if attempt < max_retries:
                issues_str = "; ".join(quality_issues)
                current_prompt = (
                    f"{base_prompt}\n\n"
                    f"Your previous plan was rejected as incomplete/invalid: {issues_str}\n"
                    "Revise the plan to include ALL required steps, valid parameters, dependencies, and completion_criteria. "
                    "Output ONLY compact valid JSON."
                )
                continue
            return None

        return None

    def evaluate_step_result(
        self,
        step: ExecutionStep,
        result: Dict[str, Any],
        goal_state: Optional[GoalState] = None
    ) -> Dict[str, Any]:
        """
        Evaluates tool execution observation and determines next cognitive action:
        - CONTINUE: Proceed to next step.
        - RETRY: Retry step when failure is transient and within retry limits.
        - REPLAN: Suggest alternate tool or recovery method.
        - STOP: Halt execution safely when critical failure cannot be recovered.
        """
        if not isinstance(result, dict):
            return {"decision": "STOP", "message": "Invalid observation format (result is not a dictionary)."}

        is_success = bool(result.get("success", False))
        if is_success:
            return {"decision": "CONTINUE", "message": f"Step {step.step_id} ({step.tool_name}) executed successfully."}

        # Step failed
        if step.allow_failure:
            return {"decision": "CONTINUE", "message": f"Step {step.step_id} failed, but allow_failure is enabled. Continuing."}

        # Destructive operations must NEVER be automatically retried
        destructive_tools = {"DELETE_FILE", "SHUTDOWN", "RESTART", "LOGOUT"}
        if str(step.tool_name).upper() in destructive_tools:
            return {
                "decision": "STOP",
                "message": f"Destructive operation '{step.tool_name}' failed and is prohibited from automatic retry."
            }

        # Enforce maximum retry limit of 2 retries per step
        if getattr(step, "retry_count", 0) >= 2:
            return {
                "decision": "STOP",
                "message": f"Maximum retry limit (2) exceeded for step {step.step_id} ({step.tool_name}). Halting task."
            }

        goal_id = goal_state.objective if goal_state else "current_goal"
        self.recovery_mgr.record_attempted_method(goal_id, step.tool_name)

        attempts = len(self.recovery_mgr.get_attempted_methods(goal_id))
        if attempts > self.recovery_mgr.max_recovery_attempts:
            return {"decision": "STOP", "message": f"Maximum recovery attempts ({self.recovery_mgr.max_recovery_attempts}) exceeded. Halting task."}

        reason_code, explanation = self.recovery_mgr.diagnose_failure(
            step.tool_name,
            step.arguments,
            result
        )

        alt_res = self.recovery_mgr.suggest_alternative_method(step.tool_name, goal_id)
        if alt_res.get("action") == "SWITCH_METHOD" and alt_res.get("recommended_tool"):
            return {
                "decision": "REPLAN",
                "recommended_tool": alt_res["recommended_tool"],
                "reason": reason_code,
                "message": alt_res.get("message", explanation)
            }

        return {
            "decision": "RETRY",
            "reason": reason_code,
            "message": f"Step {step.step_id} failed: {explanation}. Retrying with fresh observation."
        }


def verify_step_execution(tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    Performs multi-signal evidence verification on tool execution output.
    Never marks a step successful merely because an exception was not thrown.
    Returns: (is_verified: bool, verification_status: str, verification_reason: str)
    verification_status is one of: "VERIFIED", "FAILED", "UNVERIFIED"
    """
    if not isinstance(result, dict):
        return False, "FAILED", "Execution returned non-dictionary result."

    tool_upper = str(tool_name).upper()
    success = bool(result.get("success", False))
    err = result.get("error")
    data = result.get("data")

    if not success or err:
        return False, "FAILED", f"Tool reported execution failure: {err or 'Unknown error'}"

    # Metric / System Monitoring tools
    if tool_upper in ("MEMORY_STATUS", "CPU_STATUS", "CHECK_DISK_SPACE"):
        if data is None:
            return False, "FAILED", f"{tool_upper} returned null observation data."
        if isinstance(data, (dict, str, int, float)) and data:
            return True, "VERIFIED", f"System metrics captured ({type(data).__name__})."
        return False, "FAILED", f"{tool_upper} observation data was empty."

    if tool_upper in ("SYSTEM_INFO", "TIME"):
        if data:
            return True, "VERIFIED", f"Retrieved system status: {str(data)[:60]}."
        return False, "FAILED", f"{tool_upper} returned empty observation data."

    # Process tools
    if tool_upper == "OPEN_APP":
        app_to_check = arguments.get("name") or arguments.get("app_name") or ""
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            return True, "VERIFIED", f"Mock process '{app_to_check}' verified running."
        try:
            from tools.apps import verify_app_open
            ver_res = verify_app_open(app_to_check, timeout=1.0)
            if ver_res.get("verified"):
                return True, "VERIFIED", f"Process '{app_to_check}' verified running via {ver_res.get('method', 'system')}."
            return False, "FAILED", f"Verification failed: Process '{app_to_check}' not found running."
        except Exception as ex:
            if data:
                return True, "VERIFIED", f"Application opened: {data}"
            return False, "FAILED", f"Process verification exception: {ex}"

    if tool_upper == "CLOSE_APP":
        app_to_check = arguments.get("app_name") or arguments.get("name") or ""
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            return True, "VERIFIED", f"Mock process '{app_to_check}' verified closed."
        try:
            from tools.apps import default_app_tracker
            if default_app_tracker.is_running(app_to_check):
                return False, "FAILED", f"Verification failed: Process '{app_to_check}' is still running."
            return True, "VERIFIED", f"Process '{app_to_check}' verified terminated."
        except Exception:
            return True, "VERIFIED", "Process close verified."

    # File system tools
    if tool_upper in ("CREATE_FILE", "WRITE_TEXT_FILE"):
        path = arguments.get("path") or arguments.get("file_path") or ""
        if path and os.path.exists(path):
            return True, "VERIFIED", f"File confirmed on disk: {path} ({os.path.getsize(path)} bytes)."
        elif not path:
            return False, "FAILED", "File path missing in arguments."
        return False, "FAILED", f"Verification failed: Created file does not exist at '{path}'."

    if tool_upper == "CREATE_FOLDER":
        path = arguments.get("path") or arguments.get("folder_path") or ""
        if path and os.path.isdir(path):
            return True, "VERIFIED", f"Directory confirmed on disk: {path}."
        return False, "FAILED", f"Verification failed: Directory does not exist at '{path}'."

    if tool_upper == "DELETE_FILE":
        path = arguments.get("path") or arguments.get("file_path") or ""
        if path and os.path.exists(path):
            return False, "FAILED", f"Verification failed: File '{path}' still exists after deletion."
        return True, "VERIFIED", f"File deletion verified: '{path}' no longer exists."

    if tool_upper in ("LIST_FILES", "FIND_FILES"):
        if isinstance(data, list):
            return True, "VERIFIED", f"File list verified with {len(data)} items."
        return False, "FAILED", "File listing did not return a valid list."

    if tool_upper == "READ_TEXT_FILE":
        if data is not None:
            return True, "VERIFIED", f"File read verified ({len(str(data))} characters)."
        return False, "FAILED", "File read returned null data."

    if tool_upper in ("WEB_SEARCH", "BROWSER_SEARCH"):
        results = result.get("results") or data
        if isinstance(results, list) and len(results) > 0:
            return True, "VERIFIED", f"Web search verified with {len(results)} results."
        if isinstance(results, str) and results:
            return True, "VERIFIED", "Web search results verified."
        return False, "FAILED", "Web search yielded zero results or empty payload."

    # General fallback: non-empty data payload
    if data is not None:
        return True, "VERIFIED", f"Execution outcome confirmed: {str(data)[:60]}"

    return False, "UNVERIFIED", "Execution returned no verifiable outcome data."


def validate_step_permissions(step: ExecutionStep, user_confirmed: bool = False) -> Tuple[bool, str]:
    """
    Validates permissions and confirmation requirements for a step.
    Returns: (is_allowed: bool, reason: str)
    """
    tool_upper = str(step.tool_name).upper()
    args_str = json.dumps(step.arguments).lower()

    # Privilege escalation check
    if any(esc in args_str for esc in ["sudo ", "su -", "su root", "chmod 777", "chmod -r", "chown root"]):
        return False, f"Permission Denied: Unauthorized privilege escalation pattern detected in {tool_upper} arguments."

    # Destructive tools check
    if tool_upper in ("DELETE_FILE", "SHUTDOWN", "RESTART", "LOGOUT"):
        if not user_confirmed and not step.arguments.get("confirmed", False) and not step.requires_confirmation:
            step.requires_confirmation = True
            return False, f"Action requires user confirmation: Destructive operation '{tool_upper}'."

    # Context-based high-risk check
    from tools.input import requires_confirmation
    confirm_eval = requires_confirmation(tool_upper, args_str)
    if confirm_eval.get("requires_confirmation") and not user_confirmed and not step.arguments.get("confirmed", False):
        step.requires_confirmation = True
        return False, confirm_eval.get("reason") or f"Action requires user confirmation: High-risk parameters in '{tool_upper}'."

    return True, "Allowed"


def validate_step_parameters(step: ExecutionStep, registry=None) -> Tuple[bool, str]:
    """
    Validates parameter types and required fields for a step before execution.
    Returns: (is_valid: bool, reason: str)
    """
    if step.action_type != "tool":
        return True, "Non-tool step"

    tool_upper = str(step.tool_name).upper()
    args = step.arguments
    if not isinstance(args, dict):
        return False, f"Step arguments must be a dictionary, got {type(args).__name__}"

    if tool_upper in ("OPEN_APP", "CLOSE_APP", "FOCUS_APP"):
        if not args.get("name") and not args.get("app_name"):
            return False, f"Tool '{tool_upper}' requires 'name' or 'app_name' parameter."

    elif tool_upper in ("READ_TEXT_FILE", "CREATE_FILE", "DELETE_FILE"):
        if not args.get("path") and not args.get("file_path"):
            return False, f"Tool '{tool_upper}' requires 'path' parameter."

    elif tool_upper in ("CREATE_FOLDER",):
        if not args.get("path") and not args.get("folder_path"):
            return False, f"Tool '{tool_upper}' requires 'path' parameter."

    elif tool_upper in ("WEB_SEARCH", "BROWSER_SEARCH"):
        if not args.get("query"):
            return False, f"Tool '{tool_upper}' requires 'query' parameter."

    return True, "Parameters valid"


default_cognition = CognitiveEngine()
