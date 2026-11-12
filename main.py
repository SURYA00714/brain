"""
YUI Root Entrypoint
Delegates execution to yui.main.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from yui.main import verify_ground_and_travel_frame_system

if __name__ == "__main__":
    verify_ground_and_travel_frame_system()
