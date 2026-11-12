# Universal Local Model Intelligence Framework (Brain Phase 2.1)

## Overview
Brain Phase 2.1 introduces a model-independent intelligence abstraction layer designed to run on consumer hardware (AMD Ryzen 3 7320U, 8 GB RAM, AMD Radeon 610M iGPU, Linux Mint) with local Ollama providers.

The framework decouples Brain's cognitive planning, reasoning, memory, and deterministic tool execution from any specific base model, allowing seamless plug-and-play compatibility across base models, fine-tuned models, quantized GGUF variants, and future local LLMs.

---

## Architecture Components

```
+-------------------------------------------------------------------+
|                     User Request / Goal                           |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|               Universal Reasoning Orchestrator                    |
|                (core/universal_reasoning.py)                      |
|  - Dynamic 9-Strategy Selection (Direct, Decomp, Math, Tool, etc) |
|  - Strategy selection conditioned on Model Capability Profile     |
+-------------------------------------------------------------------+
        |                                           |
        v (Fast Path: Math/Logic/Seq)               v (LLM Reasoning Path)
+-------------------------------+   +-------------------------------+
|  Deterministic Engine (<1ms)  |   |    Adaptive Prompt Optimizer  |
|     (core/math_logic.py)      |   |  (models/prompt_optimizer.py) |
| - AST Arithmetic              |   | - Context budgeting           |
| - Unit Conversions            |   | - Few-shot weak-point filling |
| - Contradiction Detection     |   | - Strict constraint phrasing  |
+-------------------------------+   +-------------------------------+
                                                    |
                                                    v
                                    +-------------------------------+
                                    |    Universal Model Adapter    |
                                    | (models/universal_adapter.py) |
                                    | - Discovery (/api/tags)       |
                                    | - Metadata (/api/show)        |
                                    | - Safe unload (keep_alive: 0) |
                                    | - Normalized generate()       |
                                    +-------------------------------+
                                                    |
                                                    v
                                    +-------------------------------+
                                    | Model Capability Profiler     |
                                    | (models/capability_profiler)  |
                                    | - 10 Empirical Probe Specs    |
                                    | - MEASURED/INFERRED/UNKNOWN   |
                                    +-------------------------------+
```

---

## 1. Universal Model Adapter (`models/universal_adapter.py`)
- **Auto-Discovery**: Queries Ollama's `/api/tags` and `/api/show` to discover locally installed models without requiring configuration.
- **Metadata Extraction**: Inspects GGUF architecture format, model family, parameter size (`1.9B`, `2B`, etc.), quantization level (`Q4_K_M`), context window limits, and file size.
- **Hardware-Constrained Unloading**: Enforces sequential model swapping by invoking `keep_alive: 0` before loading a new model, preventing multiple weights from coexisting in RAM on 8 GB systems.
- **Normalized Generation Interface**: Normalizes input parameters (`num_ctx`, `num_predict`, `temperature`), tracks telemetry (`tokens_per_sec`, TTFT, `done_reason`), and guarantees standard `ModelResponse` output.

---

## 2. Model Capability Profiler (`models/capability_profiler.py`)
Rather than inferring capability from model names or marketing claims, models are evaluated empirically across 10 standardized probe dimensions:

| Capability Dimension | Measurement Method | Failure Mitigation |
| :--- | :--- | :--- |
| **Instruction Following** | Strict negative lexical constraint (forbidden letters/lengths) | Automatic constraint-based prompting with upfront warnings |
| **Logical Reasoning** | Syllogistic / transitive deduction | Step-by-step chain decomposition |
| **Mathematical Reasoning** | Multi-step word problems | `<1ms` deterministic AST math intercept |
| **Multi-step Planning** | Sequential dependency ordering | Structured planning validator with cycle check |
| **Structured JSON** | Key validation against schema | Strict raw JSON formatting instructions & bounded repair |
| **Tool-Call Formatting** | Tool name & arguments JSON structure | Deterministic tool registry argument validation |
| **Context Retention** | Single-turn token recall | Verified-first context builder with character budget |
| **Ambiguity Handling** | Under-specified command detection | Clarification request prompt |
| **Uncertainty Calibration** | Unanswerable future question probe | Explicit uncertainty analysis strategy |
| **Multilingual Ability** | Direct cross-language translation | Multi-pass language verification |

Profiles are categorized into `MEASURED`, `INFERRED`, `UNKNOWN`, and `UNSUPPORTED`, and persisted in [`data/model_profiles.json`](file:///home/jai/Downloads/Brain/data/model_profiles.json).

---

## 3. Universal Reasoning Orchestrator (`core/universal_reasoning.py`)
Coordinates 9 reasoning strategies based on the task type and the active model's profile:
1. `DIRECT_RESPONSE`: Selected when the model has measured strong reasoning and the query is concise.
2. `STEP_BY_STEP_DECOMPOSITION`: Selected for complex multi-part goals or when the model requires decomposition.
3. `CONSTRAINT_BASED_REASONING`: Selected when forbidden words or characters are detected.
4. `EVIDENCE_BASED_REASONING`: Selected for verification against factual snippets.
5. `MEMORY_ASSISTED_REASONING`: Selected when relevant personal facts exist in SQLite memory.
6. `TOOL_ASSISTED_REASONING`: Selected when OS actions or apps are requested.
7. `MATHEMATICAL_VERIFICATION`: Selected for arithmetic, sequences, or unit conversions, routed to AST engine in `<1ms`.
8. `ALTERNATIVE_COMPARISON`: Selected for trade-off queries.
9. `UNCERTAINTY_ANALYSIS`: Selected when future or unobservable facts are requested.

---

## 4. Model-Isolated Experience Learning (`core/adaptive.py`)
In Phase 2.1, experience records and procedural memory schemas in SQLite are indexed by `model_id`.
- Model A's failure history on complex plans does not contaminate Model B's strategy routing.
- High-performing procedural templates learned with a fine-tuned model are preserved separately from the base model.
