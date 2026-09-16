# Brain - Desktop AI Companion

Brain is a lightweight, persistent, computer-native AI companion living on your PC. It understands your intent, controls the computer using local deterministic tools, reasons using a multi-model cognitive engine (Groq, Gemini, local Ollama fallback), and includes a desktop avatar UI.

## Features
- **Local Control Layer:** Executes PC actions (opening apps, managing files, browser automation) deterministically for sub-second response times.
- **Cognitive Gateway:** Intelligently routes complex requests to cloud LLMs (Groq, Gemini) and falls back to local models when offline.
- **Desktop Companion UI:** A persistent background avatar (via HTTP SSE) that provides visual feedback, mood/state changes, and voice synthesis.
- **Safety & Verification:** Red-team tested epistemic safety checks, self-healing recovery strategies, and strict tool boundaries.
- **Telemetry & Profiling:** Comprehensive JSONL logs tracking token usage, latencies, and tool invocation.

## Setup
1. Create virtual environment: `python3 -m venv .venv`
2. Install requirements: `pip install -r requirements.txt` (or manually install dependencies like `psutil`, `pyautogui`, `requests`, `playwright`, etc).
3. Setup API Keys:
   ```bash
   export GROQ_API_KEY="your-groq-key"
   export GEMINI_API_KEY="your-gemini-key"
   ```
4. Run Brain:
   - CLI Mode: `./.venv/bin/python3 brain.py`
   - Companion UI Mode: `./.venv/bin/python3 brain.py --companion`
