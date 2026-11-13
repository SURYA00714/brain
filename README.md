# 🧠 Brain — Autonomous Local AI Reasoning & Execution Engine

[![Local-First](https://img.shields.io/badge/Architecture-Local--First-brightgreen.svg)]()
[![Hardware-Target](https://img.shields.io/badge/Hardware-AMD%20Ryzen%203%207320U%20%7C%208GB%20RAM-blue.svg)]()
[![Inference-Engine](https://img.shields.io/badge/Inference-Ollama%20(Local%20GGUF)-orange.svg)]()
[![Tests-Passing](https://img.shields.io/badge/Tests-148%2F148%20Passed-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

**Brain** is an autonomous, private, local-first artificial intelligence operating layer built specifically for Linux desktop environments (Linux Mint / Ubuntu). Operating entirely within hardware boundaries (AMD Ryzen 3 7320U, 8 GB RAM, AMD Radeon 610M), Brain connects local quantized LLMs served via Ollama to deterministic OS tool execution, multi-turn memory, live web research grounding, and verifiable step planning.

---

## ⚡ Key Capabilities & Architecture

```
                                  ┌───────────────────────────┐
                                  │      User Input (TUI)     │
                                  └─────────────┬─────────────┘
                                                │
                                  ┌─────────────▼─────────────┐
                                  │   Reference & Pronoun     │
                                  │       Resolution          │
                                  └─────────────┬─────────────┘
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       │                                                 │
          ┌────────────▼──────────┐                         ┌────────────▼──────────┐
          │  FastRouter / Match   │                         │  Universal Reasoning  │
          │  (Deterministic OS)   │                         │     Orchestrator      │
          └────────────┬──────────┘                         └────────────┬──────────┘
                       │                                                 │
      ┌────────────────┼────────────────┐             ┌──────────────────┼──────────────────┐
      │                │                │             │                  │                  │
┌─────▼─────┐   ┌──────▼──────┐   ┌─────▼─────┐ ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐
│  Desktop  │   │   System    │   │ Universal │ │  DIRECT   │      │ ASSISTED  │      │ VERIFIED  │
│    Apps   │   │  Hardware   │   │ Compound  │ │  (Fast    │      │ (Thinking │      │ (Math AST │
│  (Brave,  │   │   (Wi-Fi,   │   │  Action   │ │ Dialogue) │      │ & Plans)  │      │ & Safety) │
│ Terminal, │   │  Bluetooth, │   │ Decomposer│ └───────────┘      └───────────┘      └───────────┘
│  Thunar)  │   │   Volume)   │   └───────────┘
└───────────┘   └─────────────┘
```

### 1. Three Conditional Execution Modes
- **`DIRECT`**: Sub-3-second conversational generation using local quantized models with active short-term dialogue context and system identity.
- **`ASSISTED`**: Multi-step decomposition, uncertainty analysis, and structured comparative reasoning for complex logic.
- **`VERIFIED`**: Sub-millisecond deterministic math AST evaluation, negative constraint checks, and hardware actions.

### 2. Universal Compound Action Decomposer
- Splits multi-clause requests (*"open brave and open wikipedia"*, *"turn off wifi and turn off bluetooth"*) into sequential execution graphs in `<0.5s`.
- Disambiguates desktop applications from websites (e.g. automatically navigating Brave to `wikipedia.org` or `youtube.com` rather than failing to launch a desktop binary).

### 3. Deterministic OS & Hardware Control
- **Application Lifecycle**: Brave browser, Terminal (`xfce4-terminal`), File Manager (`thunar`), Text Editor, Calculator.
- **Hardware Controls**:
  - Wi-Fi toggle & status via `nmcli` (<50ms).
  - Bluetooth toggle & status via `rfkill` (<40ms).
  - Audio volume up, down, and mute via `amixer`.
  - Screen brightness adjustment via `xrandr`.
  - Full-screen & region capture via `pyautogui`.
- **System Telemetry**: Real-time memory (used/total in GB), CPU percentage, disk space, and process verification.

### 4. Grounded Identity & Live Web Research
- **No Hallucinations**: Injects Brain's verified Linux identity into prompts, eliminating cloud LLM identity confusion.
- **Live Real-Time Grounding**: Temporal and live factual queries (*"who is president of usa"*, *"latest news"*, *"who won"*) trigger fast DuckDuckGo/Brave web research in ~1.5s, delivering factual current-day sources without prompt cheats.

### 5. Multi-Turn Context & Persistent Memory
- **Short-Term Dialogue Context**: Tracks recent turns to resolve pronoun references (*"close it"*, *"focus it"*, *"how many teams are there"*).
- **Persistent SQLite Memory**: Stores user facts, preferences (e.g. browser choice, communication style), and past procedures across sessions.

---

## 💻 Hardware Budget & Supported Models

Engineered strictly for compact, resource-constrained laptops:
- **Processor**: AMD Ryzen 3 7320U (4 Cores / 8 Threads, 2.4 GHz - 4.1 GHz)
- **RAM Bound**: Maximum inference allocation bounded within **5.4 GB** (preserving OS buffer on an 8 GB device).
- **Models Supported via Ollama**:
  - `qwen3.5-brain:v2` (1.3 GB GGUF, default preferred) — Cold start: 4.38s, warm latency: 0.78s (**60% faster**).
  - `qwen3.5:2b-q4_K_M` (1.9 GB GGUF, baseline fallback) — Cold start: 5.95s, warm latency: 1.99s.
  - Supports dynamic model switching with sequential VRAM/RAM unloading (`keep_alive: 0`).

---

## 🖥️ Terminal GUI (TUI)

Brain features an interactive, beginner-friendly terminal interface styled in hacker-green with JetBrains Mono aesthetics:

```
 ██████╗ ██████╗  █████╗ ██╗███╗   ██╗
 ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║
 ██████╔╝██████╔╝███████║██║██╔██╗ ██║
 ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║
 ██████╔╝██║  ██║██║  ██║██║██║ ╚████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
 🧠 AUTONOMOUS LOCAL AI REASONING & EXECUTION ENGINE ⚡
  Local-First • AMD Ryzen 3 7320U • 8GB RAM Safe • Zero Cloud Required
```

### Dashboard Features:
- **Top Metrics Bar**: Active model, execution mode, dynamic RAM usage (`used / total GB (percent%)`), and CPU model/load.
- **Interactive Menu Options**:
  - `1` / `/model`: Dynamic local model switcher.
  - `2` / `/mode`: Force execution mode (`AUTO`, `DIRECT`, `ASSISTED`, `VERIFIED`).
  - `3` / `/tools`: Display registered tool capabilities.
  - `4` / `/stats`: System and hardware telemetry breakdown.
  - `5` / `/clear`: Clear terminal screen & reset dialogue context window.
  - `q` / `exit`: Safely exit Brain.
- **Telemetry Subtitles**: Each response displays execution time (`⏱️ Time: X.XXs`), RAM usage (`💾 RAM: X.XX GB`), and path (`⚡ Path: AUTONOMOUS_TOOL_EXECUTION`).

---

## 🚀 Getting Started

### 1. Prerequisites
- Linux OS (Linux Mint 22+, Ubuntu 22.04+, Debian 12+)
- Python 3.10+
- [Ollama](https://ollama.com) installed and running:
  ```bash
  ollama pull qwen3.5:2b-q4_K_M
  ```

### 2. Installation
Clone the repository and set up dependencies:
```bash
git clone https://github.com/SURYA00714/brain.git
cd brain

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Launching Brain

#### Option A: Terminal GUI (Recommended)
```bash
./brain-app
# or
python3 brain_tui.py
```

#### Option B: Headless CLI Mode
```bash
python3 brain_cli.py "turn off bluetooth on this device"
```

#### Option C: Desktop Launcher
A `.desktop` entry is available at `~/.local/share/applications/brain.desktop` and on your Desktop, launchable with one click in a terminal window.

---

## 🧪 Verification & Test Suite

Brain includes an extensive automated test suite covering safety boundaries, multi-turn memory, universal reasoning, and deterministic tool execution:

```bash
# Run full 148-test regression suite
BRAIN_MOCK_GUI=1 python3 -m unittest tests/test_app_conversation.py \
    tests/test_phase22_intelligence.py \
    tests/test_phase21_universal.py \
    tests/test_phase19_reasoning.py \
    tests/test_phase18_adaptive.py \
    tests/test_phase17_1_hardening.py \
    tests/test_phase17_execution.py \
    tests/test_learning_pipeline.py \
    tests/test_gateway_hybrid.py \
    tests/test_memory_intelligence.py \
    tests/test_stage3_planning_constraints.py \
    tests/test_accuracy_engine.py \
    tests/test_controlled_execution.py \
    tests/test_cognitive_reasoning.py \
    tests/test_gateway.py \
    tests/test_phase18.py \
    tests/test_phase17.py \
    tests/test_phase17_1.py \
    tests/test_compound_agency.py
```

**Result: 148/148 Tests Passed in ~4.1 seconds (100% Success Rate).**

---

## 📂 Project Structure

```
├── brain-app                      # Shell executable wrapper for the TUI
├── brain_tui.py                   # Hacker-green Rich terminal interface
├── brain_cli.py                   # Command-line single-task execution interface
├── core/
│   ├── app_backend.py             # BrainAppCore: unified engine manager & router
│   ├── universal_reasoning.py     # DIRECT, ASSISTED, VERIFIED mode orchestrator
│   ├── cognition.py               # Cognitive engine, compound goal decomposition
│   ├── context.py                 # Dialogue short-term memory & ContextBuilder
│   ├── identity.py                # Brain persona & operational rules
│   ├── memory.py                  # Persistent SQLite long-term memory engine
│   └── world_state.py             # Physical hardware & app observation state
├── models/
│   ├── universal_adapter.py       # Normalized Ollama provider & model manager
│   ├── capability_profiler.py     # Empirical capability and latency profiler
│   └── needle_router.py           # 27MB fast semantic tool routing model
├── tools/
│   ├── router.py                  # FastRouter: sub-millisecond intent matcher
│   ├── registry.py                # Central verified tool registration hub
│   ├── apps.py                    # App lifecycle management & verification
│   ├── browser.py                 # Brave browser automation & navigation
│   ├── search.py                  # Structured DuckDuckGo live search scraper
│   └── system_control.py          # Wi-Fi, Bluetooth, Audio, Screen hardware tools
└── tests/                         # 148 automated unit & integration test files
```

---

## 📄 License
This project is open-source software licensed under the MIT License.
