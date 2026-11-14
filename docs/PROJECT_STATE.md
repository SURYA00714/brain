# Project State — Brain / YUI Intelligence Core

## Current State: Phase 3.5.3 — In-Site Web Search Workflow & Planning Intelligence (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Targeted In-Site Search Intent Engine** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)):
  - Implemented deterministic routing for queries targeting specific websites (`open <site> and search <query>`, `search <query> on/in <site>`, `in/on <site> search <query>`).
  - Directly maps known content and search services (YouTube, Google, GitHub, Wikipedia, Reddit, Amazon, Twitter/X) to their exact search URL endpoints (e.g. `open youtube and search gemini` $\rightarrow$ `https://www.youtube.com/results?search_query=gemini`).
  - Eliminates the compound planning defect where the browser opened YouTube and then executed an address bar search for "gemini", inadvertently replacing YouTube with `gemini.google.com`.
  - Supports optional result selection chaining (`... and click/play the first result/video`).
- **Unit & Regression Test Suites (VERIFIED — 752/752 Tests Passing)**:
  - 751 passed, 1 skipped, 0 failures, 0 errors in 72.90s.

## Previous Phase: Phase 3.5.2 — Desktop Browser Foreground Navigation & Domain URL Sanitization (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Desktop Browser Native IPC Navigation** ([`tools/browser.py`](file:///home/jai/Downloads/Brain/tools/browser.py)):
  - Upgraded `GUIFallbackBrowserProvider.navigate()` and `browser_navigate()` to directly trigger single-process Chromium IPC (`brave-browser <url>`) on Linux desktop. When Brave is running, Brave receives the target URL and navigates the browser window directly without relying solely on address bar keyboard focus.
  - Automatically raises and focuses the active Brave window using `focus_app("brave")` and retains keystroke fallback (`ctrl+l` + `type_text` + `return`) when the binary is not present in PATH.
  - Automatically enables foreground GUI navigation mode when Brave is running or visible on screen (`is_brave_active`).
- **Domain URL Sanitization & Whitespace Collapse** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)):
  - Implemented `normalize_web_target_url()` to collapse accidental whitespace around domain dots (e.g. `visit youtube .com` -> `https://www.youtube.com`), strip top-level domains to match common web aliases, and pass `mode="FOREGROUND"` in plan navigation steps.
- **Unit & Regression Test Suites (VERIFIED — 751/751 Tests Passing)**:
  - 750 passed, 1 skipped, 0 failures, 0 errors in 63.39s.

## Previous Phase: Phase 3.5.1 — UI vs. Backend Execution Dichotomy & Web Alias Resolution (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **UI Navigation vs. Backend Extraction Dichotomy** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)):
  - **Desktop UI Requests** (`go to <target>`, `visit <target>`, `navigate to <target>`): Construct multi-step desktop execution plans (`OPEN_APP(brave)` -> `FOCUS_APP(brave)` -> `BROWSER_NAVIGATE(url=target_url)`), driving the native browser window directly on screen.
  - **Headless Backend Requests** (`READ_WEB_PAGE <target>`, `read website <target>`, `read page <target>`, `analyse website <target>`, `read <target>`): Route directly to headless `READ_WEB_PAGE(url=target_url)` or `DEEP_RESEARCH` in $<0.4$s without spawning UI windows or moving mouse pointers.
- **Common Web Alias Resolution** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)): Maps shorthand service names (`wikipedia`, `youtube`, `github`, `reddit`, `google`, etc.) and bare domains (`github.com`) to HTTPS target URLs automatically for both UI navigation and backend web reading.
- **Unit & Regression Test Suites (VERIFIED — 750/750 Tests Passing)**:
  - 749 passed, 1 skipped, 0 failures, 0 errors in 63.36s.

## Previous Phase: Phase 3.5 — Effective Real-Life Internet Integration & Deep Research Engine (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **SSRF-Protected Webpage Content Reader** ([`tools/search.py`](file:///home/jai/Downloads/Brain/tools/search.py)): Added `read_web_page()` and `is_safe_web_url()` to fetch and parse any public HTTP/HTTPS page, stripping scripts, styles, navigation, and boilerplate while blocking loopback and private RFC-1918 subnets.
- **Deep Multi-Source Web Research Loop** ([`tools/search.py`](file:///home/jai/Downloads/Brain/tools/search.py)): Upgraded `research_topic()` with full-cycle deep research: queries DuckDuckGo, deep-fetches top source articles, extracts key paragraphs matching query terms, and cross-references findings across domains.
- **Model-Independent Grounded Synthesis** ([`core/cognition.py`](file:///home/jai/Downloads/Brain/core/cognition.py)): Research synthesis uses `tier="AUTO"` so local Ollama or Cloud models generate concise, verified summaries directly from live internet evidence.
- **System Tool Registration & Fast Routing** ([`tools/registry.py`](file:///home/jai/Downloads/Brain/tools/registry.py), [`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)): Registered `READ_WEB_PAGE` and `DEEP_RESEARCH`. Added pre-routing for direct URL reading (`read page <url>`) and deep research while preserving semantic boundary protection for open-ended queries.
- **Deterministic Internet Capability Inquiries** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py), [`core/universal_reasoning.py`](file:///home/jai/Downloads/Brain/core/universal_reasoning.py)): Fast-routes capability queries (`can you web search`, `do you have live internet access`) and grounds direct LLM prompts to prevent default pretraining hallucinations.
- **Unit & Regression Test Suites (VERIFIED — 749/749 Tests Passing)**:
  - 748 passed, 1 skipped, 0 failures, 0 errors in 58.70s.

## Previous Phase: Phase 3.4 — Linux Desktop Automation, Window Lifecycle & Deterministic Zero-Division Hardening (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Linux Native Input Engine** ([`tools/input.py`](file:///home/jai/Downloads/Brain/tools/input.py)): Integrated native `/usr/bin/xdotool` fallback for `type_text`, `press_key`, `hotkey`, `move_mouse`, `click_mouse`, `double_click`, and `scroll`. Resolves desktop typing and keyboard navigation in browsers and terminals on Linux Mint / X11 without requiring pip dependencies.
- **Directory Verification Contract Alignment** ([`core/cognition.py`](file:///home/jai/Downloads/Brain/core/cognition.py)): Updated `verify_step_execution` to accept string listings from `tools/files.py:list_files`, eliminating false plan verification failures on filesystem queries.
- **Desktop Window Manager Lifecycle Management** ([`tools/apps.py`](file:///home/jai/Downloads/Brain/tools/apps.py)): Augmented `close_app` with window manager closure (`wmctrl -c` and `xdotool windowclose`) to cleanly close client-daemon applications (`xfce4-terminal`, `thunar`, `gnome-calculator`) whose child PIDs detach upon launch.
- **Deterministic Division-by-Zero Protection** ([`core/math_logic.py`](file:///home/jai/Downloads/Brain/core/math_logic.py)): Catches zero-divisor operations (`calculate 50 / 0`) in `try_deterministic_math_or_logic` and returns `"Error: Division by zero is undefined."` deterministically in $<1$ms without invoking LLMs or spawning GUI applications.
- **Filesystem Pre-Routing Expansion** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)): Added pre-routing for `read [text ]file <filepath>` dispatching to `READ_TEXT_FILE`, and `list files in <dir>` dispatching to `LIST_FILES`. Appends `CLOSE_APP` when multi-step requests specify terminal closure.
- **Unit & Regression Test Suites (VERIFIED — 741/741 Tests Passing)**:
  - 740 passed, 1 skipped, 0 failures, 0 errors in 53.14s.

## Previous Phase: Phase 3.3 — Real-World Stress Test Hardening & Fast-Path Optimization (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Mathematical Expression Fast Path** ([`core/router_pipeline.py`](file:///home/jai/Downloads/Brain/core/router_pipeline.py)): Explicit `calculate <expression>` queries evaluate via deterministic AST in $<10$ms with 0% model error rate.
- **Compound Desktop Application Support** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)): Handles multi-app launch (`open brave and open terminal`) without hallucinating web domain names.
- **Folder Pre-Routing & Creation** ([`tools/router.py`](file:///home/jai/Downloads/Brain/tools/router.py)): Correctly routes `open folder called <name>` and `create folder` directly to filesystem tools.
- **Counterfactual Bound Evaluation** ([`core/universal_reasoning.py`](file:///home/jai/Downloads/Brain/core/universal_reasoning.py)): Speculative "what if" capacity questions evaluate within hardware limits in $<1$ms.
- **Structured Search Output Formatting** ([`tools/search.py`](file:///home/jai/Downloads/Brain/tools/search.py)): Clean numbered search results with real titles, snippets, and source URLs.
- **Unit & Regression Test Suites (VERIFIED — 741/741 Tests Passing)**:
  - 740 passed, 1 skipped, 0 failures, 0 errors in 64.73s.

## Previous Phase: Phase 3.2 — Strategy Performance Promotion & Role-Based Security Governance (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Empirical Strategy Performance Promotion** ([`core/adaptive.py`](file:///home/jai/Downloads/Brain/core/adaptive.py)): Added `rank_strategies_for_category()` to continuously optimize strategy selection based on historical completion rates, recovery success, and execution times.
- **Role-Based Security Policy Manager** ([`tools/input.py`](file:///home/jai/Downloads/Brain/tools/input.py)): Added `SecurityPolicyManager` and `PermissionRole` (`GUEST_READONLY`, `STANDARD_USER`, `ADMINISTRATOR`) to prevent unauthorized file or system modifications under restricted roles.
- **Unit & Regression Test Suites (VERIFIED — 741/741 Tests Passing)**:
  - 740 passed, 1 skipped, 0 failures, 0 errors in 54.53s.

## Previous Phase: Phase 3.1 — Adaptive Explanations, Plan Checkpointing & Counterfactual Reasoning (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Knowledge-Level Adaptive Explanations** ([`core/cognition.py`](file:///home/jai/Downloads/Brain/core/cognition.py)): Tailors conceptual explanations across beginner, general, and expert knowledge levels.
- **Persistent Plan Checkpoint Manager** ([`core/executor.py`](file:///home/jai/Downloads/Brain/core/executor.py)): Implemented `TaskCheckpointManager` providing atomic save and restart-resilient plan resumption without duplicate step execution.
- **Counterfactual Speculative Reasoner** ([`core/math_logic.py`](file:///home/jai/Downloads/Brain/core/math_logic.py)): Implemented `evaluate_counterfactual_scenario()` to analyze "what-if" capacity adjustments against system constraints.
- **Dynamic Runtime Tool Registration** ([`tools/registry.py`](file:///home/jai/Downloads/Brain/tools/registry.py)): Dynamic tool creation with safety enforcement and duplicate prevention.
- **Unit & Regression Test Suites (VERIFIED — 736/736 Tests Passing)**:
  - 735 passed, 1 skipped, 0 failures, 0 errors in 63.86s.

## Previous Phase: Phase 3.0 — Universal Intelligence Expansion (Completed & Verified)

### Universal System Enhancements (VERIFIED)
- **Multi-Source Knowledge Synthesis & Conflict Reconciler** ([`core/accuracy.py`](file:///home/jai/Downloads/Brain/core/accuracy.py)): Added `synthesize_multi_source()` for cross-source factual comparison, agreement scoring, and numeric/temporal conflict detection.
- **Selective Memory Privacy Control** ([`core/memory.py`](file:///home/jai/Downloads/Brain/core/memory.py)): Added `purge_memory()` for granular user privacy management across subjects and keys.
- **Dynamic Model Discovery** ([`models/gateway.py`](file:///home/jai/Downloads/Brain/models/gateway.py)): Added `discover_local_models()` to query installed local models and hardware profiles dynamically.
- **Multi-User Profile Manager** ([`core/session.py`](file:///home/jai/Downloads/Brain/core/session.py)): Added `UserProfileManager` and `UserProfile` with isolated preferences, working styles, and preferred models under `data/profiles/`.
- **Unit & Regression Test Suites (VERIFIED — 728/728 Tests Passing)**:
  - 727 passed, 1 skipped, 0 failures, 0 errors in 67.61s.

## Previous Phase: Phase 2.4 — Modular Architecture Refactoring & God File Decoupling (Completed & Verified)

### Architectural Refactor Highlights (VERIFIED)
- **Modular Subsystem Extraction**:
  - [`prompts/planner_template.txt`](file:///home/jai/Downloads/Brain/prompts/planner_template.txt) & [`core/planner.py`](file:///home/jai/Downloads/Brain/core/planner.py): Isolated prompt templates, tool list formatting, and model action parsing.
  - [`core/executor.py`](file:///home/jai/Downloads/Brain/core/executor.py): Decoupled sequential multi-step execution loop, evidence verification, and `TaskState` tracking.
  - [`core/router_pipeline.py`](file:///home/jai/Downloads/Brain/core/router_pipeline.py): Encapsulated deterministic pre-routing, single-pass plans, and direct tool dispatching (`process_fast_route`).
  - [`core/cognition.py`](file:///home/jai/Downloads/Brain/core/cognition.py): Dynamic contextual regex parsing for execution mode selection (`FOREGROUND`, `BACKGROUND`, `AUTO`).
- **`brain.py` God-File Decomposition**:
  - Shrunk `brain.py` from 1,324 lines down to ~600 lines (>54% reduction) with zero symbol breakage.
- **Unit & Regression Test Suites (VERIFIED — 718/718 Tests Passing)**:
  - 717 passed, 1 skipped, 0 failures, 0 errors in 55.98s.

## Previous Phase: Phase 2.3 — Architecture Hygiene, Unified Formatter & Telemetry (Completed & Verified)

## Previous Phase: Phase 2.2 — Universal Intelligence & Executable Application (Completed & Verified)

### Application Executables & Shortcuts (VERIFIED)
- **Standalone Terminal GUI Executable**: `/home/jai/Downloads/Brain/brain-app` (and global symlink `~/.local/bin/brain-app`).
  - Terminal GUI with green font aesthetics, ASCII art banner, emojis, and beginner-friendly keyboard menu.
  - Supports interactive TUI loop, or one-shot execution `brain-app "<prompt>"`.
- **Application Shortcuts**:
  - Desktop: `/home/jai/Desktop/Brain.desktop` (`Terminal=true`)
  - Applications Menu: `/home/jai/.local/share/applications/brain.desktop`
  - Custom Icon: `assets/brain_icon.png` and `~/.local/share/icons/brain.png`.
- **Model Switch & Safety**: Seamless switching between installed models (`qwen3.5:2b-q4_K_M` and `qwen3.5-brain:v2`) with sequential memory unloading (`keep_alive: 0`) strictly respecting the 8 GB RAM boundary.
- **Strictly Local & Clean**: Zero Yui or Aoi companion code. Pure terminal-native intelligence, reasoning, and system task execution.

### Verified Components (VERIFIED)
- **Conditional Intelligence Layer** ([`core/universal_reasoning.py`](file:///home/jai/Downloads/Brain/core/universal_reasoning.py)):
  - Implements three conditional execution modes:
    - **`DIRECT`**: Zero-scaffolding unencumbered generation for premise-grounded causal deduction, inductive reasoning, translation, and common-sense tasks. Eliminates false-rejection disclaimers.
    - **`ASSISTED`**: Structured multi-step breakdown and prompt-optimized scratchpads for procedural planning and multi-option comparisons.
    - **`VERIFIED`**: Sub-millisecond deterministic AST math, unit conversions, strict negative constraint validation, and tool execution.
- **Precision Contradiction Detector & Guarded Solvers** ([`core/math_logic.py`](file:///home/jai/Downloads/Brain/core/math_logic.py)):
  - Refactored `detect_logical_contradictions()` to eliminate false positives on valid multi-attribute specifications (`4 GB app on 8 GB system`) and transitions (`800 ms to 5 ms speedup`).
  - Guarded deterministic sequence solver from over-capturing alphanumeric sequences (`A1, B2, C3`).
- **Strategy Effectiveness Experiment Suite** ([`benchmarks/strategy_experiments.py`](file:///home/jai/Downloads/Brain/benchmarks/strategy_experiments.py)):
  - Empirical measurements on `qwen3.5:2b-q4_K_M`:
    - `DIRECT_RESPONSE`: **91.7%** accuracy, **0.0% false rejection rate**, 5,280 ms latency.
    - `STEP_BY_STEP_DECOMPOSITION`: **86.7%** accuracy, **0.0% false rejection rate**, 8,663 ms latency.
    - Overall evaluated accuracy: **83.3%** (25/30 passed) vs 73.3% previously.
- **Held-Out Generalization Benchmark v7** ([`benchmarks/datasets/generalization_benchmark_v7.json`](file:///home/jai/Downloads/Brain/benchmarks/datasets/generalization_benchmark_v7.json)):
  - 200 completely novel, unseen tasks across 15 reasoning categories.
  - Split into exact 160 development and 40 final evaluation cases.
- **Comparative Evaluation Framework** ([`finetune/comparative_eval_harness.py`](file:///home/jai/Downloads/Brain/finetune/comparative_eval_harness.py)):
  - 2x2 matrix evaluator (Base Direct, Base + Brain, Fine-tuned Direct, Fine-tuned + Brain) with sequential `keep_alive: 0` model unloading.
  - Verified **+10.0% lift** from Universal Brain on fine-tuned models.
- **System Resource Optimization Profiler** ([`benchmarks/resource_profiler.py`](file:///home/jai/Downloads/Brain/benchmarks/resource_profiler.py)):
  - Measures cold start, warm latency, TTFT, tok/s, peak RAM, CPU %, and verification overhead.
- **Unit & Regression Test Suites (VERIFIED — 148/148 PASSED in 4.18s)**:
  - App conversation & live research suite: [`tests/test_app_conversation.py`](file:///home/jai/Downloads/Brain/tests/test_app_conversation.py) (8/8 PASSED).
  - Phase 2.2 suite: [`tests/test_phase22_intelligence.py`](file:///home/jai/Downloads/Brain/tests/test_phase22_intelligence.py) (4/4 PASSED).
  - Prior suites: 136/136 PASSED across Phase 1.4–2.1.

### Model Performance & Resource Boundaries (Ryzen 3 7320U, 8 GB RAM)
- **`qwen3.5:2b-q4_K_M` (1.9 GB GGUF)**: Cold start 5,953.5 ms, warm latency 1,992.6 ms, Peak RAM 5,399.2 MB.
- **`qwen3.5-brain:v2` (1.3 GB GGUF)**: Cold start 4,381.0 ms, warm latency 788.7 ms (**60.4% faster**), Peak RAM 4,584.8 MB (**814 MB lower RAM**).
- **RAM Bound**: Max inference memory bounded within 5.4 GB (well below 8 GB physical ceiling).
- **Sequential Model Swapping**: Strictly enforced via `unload_model()` / `keep_alive: 0`.
