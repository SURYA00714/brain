# Phase 2.1 Failure Analysis Report: Base Model vs Universal Brain

## 1. Executive Summary
- **Track A (Direct Base Model - `qwen3.5:2b-q4_K_M`)**: 121 / 150 passed (**80.7%**)
- **Track B (Universal Brain Orchestration)**: 110 / 150 passed (**73.3%**)
- **Net Delta**: -7.4% regression (-11 cases)
- **Case Breakdown**:
  - **Brain HURT (Passed Track A, Failed Track B)**: 31 cases
  - **Brain HELPED (Failed Track A, Passed Track B)**: 20 cases
  - **Both Failed**: 9 cases
  - **Both Passed**: 90 cases

---

## 2. Root Cause Classification of the 31 Regressions

### Category 1: Over-Aggressive Verification & Uncertainty Prompting (16 cases - 51.6%)
* **Cases**: `CAR_01`, `CAR_02`, `CAR_03`, `CAR_06`, `CAR_08`, `CAR_09`, `IND_01`, `IND_03`, `IND_05`, `CON_07`, `PLR_04`, `PLR_07`, `GEN_08`, `MLR_06`, `CSA_04`, `GEN_02`
* **Mechanism**: In `core/reasoning.py`, the default prompt appended:
  ```
  "If information is missing or cannot be verified, state that explicitly."
  ```
  For inductive reasoning (e.g., predicting the sunrise in the East on Friday based on Mon–Thu) and causal reasoning (deducing a memory leak or full disk from described symptoms), the 2B model took this meta-instruction literally and defensively answered `"Cannot be verified"`, `"Not enough information"`, or `"Insufficient information"` instead of deriving the intended deduction from the premises.
* **Resolution**: Causal, inductive, and deductive premise-based tasks must execute in **DIRECT** mode without meta-uncertainty prompts.

### Category 2: False Positive Contradiction Detection (3 cases - 9.7%)
* **Cases**: `CAR_07`, `CAR_10`, `CON_06`
* **Mechanism**: In `core/math_logic.py`, `detect_logical_contradictions()` flagged valid numeric and unit differences as contradictory:
  - `CAR_10`: "two 4GB models loaded on 8GB RAM" triggered `"Numeric contradiction for 'gb': 4, 8"`.
  - `CAR_07`: "800ms → 5ms speedup" triggered conflicting numeric values.
  The engine injected a `"Contradiction detected in input"` warning into the prompt, forcing the model to report contradiction rather than explaining the causal mechanism.
* **Resolution**: Scope numeric contradiction checks so they only compare values attached to the exact same entity and attribute, and exclude delta/transition expressions (`X -> Y`, `X to Y`).

### Category 3: Deterministic AST Over-Capture on Alphanumerics (1 case - 3.2%)
* **Cases**: `ABR_01`
* **Mechanism**: Query `"A1, B2, C3, D4, ?"` matched sequence pattern keywords. `try_deterministic_math_or_logic()` stripped letters, extracted numbers `[1, 2, 3, 4]`, and deterministically returned `"5 (arithmetic (d=1.0))"` instead of `"E5"`.
* **Resolution**: Require pure numeric tokens in `try_deterministic_math_or_logic()` sequence solver; alphanumeric tokens must fall through to the LLM or alphanumeric pattern recognizers.

### Category 4: Multi-Step Word Math Decomposition Degradation (6 cases - 19.4%)
* **Cases**: `MWP_06`, `MWP_07`, `MWP_08`, `MWP_09`, `MWP_10`, `MSL_04`
* **Mechanism**: The deterministic AST engine only handles self-contained arithmetic expressions (e.g., `"12 + 8 * 3"`), not multi-sentence word problems. Word problems fell through to `DeepReasoningEngine` decomposition, which instructed the model to state `"ONLY the final verified answer"`, which deprived the 2B model of its natural chain-of-thought scratchpad where it would otherwise calculate intermediate steps correctly.
* **Resolution**: Allow multi-step word problems to use concise step-by-step thinking scratchpads or route directly.

### Category 5: Language & Translation Mismatch (2 cases - 6.5%)
* **Cases**: `MLR_01`, `MLR_02`
* **Mechanism**: In multilingual queries, prompt formatting caused the model to answer in the input source language rather than following target language constraints.

### Category 6: Abstract Reasoning Strategy Degradation (3 cases - 9.7%)
* **Cases**: `ABR_10`, `GEN_01`, `GEN_06`
* **Mechanism**: The decomposition prompt forced an artificial schema (`Knowns: ... Unknowns: ... Reasoning: ...`) that confused the 2B model on novel analogies and spatial riddles.

---

## 3. Action Plan for Phase 2.2
1. **Stage 1 (Conditional Intelligence Layer)**:
   - Create 3 distinct execution modes: `DIRECT`, `ASSISTED`, `VERIFIED`.
   - Never inject uncertainty / missing-info disclaimers on premise-contained causal/inductive tasks.
   - Refactor `detect_logical_contradictions()` to eliminate false positives on transitions and multi-attribute specs.
   - Guard deterministic sequence solvers against alphanumeric inputs.
2. **Stage 2 (Model-Specific Optimization)**:
   - Target interventions exclusively where the model has measured probe failures (negative lexical constraints, pure math word problems).
3. **Stage 3 & 4 (Experiments & Held-Out Benchmark)**:
   - Quantify per-strategy performance.
   - Build a 200-case held-out benchmark (`generalization_benchmark_v7.json`).
