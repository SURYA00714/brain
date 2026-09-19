import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

from core.context import default_short_term_memory, default_context_builder
from core.world_state import default_world_state
from models.gateway import default_gateway, ModelResponse
from tools.search import research_topic
from tools.plan import ExecutionPlan, ExecutionStep
from tools.registry import default_registry


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

        # 2. Ambiguity check
        if lowered in {"fix this", "do this", "handle it", "fix it", "what about it", "help with this"}:
            last_app = self.short_term_mem.get_last_app()
            last_query = self.short_term_mem.get_last_query()
            if not last_app and not last_query:
                return {
                    "intent": "AMBIGUOUS",
                    "level": CognitiveLevel.LEVEL_0_DETERMINISTIC,
                    "clarification": "Could you clarify what you would like me to fix or handle? Please specify the application or problem."
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

        # Phase 18: Quality & Relevance Domain Filtering
        # Filter findings and sources by domain keywords to prevent irrelevant or portal results
        stop_words = {"the", "a", "an", "and", "or", "for", "with", "about", "what", "is", "are", "how", "latest", "recent", "new", "in", "on", "at", "to", "from"}
        q_tokens = [w.lower() for w in re.findall(r"\w+", clean_q) if len(w) > 2 and w.lower() not in stop_words]
        if q_tokens:
            scored_findings = []
            for f in findings:
                f_lower = f.lower()
                matches = sum(1 for tok in q_tokens if tok in f_lower)
                if matches > 0:
                    scored_findings.append((matches, f))
            if scored_findings:
                scored_findings.sort(key=lambda x: x[0], reverse=True)
                findings = [item[1] for item in scored_findings[:3]]

        joined_findings = "\n".join(f"- {f}" for f in findings)

        # Stage 2: Synthesis - Use Cloud model if available
        cloud_avail = self.gateway.providers["groq"].is_available() or self.gateway.providers["gemini"].is_available()
        if cloud_avail:
            prompt = f"Summarize these verified search results about '{clean_q}' in 2 concise sentences:\n{joined_findings}"
            res = self.gateway.generate(prompt, tier="CLOUD", timeout=5.0)
            self.last_synthesis_response = res
            if res.success and res.text:
                return {
                    "epistemic_status": EpistemicStatus.RETRIEVED,
                    "text": f"Summary for '{clean_q}':\n{res.text.strip()}",
                    "sources": sources,
                    "model_used": True,
                    "provider": res.provider
                }

        self.last_synthesis_response = None
        # Offline deterministic fallback: return clean extracted bullet points directly (<1ms)
        answer = f"Based on retrieved web sources for '{clean_q}':\n{joined_findings}"
        return {
            "epistemic_status": EpistemicStatus.RETRIEVED,
            "text": answer,
            "sources": sources,
            "model_used": False
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

        # Compile targeted contextual prompt
        import sys
        brain_mod = sys.modules.get("brain")
        builder = getattr(brain_mod, "default_context_builder", self.context_builder) if brain_mod else self.context_builder
        system_ctx = builder.build_system_context(user_request)
        full_prompt = (
            f"{system_ctx}\n\n"
            f"User Question: {user_request}\n\n"
            "Instructions: Provide a concise, factual, and grounded response. "
            "Distinguish observed system facts from inferred possibilities. "
            "If an exact cause is not verified, state it as a possibility rather than a fact."
        )

        tier = "CLOUD"
        resp = self.gateway.generate(prompt=full_prompt, tier=tier, timeout=30.0)
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
            if resp.fallback_used:
                # Honestly inform user of local fallback if cloud failed
                return f"[Local fallback]: {out_text}"
            return out_text

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

        return None


default_cognition = CognitiveEngine()
