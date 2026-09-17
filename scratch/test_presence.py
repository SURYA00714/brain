import sys
import logging
logging.basicConfig(level=logging.DEBUG)
from core.desktop_presence import DesktopPresenceManager
mgr = DesktopPresenceManager()
win_id = mgr.get_window_id()
if win_id:
    print(f"Applying presence to {win_id}")
    mgr.apply_desktop_presence(win_id)
else:
    print("No window found")
