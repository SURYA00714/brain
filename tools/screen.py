import os
import time
from pathlib import Path

try:
    from mss import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except (ImportError, SystemExit):
    HAS_PYAUTOGUI = False


DEFAULT_SCREENSHOT_PATH = Path("/home/jai/Downloads/Brain/logs/screen_temp.png")


def capture_screen(output_path=None):
    """
    Captures the current desktop screen.
    Overwrites a single controlled temporary file to prevent unbounded SSD storage accumulation.
    Returns structured dict with image path, dimensions, and timestamp.
    """
    if output_path is None:
        target_file = DEFAULT_SCREENSHOT_PATH
    else:
        target_file = Path(output_path)

    # Ensure parent directory exists
    target_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if HAS_MSS:
            with mss() as sct:
                monitor = sct.monitors[0]  # Full desktop
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.save(target_file)
                width, height = sct_img.width, sct_img.height
        elif HAS_PYAUTOGUI:
            screenshot = pyautogui.screenshot()
            screenshot.save(target_file)
            width, height = screenshot.size
        else:
            return "Error: No screen capture library (mss/pyautogui) available."

        return {
            "image_path": str(target_file.resolve()),
            "width": width,
            "height": height,
            "timestamp": timestamp
        }
    except Exception as e:
        return f"Error capturing screen: {str(e)}"


from tools.vision import default_vision, VisionProvider


def analyze_captured_screen(image_path=None):
    """
    Captures screen if image_path is missing, then analyzes using default_vision.
    Returns structured screen observation dict.
    """
    if not image_path or not Path(image_path).exists():
        capture_res = capture_screen()
        if isinstance(capture_res, str) and capture_res.startswith("Error:"):
            return {
                "success": False,
                "status": "ERROR",
                "screen": {"width": 1920, "height": 1080},
                "elements": [],
                "image_path": "",
                "error": capture_res
            }
        image_path = capture_res.get("image_path")
        w, h = capture_res.get("width", 1920), capture_res.get("height", 1080)
    else:
        w, h = 1920, 1080

    return default_vision.analyze_screen(image_path=image_path, screen_width=w, screen_height=h)

