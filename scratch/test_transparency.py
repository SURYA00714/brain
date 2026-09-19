import time
import subprocess
import os
import signal

print("Killing old instances...")
os.system("killall -9 DesktopMate.exe 2>/dev/null")
os.system("killall -9 desktopmate.exe 2>/dev/null")
time.sleep(1)

print("Launching Desktop Mate...")
proc = subprocess.Popen(["/home/jai/Downloads/Brain/launch_desktopmate.sh"])
time.sleep(10) # wait for Unity and Proton to load

print("Taking screenshot...")
from PIL import ImageGrab
img = ImageGrab.grab()
img.save('desktop_transparent_live.png')
print("Screenshot taken.")
