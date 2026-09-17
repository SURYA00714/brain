import mss
import os
import sys

def main():
    try:
        with mss.mss() as sct:
            sct.shot(output="/home/jai/.gemini/antigravity-ide/brain/c09f66f0-abd6-44a0-b95b-92dcdfdab97c/desktop_transparent.png")
            print("Screenshot saved via mss.")
    except Exception as e:
        print("mss failed:", e)

if __name__ == "__main__":
    main()
