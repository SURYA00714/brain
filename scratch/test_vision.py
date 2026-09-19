import json
import time
from tools.vision import default_vision, RemoteGUIVisionProvider
from tools.screen import capture_screen

def test():
    print("Capturing screen...")
    res = capture_screen()
    image_path = res.get("image_path") if res.get("success") else None
    if not image_path:
        print("Failed to capture screen.")
        return

    from models.gateway import default_gateway
    print("Testing direct Gateway call...")
    resp = default_gateway.generate("Test vision", tier="DEEP", image_path=image_path)
    print("Response Success:", resp.success)
    if not resp.success:
        print("Response Error:", resp.error)
        print("Cloud attempted:", resp.cloud_attempted)
        print("Cloud failure reason:", resp.cloud_failure_reason)

    print("Analyzing screen with Gemini...")
    obs = default_vision.analyze_screen(image_path)
    
    print("Observation Status:", obs.get("status"))
    print("Provider used:", default_vision.active_provider.status_name)
    print("Found elements:", len(obs.get("elements", [])))
    
    if obs.get("elements"):
        print("Sample element:", obs["elements"][0])

if __name__ == "__main__":
    from models.gateway import _load_dotenv_if_present
    _load_dotenv_if_present()
    test()
