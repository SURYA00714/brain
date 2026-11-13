"""
Brain AI — Main Entrypoint.
Executes Brain Terminal GUI (TUI) with ASCII art, emojis, and green font aesthetics.
Strictly local intelligence — No Yui or Aoi companion code.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ("--help",):
        # Direct one-shot prompt
        from core.app_backend import default_app_core
        query = " ".join(sys.argv[1:])
        res = default_app_core.execute_task(query)
        print(f"[{res.get('mode', 'DIRECT')} | {res.get('strategy', 'N/A')}] {res.get('text', '')}")
    else:
        # Launch Terminal GUI
        from brain_tui import run_terminal_gui
        run_terminal_gui()


if __name__ == "__main__":
    main()
