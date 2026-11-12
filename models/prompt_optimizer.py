"""
Adaptive Prompt Optimizer for Brain.
Generates model-independent prompt templates with capability-aware adjustments.
Optimizes instruction clarity, context window budgeting, token allocation,
and constraint presentation based on measured model capabilities.
Does not claim prompt optimization increases intrinsic model weights or IQ.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from models.capability_profiler import ModelCapabilityProfile

logger = logging.getLogger("brain.models.prompt_optimizer")


class PromptOptimizer:
    """
    Constructs model-tailored prompts by adapting verbosity, token limits,
    few-shot guidance, and constraint formatting to measured model capabilities.
    """

    BASE_SYSTEM_PROMPT = "You are an accurate, reliable, and helpful AI assistant."

    @staticmethod
    def build_system_prompt(
        profile: Optional[ModelCapabilityProfile] = None,
        task_type: str = "general",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Builds a concise, capability-adapted system prompt.
        """
        parts = [PromptOptimizer.BASE_SYSTEM_PROMPT]

        if not profile:
            return " ".join(parts)

        # Context length awareness: keep system prompt ultra-short for small models
        ctx_len = profile.metadata.get("context_window", 2048)
        is_compact = ctx_len <= 2048

        # Instruction-following adjustments
        if not profile.is_capable("instruction_following", threshold=0.7):
            parts.append("Pay extreme attention to negative constraints and formatting instructions.")

        # Structured JSON adjustments
        if task_type == "planning" or task_type == "json":
            if profile.is_capable("structured_json_generation", threshold=0.7):
                parts.append("Provide valid JSON without markdown fences.")
            else:
                parts.append("Return ONLY raw JSON starting with '{' and ending with '}'. Do not include conversational remarks.")

        # Tool calling adjustments
        if task_type == "tool_calling":
            parts.append("Select only valid tools from the provided schema. Do not invent non-existent tools.")

        # Negative constraints preservation
        if constraints:
            if constraints.get("forbidden_words"):
                parts.append(f"Forbidden words: {constraints['forbidden_words']}.")
            if constraints.get("forbidden_chars"):
                parts.append(f"Forbidden characters: {constraints['forbidden_chars']}.")

        return " ".join(parts)

    @staticmethod
    def calculate_token_budget(
        prompt: str,
        profile: Optional[ModelCapabilityProfile] = None,
        task_complexity: str = "moderate",
    ) -> Dict[str, int]:
        """
        Computes dynamic num_ctx and num_predict based on task complexity
        and model profile.
        """
        prompt_tokens = max(len(prompt.split()) * 2, 64)

        if task_complexity == "simple":
            predict_budget = 128
        elif task_complexity == "complex":
            predict_budget = 512
        else:
            predict_budget = 256

        # Cap predict budget if model struggles with long generation truncation
        if profile and profile.metadata.get("parameter_size") in ("1.5B", "1.9B", "2B"):
            predict_budget = min(predict_budget, 448)

        num_ctx = min(max(prompt_tokens + predict_budget + 128, 1024), 2048)

        return {
            "num_ctx": num_ctx,
            "num_predict": predict_budget,
        }

    @staticmethod
    def format_few_shot(
        task_type: str,
        profile: Optional[ModelCapabilityProfile] = None,
    ) -> str:
        """
        Selects minimal few-shot demonstrations only when model has measured gaps.
        """
        if not profile:
            return ""

        # Only inject few-shot if the model has a measured weakness in that area
        if task_type == "json" and not profile.is_capable("structured_json_generation", threshold=0.6):
            return "Example output: {\"status\": \"ok\", \"count\": 1}\n"

        if task_type == "planning" and not profile.is_capable("multistep_planning", threshold=0.6):
            return "Example plan:\nStep 1: Check requirements\nStep 2: Execute task\nStep 3: Verify outcome\n"

        return ""
