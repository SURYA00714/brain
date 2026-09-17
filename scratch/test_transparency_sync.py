import os
import sys
import time
from PIL import ImageGrab

sys.path.insert(0, os.path.abspath('.'))
from bridge.desktopmate_bridge import DesktopMateBridge

def main():
    bridge = DesktopMateBridge()
    bridge.start()
    print("Waiting for connection...")
    time.sleep(2)
    print("Checking health to trigger CheckRuntime (and transparency)...")
    res = bridge.send_and_wait("health", {})
    print("Health response:", res)
    
    print("Waiting for frame render...")
    time.sleep(3) 

    print("Taking screenshot...")
    img = ImageGrab.grab()
    img.save("/home/jai/.gemini/antigravity-ide/brain/c09f66f0-abd6-44a0-b95b-92dcdfdab97c/desktop_transparent_live.png")
    print("Saved screenshot with PIL.")
    bridge.stop()

if __name__ == "__main__":
    main()
