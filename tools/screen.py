import os
import subprocess
import time
from pathlib import Path

try:
    from mss import MSS as mss
    HAS_MSS = True
except ImportError:
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


DEFAULT_SCREENSHOT_PATH = Path("/home/jai/Downloads/Brain/scratch/screen_temp.png")


def cleanup_screenshots(keep_latest: bool = True):
    """
    Cleans up temporary screen capture files to enforce bounded SSD storage.
    If keep_latest is True, retains only DEFAULT_SCREENSHOT_PATH and deletes any other temp images.
    """
    scratch_dir = DEFAULT_SCREENSHOT_PATH.parent
    if not scratch_dir.exists():
        return

    for img_file in scratch_dir.glob("screen_*.png"):
        if keep_latest and img_file.resolve() == DEFAULT_SCREENSHOT_PATH.resolve():
            continue
        try:
            img_file.unlink(missing_ok=True)
        except Exception:
            pass


def get_screen_metadata():
    """
    Deterministically gathers screen dimensions, workspace info, and display geometry.
    Returns structured dict.
    """
    width, height = 1920, 1080
    if HAS_MSS:
        try:
            with mss() as sct:
                mon = sct.monitors[0]
                width, height = mon["width"], mon["height"]
        except Exception:
            pass
    elif HAS_PYAUTOGUI:
        try:
            w, h = pyautogui.size()
            width, height = int(w), int(h)
        except Exception:
            pass

    workspace = "1"
    if os.environ.get("BRAIN_MOCK_GUI") != "1":
        try:
            res = subprocess.run(["wmctrl", "-d"], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "*" in line:
                        parts = line.split()
                        if parts:
                            workspace = parts[0]
                        break
        except Exception:
            pass

    return {
        "screen": {
            "width": width,
            "height": height,
            "workspace": workspace
        }
    }


def capture_screen(output_path=None):
    """
    Captures the current desktop screen.
    Overwrites a single controlled temporary file to prevent unbounded SSD storage accumulation.
    Returns structured dict with image path, dimensions, timestamp, and tool metadata.
    """
    if output_path is None:
        target_file = DEFAULT_SCREENSHOT_PATH
    else:
        target_file = Path(output_path)

    # Ensure parent directory exists
    target_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if not HAS_MSS and not HAS_PYAUTOGUI and os.environ.get("BRAIN_MOCK_GUI") != "1":
        err_msg = "Unable to capture X11 screen: No capture backend (mss/pyautogui) available"
        return {
            "success": False,
            "tool": "SCREENSHOT",
            "data": None,
            "image_path": "",
            "error": err_msg
        }

    if os.environ.get("BRAIN_MOCK_GUI") == "1":
        try:
            from PIL import Image
            img = Image.new("RGB", (1920, 1080), color=(240, 240, 240))
            img.save(target_file)
            img_resolved = str(target_file.resolve())
            return {
                "success": True,
                "tool": "SCREENSHOT",
                "image_path": img_resolved,
                "width": 1920,
                "height": 1080,
                "timestamp": timestamp,
                "data": {
                    "image_path": img_resolved,
                    "width": 1920,
                    "height": 1080,
                    "timestamp": timestamp
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "tool": "SCREENSHOT",
                "data": None,
                "image_path": "",
                "error": f"Mock capture failed: {str(e)}"
            }

    try:
        width, height = 1920, 1080
        if HAS_MSS:
            with mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                from PIL import Image
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.save(target_file)
                width, height = sct_img.width, sct_img.height
        elif HAS_PYAUTOGUI:
            screenshot = pyautogui.screenshot()
            screenshot.save(target_file)
            width, height = screenshot.size

        img_resolved = str(target_file.resolve())
        return {
            "success": True,
            "tool": "SCREENSHOT",
            "image_path": img_resolved,
            "width": width,
            "height": height,
            "timestamp": timestamp,
            "data": {
                "image_path": img_resolved,
                "width": width,
                "height": height,
                "timestamp": timestamp
            },
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "SCREENSHOT",
            "data": None,
            "image_path": "",
            "error": f"Error capturing screen: {str(e)}"
        }


from tools.vision import default_vision, VisionProvider


def analyze_captured_screen(image_path=None, force_refresh=False):
    """
    Captures screen if image_path is missing, then analyzes using default_vision.
    Returns structured screen observation dict.
    If a fresh observation exists in default_vision and force_refresh is False,
    returns the cached observation to avoid redundant OCR computation.
    """
    if not force_refresh and not image_path and default_vision.is_observation_fresh(max_age_seconds=15):
        existing_obs = default_vision.get_current_observation()
        if existing_obs:
            res = dict(existing_obs)
            res["success"] = True
            res["tool"] = "ANALYZE_SCREEN"
            res["data"] = existing_obs
            res["error"] = None
            return res

    if not image_path or not Path(image_path).exists():
        capture_res = capture_screen()
        if not capture_res.get("success"):
            try:
                from PIL import Image
                temp_path = DEFAULT_SCREENSHOT_PATH
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (1920, 1080), color=(240, 240, 240))
                img.save(temp_path)
                image_path = str(temp_path.resolve())
                w, h = 1920, 1080
            except Exception:
                from tools.apps import default_app_tracker
                focused_app = default_app_tracker.get_focused_app() or "unknown"
                return {
                    "success": False,
                    "tool": "ANALYZE_SCREEN",
                    "status": "ERROR",
                    "screen": {"width": 1920, "height": 1080},
                    "elements": [],
                    "image_path": "",
                    "data": None,
                    "error": capture_res.get("error", "Failed to capture screen"),
                    "focused_application": focused_app,
                    "source_application": focused_app
                }
        else:
            image_path = capture_res.get("image_path")
            w, h = capture_res.get("width", 1920), capture_res.get("height", 1080)
    else:
        w, h = 1920, 1080

    obs = default_vision.analyze_screen(image_path=image_path, screen_width=w, screen_height=h)
    from core.perception import default_perception_router
    perc = default_perception_router.perceive(image_path=image_path, force_refresh=force_refresh)
    res = dict(obs)
    res["success"] = obs.get("success", True)
    res["tool"] = "ANALYZE_SCREEN"
    res["data"] = obs
    res["perception"] = perc.to_dict()
    res["screen_state"] = perc.screen_state
    res["error"] = None
    return res



