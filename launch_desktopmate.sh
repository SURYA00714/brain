#!/bin/bash
cd /home/jai/Downloads/Brain
source .venv/bin/activate
python3 -c "import sys; sys.path.insert(0, '.'); from core.desktop_presence import DesktopPresenceManager; DesktopPresenceManager().ensure_running()"
