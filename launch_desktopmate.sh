#!/bin/bash
cd /home/jai/Downloads/Brain
exec /usr/bin/nohup /home/jai/Downloads/Brain/.venv/bin/python3 -u -c "import sys, logging; logging.basicConfig(level=logging.INFO); sys.path.insert(0, '/home/jai/Downloads/Brain'); from core.desktop_presence import DesktopPresenceManager; DesktopPresenceManager().ensure_running()" > /tmp/desktopmate_launch.log 2>&1 &
