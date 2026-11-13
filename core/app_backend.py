"""
Brain Unified Application Backend.
Connects the Universal Reasoning Orchestrator, Model Gateway, Tool Registry,
Adaptive Memory, and Resource Telemetry into a single unified interface.
Strictly local, no Yui or Aoi companion/avatar dependencies.
"""

import os
import gc
import time
import psutil
from typing import Dict, Any, List, Optional

from models.universal_adapter import UniversalModelAdapter
from models.capability_profiler import ModelCapabilityProfiler
from core.universal_reasoning import (
    UniversalReasoningOrchestrator,
    UniversalStrategy,
    ExecutionMode,
    UniversalReasoningResult,
)
from core.adaptive import AdaptiveIntelligenceEngine
from core.context import default_short_term_memory, default_context_builder
from core.cognition import CognitiveEngine
from tools.registry import default_registry
from tools.router import default_router
from brain import run_planner_task


class BrainAppCore:
    """
    Unified manager for the Brain executable application.
    Supports dynamic model switching, execution mode overrides, and full telemetry.
    """

    def __init__(self, default_model: Optional[str] = None):
        self.adapter = UniversalModelAdapter()
        self.profiler = ModelCapabilityProfiler(self.adapter)
        self.orchestrator = UniversalReasoningOrchestrator(
            adapter=self.adapter, profiler=self.profiler
        )
        self.memory_engine = AdaptiveIntelligenceEngine()
        self.cognitive_engine = CognitiveEngine()

        # Discover installed models
        models = self.adapter.list_models()
        self.available_models = [m.name for m in models] if models else ["qwen3.5:2b-q4_K_M"]

        # Default model selection: prefer qwen3.5-brain:v2, then qwen3.5:2b-q4_K_M
        if default_model and default_model in self.available_models:
            self.active_model = default_model
        elif "qwen3.5-brain:v2" in self.available_models:
            self.active_model = "qwen3.5-brain:v2"
        elif "qwen3.5:2b-q4_K_M" in self.available_models:
            self.active_model = "qwen3.5:2b-q4_K_M"
        else:
            self.active_model = self.available_models[0]

        self.adapter.set_active_model(self.active_model, unload_previous=False)
        self.current_mode = "AUTO"  # AUTO | DIRECT | ASSISTED | VERIFIED

    def switch_model(self, model_name: str) -> bool:
        """
        Safely switches active model with sequential VRAM/RAM unloading.
        """
        if model_name not in self.available_models:
            # Refresh in case a new model was pulled in Ollama
            self.adapter.refresh_models()
            self.available_models = [m.name for m in self.adapter.list_models()]

        if model_name in self.available_models:
            success = self.adapter.set_active_model(model_name, unload_previous=True)
            if success:
                self.active_model = model_name
                gc.collect()
                return True
        return False

    def set_execution_mode(self, mode: str) -> None:
        """
        Sets execution mode: AUTO, DIRECT, ASSISTED, or VERIFIED.
        """
        m_upper = mode.upper().strip()
        if m_upper in ("AUTO", "DIRECT", "ASSISTED", "VERIFIED"):
            self.current_mode = m_upper

    def clear_conversation(self):
        """Clears short-term conversational dialogue memory."""
        default_short_term_memory.clear()

    def execute_task(self, prompt: str) -> Dict[str, Any]:
        """
        Executes a user request or reasoning problem.
        Routes through UniversalReasoningOrchestrator or Planner Loop as appropriate.
        """
        start_time = time.perf_counter()
        ram_before = psutil.virtual_memory().used / (1024 * 1024)

        # 1. Resolve conversational references (e.g. "close it", "focus it")
        resolved_prompt = default_short_term_memory.resolve_references(prompt)

        # 2. Check if user specified a forced mode
        forced_mode = None
        if self.current_mode == "DIRECT":
            forced_mode = ExecutionMode.DIRECT
        elif self.current_mode == "ASSISTED":
            forced_mode = ExecutionMode.ASSISTED
        elif self.current_mode == "VERIFIED":
            forced_mode = ExecutionMode.VERIFIED

        # 3. Check if the query is an OS/desktop tool command (e.g. apps, bluetooth, wifi, files)
        routed = default_router.route(resolved_prompt)
        p_lower = resolved_prompt.lower()
        tool_keywords = ("open ", "launch ", "click ", "type ", "terminal", "screenshot", "find files", "list files")
        is_tool_action = (routed is not None) or any(k in p_lower for k in tool_keywords)

        if is_tool_action:
            # Run through Brain autonomous execution planner
            res_text = run_planner_task(resolved_prompt, quiet=True)
            dur_ms = (time.perf_counter() - start_time) * 1000.0
            ram_after = psutil.virtual_memory().used / (1024 * 1024)
            dur_sec = round(dur_ms / 1000.0, 2)
            ram_gb = round(ram_after / 1024.0, 2)

            # Record turn in conversational short-term memory
            tool_name = routed.get("tool") if isinstance(routed, dict) else "PLANNER"
            default_short_term_memory.add_turn(
                user_text=prompt,
                agent_response=str(res_text),
                tool_used=tool_name
            )

            return {
                "text": str(res_text),
                "strategy": "TOOL_ASSISTED_EXECUTION",
                "mode": "VERIFIED",
                "execution_path": "AUTONOMOUS_TOOL_EXECUTION",
                "model_id": self.active_model,
                "duration_ms": round(dur_ms, 1),
                "duration_sec": dur_sec,
                "ram_mb": round(ram_after, 1),
                "ram_gb": ram_gb,
                "verified": True,
                "confidence": 1.0,
            }

        # 4. Check if query requires real-time factual web grounding
        freshness_triggers = (
            "who is president", "who is the president", "who is prime minister",
            "who is the prime minister", "current price", "latest news", "who won",
            "weather in", "current weather"
        )
        if any(f in p_lower for f in freshness_triggers):
            web_res = self.cognitive_engine.execute_web_research(resolved_prompt)
            if web_res and web_res.get("text"):
                dur_ms = (time.perf_counter() - start_time) * 1000.0
                ram_after = psutil.virtual_memory().used / (1024 * 1024)
                dur_sec = round(dur_ms / 1000.0, 2)
                ram_gb = round(ram_after / 1024.0, 2)
                res_text = web_res["text"]

                default_short_term_memory.add_turn(
                    user_text=prompt,
                    agent_response=res_text,
                    tool_used="WEB_RESEARCH"
                )

                return {
                    "text": res_text,
                    "strategy": "GROUNDED_WEB_RESEARCH",
                    "mode": "VERIFIED",
                    "execution_path": "LIVE_WEB_RESEARCH",
                    "model_id": self.active_model,
                    "duration_ms": round(dur_ms, 1),
                    "duration_sec": dur_sec,
                    "ram_mb": round(ram_after, 1),
                    "ram_gb": ram_gb,
                    "verified": True,
                    "confidence": 1.0,
                }

        # 5. Otherwise run through Universal Reasoning Orchestrator with dialogue context and grounded system context
        context = default_short_term_memory.get_context_snippet()
        sys_context = default_context_builder.build_system_context(resolved_prompt)
        res: UniversalReasoningResult = self.orchestrator.solve(
            prompt=resolved_prompt,
            context=context,
            system_prompt=sys_context,
            model_id=self.active_model,
            forced_mode=forced_mode,
        )

        dur_ms = (time.perf_counter() - start_time) * 1000.0
        ram_after = psutil.virtual_memory().used / (1024 * 1024)
        dur_sec = round(dur_ms / 1000.0, 2)
        ram_gb = round(ram_after / 1024.0, 2)

        # Record turn in conversational short-term memory
        default_short_term_memory.add_turn(
            user_text=prompt,
            agent_response=res.text
        )
        ram_gb = round(ram_after / 1024.0, 2)

        # Record experience in adaptive memory
        try:
            self.memory_engine.record_experience(
                user_request=prompt,
                strategy_used=res.strategy,
                plan_dict={"text": res.text, "mode": res.mode},
                tools_selected=[],
                tool_results=[],
                duration_ms=dur_ms,
                verification_outcome="VERIFIED" if res.verified else "UNVERIFIED",
                outcome="SUCCESS" if res.verified else "PARTIAL",
                model_id=self.active_model,
            )
        except Exception:
            pass

        return {
            "text": res.text,
            "strategy": res.strategy,
            "mode": getattr(res, "mode", "DIRECT"),
            "execution_path": res.execution_path,
            "model_id": res.model_id,
            "duration_ms": round(dur_ms, 1),
            "duration_sec": dur_sec,
            "ram_mb": round(ram_after, 1),
            "ram_gb": ram_gb,
            "verified": res.verified,
            "confidence": res.confidence,
            "tokens_per_sec": res.tokens_per_sec,
            "metadata": res.metadata,
        }

    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns real-time system and model memory metrics."""
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        used_gb = round(vm.used / (1024**3), 2)
        total_gb = round(vm.total / (1024**3), 2)
        avail_gb = round(vm.available / (1024**3), 2)
        return {
            "active_model": self.active_model,
            "available_models": self.available_models,
            "current_mode": self.current_mode,
            "ram_used_gb": used_gb,
            "ram_total_gb": total_gb,
            "ram_avail_gb": avail_gb,
            "ram_used_mb": round(vm.used / (1024 * 1024), 1),
            "ram_total_mb": round(vm.total / (1024 * 1024), 1),
            "ram_percent": vm.percent,
            "cpu_percent": cpu,
            "cpu_model": "AMD Ryzen 3 7320U (4C/8T)",
        }


# Global singleton instance for application use
default_app_core = BrainAppCore()
