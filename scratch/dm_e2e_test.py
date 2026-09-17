import time
import logging
import os
import sys

# Add Brain root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.DEBUG)

from core.companion_state import default_companion_state, CompanionActivity

from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.companion_mode import default_companion_mode

# Connect bridge
bridge = DesktopMateBridge()
if not bridge.start():
    print("Bridge failed to start")
    exit(1)

# Ensure connected
for _ in range(50):
    if bridge.connected:
        break
    time.sleep(0.1)

print("Bridge connected:", bridge.connected)
default_companion_mode.set_mode("ACTIVE")

from brain import run_planner_task
print("Sending request: Open Brave and search for Python tutorials")
run_planner_task("Open Brave and search for Python tutorials.")

time.sleep(10)
print("Finished.")
bridge.stop()
