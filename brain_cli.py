"""
Brain CLI — Interactive Console Interface.
Allows running reasoning and task execution directly from terminal without a browser.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.app_backend import default_app_core


def run_cli_loop():
    core = default_app_core
    print("=" * 65)
    print("🧠 BRAIN — AUTONOMOUS LOCAL REASONING & TASK EXECUTION ENGINE")
    print(f"Active Model: {core.active_model} | Mode: {core.current_mode}")
    print("Commands:")
    print("  /model <name>  - Switch model (e.g. /model qwen3.5-brain:v2)")
    print("  /models        - List available local models")
    print("  /mode <mode>   - Set mode (AUTO | DIRECT | ASSISTED | VERIFIED)")
    print("  /stats         - Show system RAM and model metrics")
    print("  /help          - Show this help message")
    print("  exit / quit    - Exit application")
    print("=" * 65)

    while True:
        try:
            line = input(f"\n[{core.active_model} | {core.current_mode}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Brain. Goodbye!")
            break

        if not line:
            continue

        low = line.lower()
        if low in ("exit", "quit", "q"):
            print("Exiting Brain. Goodbye!")
            break

        if low == "/models":
            print("\nAvailable Local Models:")
            for m in core.available_models:
                star = " *" if m == core.active_model else ""
                print(f"  - {m}{star}")
            continue

        if low.startswith("/model "):
            target = line.split(maxsplit=1)[1].strip()
            print(f"Switching model to '{target}'...")
            if core.switch_model(target):
                print(f"Successfully switched active model to {core.active_model}")
            else:
                print(f"Error: Model '{target}' not found. Use /models to see available models.")
            continue

        if low.startswith("/mode "):
            m_target = line.split(maxsplit=1)[1].strip().upper()
            if m_target in ("AUTO", "DIRECT", "ASSISTED", "VERIFIED"):
                core.set_execution_mode(m_target)
                print(f"Execution mode set to: {core.current_mode}")
            else:
                print("Error: Valid modes are AUTO, DIRECT, ASSISTED, VERIFIED")
            continue

        if low == "/stats":
            hw = core.get_hardware_status()
            print("\nHardware & Runtime Telemetry:")
            print(f"  Active Model: {hw['active_model']}")
            print(f"  Mode:         {hw['current_mode']}")
            print(f"  RAM Usage:    {hw['ram_used_mb']} MB / {hw['ram_total_mb']} MB ({hw['ram_percent']}%)")
            print(f"  CPU Load:     {hw['cpu_percent']}%")
            continue

        if low == "/help":
            print("\nEnter any task or reasoning question, or use commands: /models, /model, /mode, /stats, exit")
            continue

        # Execute task through Brain
        print("Brain: Thinking...", end="\r", flush=True)
        res = core.execute_task(line)
        print(" " * 20, end="\r")  # clear thinking line
        print(f"\nBrain ({res.get('mode', 'DIRECT')} | {res.get('strategy', 'N/A')} | {res.get('duration_ms', 0)}ms):")
        print(f"{res['text']}")


if __name__ == "__main__":
    run_cli_loop()
