import re
import time
from pathlib import Path

try:
    from rapidocr_onnxruntime import RapidOCR
    _rapid_ocr_engine = RapidOCR()
    HAS_RAPID_OCR = True
except Exception:
    _rapid_ocr_engine = None
    HAS_RAPID_OCR = False


class ScreenElement:
    """Normalized abstraction for a visible UI element on screen."""
    def __init__(self, element_id, element_type, text="", x=0, y=0, width=0, height=0, confidence=1.0, is_sensitive=False):
        self.id = str(element_id)
        self.type = str(element_type).lower()  # button, text, input, link, checkbox, menu, icon, image, window, unknown
        self.text = str(text)
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.center_x = self.x + (self.width // 2) if self.width > 0 else self.x
        self.center_y = self.y + (self.height // 2) if self.height > 0 else self.y
        self.confidence = float(confidence)
        self.is_sensitive = bool(is_sensitive)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "confidence": self.confidence,
            "is_sensitive": self.is_sensitive
        }


class OCRProvider:
    """Interface / Base class for OCR text extraction."""
    def __init__(self):
        self.available = HAS_RAPID_OCR

    def extract_text(self, image_path):
        """
        Extracts visible text and bounding boxes from an image file.
        Returns standardized dict: {"success": bool, "status": str, "text": list, "regions": list}
        """
        if not self.available or not HAS_RAPID_OCR or not _rapid_ocr_engine:
            return {
                "success": True,
                "status": "OCR_NOT_AVAILABLE",
                "text": [],
                "regions": []
            }

        try:
            p = str(image_path)
            if not Path(p).exists():
                return {
                    "success": False,
                    "status": "IMAGE_NOT_FOUND",
                    "text": [],
                    "regions": []
                }

            result, _ = _rapid_ocr_engine(p)
            if not result:
                return {
                    "success": True,
                    "status": "OCR_ANALYZED",
                    "text": [],
                    "regions": []
                }

            texts = []
            regions = []
            for box, txt, score in result:
                # box is [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)

                texts.append(txt)
                regions.append({
                    "text": txt,
                    "x": int(x_min),
                    "y": int(y_min),
                    "width": int(x_max - x_min),
                    "height": int(y_max - y_min),
                    "confidence": float(score)
                })

            return {
                "success": True,
                "status": "OCR_ANALYZED",
                "text": texts,
                "regions": regions
            }
        except Exception as e:
            return {
                "success": False,
                "status": f"OCR_ERROR: {str(e)}",
                "text": [],
                "regions": []
            }


class BaseVisionProvider:
    """Base class for all vision analysis providers."""
    def __init__(self):
        self.status_name = "BASE_VISION"

    def analyze_screen(self, image_path, screen_width=1920, screen_height=1080):
        raise NotImplementedError("Subclasses must implement analyze_screen()")


class UnavailableVisionProvider(BaseVisionProvider):
    """Default fallback provider when no heavy vision model or OCR is loaded."""
    def __init__(self):
        super().__init__()
        self.status_name = "VISION_NOT_AVAILABLE"

    def analyze_screen(self, image_path, screen_width=1920, screen_height=1080):
        return {
            "success": True,
            "status": "VISION_NOT_AVAILABLE",
            "screen": {
                "width": screen_width,
                "height": screen_height
            },
            "elements": [],
            "image_path": str(image_path) if image_path else "",
            "timestamp": time.time(),
            "observation_id": f"obs_{int(time.time()*1000)}"
        }


class RemoteGUIVisionProvider(BaseVisionProvider):
    """
    Pluggable Remote GUI Vision Provider.
    Routes screen analysis through remote multimodal models (e.g. Gemini 2.5 Flash)
    without downloading a large local vision model.
    """
    def __init__(self, gateway=None):
        super().__init__()
        self.status_name = "REMOTE_GUI_VISION"
        from models.gateway import default_gateway
        self.gateway = gateway or default_gateway

    def analyze_screen(self, image_path, screen_width=1920, screen_height=1080):
        if not image_path or not Path(image_path).exists():
            return {
                "success": False,
                "status": "IMAGE_NOT_FOUND",
                "screen": {"width": screen_width, "height": screen_height},
                "elements": [],
                "image_path": str(image_path) if image_path else "",
                "timestamp": time.time(),
                "observation_id": f"obs_{int(time.time()*1000)}"
            }

        prompt = (
            "Analyze this GUI screenshot. Return a JSON array of detected interactive UI elements with keys:\n"
            "type ('button', 'input', 'link', 'text'), label, x (center int), y (center int), confidence (float).\n"
            "Return ONLY raw JSON object {\"elements\": [...]}.\n"
        )
        resp = self.gateway.generate(prompt, tier="DEEP", image_path=image_path, timeout=30.0)
        if not resp.success or not resp.text:
            return UnavailableVisionProvider().analyze_screen(image_path, screen_width, screen_height)

        try:
            import json, re
            raw = resp.text.strip()
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
            data = json.loads(raw)
            raw_elems = data.get("elements", [])
            elements = []
            for idx, e in enumerate(raw_elems, 1):
                if isinstance(e, dict):
                    x = int(e.get("x", 0))
                    y = int(e.get("y", 0))
                    lbl = str(e.get("label", f"element_{idx}"))
                    elem_type = str(e.get("type", "button")).lower()
                    elements.append({
                        "id": f"gui_elem_{idx}_{x}_{y}",
                        "type": elem_type,
                        "text": lbl,
                        "x": x - 20,
                        "y": y - 10,
                        "width": 40,
                        "height": 20,
                        "center_x": x,
                        "center_y": y,
                        "confidence": float(e.get("confidence", 0.9)),
                        "is_sensitive": False
                    })
            return {
                "success": True,
                "status": "REMOTE_GUI_VISION_ANALYZED",
                "screen": {"width": screen_width, "height": screen_height},
                "elements": elements,
                "image_path": str(image_path),
                "timestamp": time.time(),
                "observation_id": f"obs_{int(time.time()*1000)}"
            }
        except Exception:
            return UnavailableVisionProvider().analyze_screen(image_path, screen_width, screen_height)


class RapidOCRVisionProvider(BaseVisionProvider):
    """Real lightweight OCR vision provider backed by rapidocr-onnxruntime."""
    def __init__(self):
        super().__init__()
        self.status_name = "VISION_ANALYZED"
        self.ocr = OCRProvider()

    def analyze_screen(self, image_path, screen_width=1920, screen_height=1080):
        if not image_path or not Path(image_path).exists():
            return {
                "success": False,
                "status": "IMAGE_NOT_FOUND",
                "screen": {"width": screen_width, "height": screen_height},
                "elements": [],
                "image_path": str(image_path) if image_path else "",
                "timestamp": time.time(),
                "observation_id": f"obs_{int(time.time()*1000)}"
            }

        ocr_res = self.ocr.extract_text(image_path)
        if not ocr_res.get("success"):
            return {
                "success": False,
                "status": ocr_res.get("status", "OCR_FAILED"),
                "screen": {"width": screen_width, "height": screen_height},
                "elements": [],
                "image_path": str(image_path),
                "timestamp": time.time(),
                "observation_id": f"obs_{int(time.time()*1000)}"
            }

        elements = []
        sensitive_keywords = {"password", "passcode", "pin", "secret", "cvv", "ssn", "otp", "api_key", "apikey", "token"}

        for idx, reg in enumerate(ocr_res.get("regions", []), 1):
            txt = reg.get("text", "").strip()
            if not txt:
                continue

            clean_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", txt.lower()).strip("_")
            if not clean_slug:
                clean_slug = f"text_{idx}"

            x = reg.get("x", 0)
            y = reg.get("y", 0)
            w = reg.get("width", 0)
            h = reg.get("height", 0)
            cx = x + (w // 2)
            cy = y + (h // 2)
            conf = reg.get("confidence", 1.0)

            # Heuristic for element type
            elem_type = "text"
            lower_txt = txt.lower()
            if any(w in lower_txt for w in ["click", "submit", "ok", "cancel", "open", "save", "search", "login", "button"]):
                elem_type = "button"
            elif any(w in lower_txt for w in ["search...", "enter ", "type ", "input", "find..."]):
                elem_type = "input"

            is_sensitive = any(kw in lower_txt for kw in sensitive_keywords)
            display_text = "[REDACTED]" if is_sensitive else txt

            elem_id = f"elem_{elem_type}_{clean_slug}_{cx}_{cy}"
            elem_obj = ScreenElement(
                element_id=elem_id,
                element_type=elem_type,
                text=display_text,
                x=x,
                y=y,
                width=w,
                height=h,
                confidence=conf,
                is_sensitive=is_sensitive
            )
            elements.append(elem_obj.to_dict())

        return {
            "success": True,
            "status": "VISION_ANALYZED",
            "screen": {"width": screen_width, "height": screen_height},
            "elements": elements,
            "image_path": str(image_path),
            "timestamp": time.time(),
            "observation_id": f"obs_{int(time.time()*1000)}"
        }


class VisionProvider:
    """
    Central Manager for Visual Screen Understanding.
    Supports pluggable vision and OCR backends while maintaining strict resource bounds.
    """
    def __init__(self, active_provider=None, ocr_provider=None):
        if active_provider:
            self.active_provider = active_provider
        else:
            from models.gateway import default_gateway
            if default_gateway.get_provider("gemini").is_available():
                self.active_provider = RemoteGUIVisionProvider(gateway=default_gateway)
            elif HAS_RAPID_OCR:
                self.active_provider = RapidOCRVisionProvider()
            else:
                self.active_provider = UnavailableVisionProvider()

        self.ocr_provider = ocr_provider or OCRProvider()
        self._current_observation = None
        self._max_elements = 100

    def set_provider(self, provider):
        """Sets the active vision provider implementation."""
        if isinstance(provider, BaseVisionProvider):
            self.active_provider = provider

    def analyze_screen(self, image_path=None, screen_width=1920, screen_height=1080):
        """
        Analyzes a screen capture and stores a standardized observation.
        Ensures bounding and no fake data.
        """
        raw_res = self.active_provider.analyze_screen(
            image_path=image_path,
            screen_width=screen_width,
            screen_height=screen_height
        )

        elements = raw_res.get("elements", [])
        if len(elements) > self._max_elements:
            elements = elements[:self._max_elements]

        from tools.apps import default_app_tracker
        focused_app = default_app_tracker.get_focused_app() or "desktop"

        obs = {
            "success": raw_res.get("success", True),
            "status": raw_res.get("status", "VISION_NOT_AVAILABLE"),
            "screen": raw_res.get("screen", {"width": screen_width, "height": screen_height}),
            "elements": elements,
            "image_path": raw_res.get("image_path", str(image_path) if image_path else ""),
            "timestamp": raw_res.get("timestamp", time.time()),
            "observation_id": raw_res.get("observation_id", f"obs_{int(time.time()*1000)}"),
            "source_application": focused_app,
            "focused_application": focused_app
        }

        self._current_observation = obs
        return obs

    def get_current_observation(self):
        """Returns the most recent screen observation."""
        return self._current_observation

    def is_observation_fresh(self, max_age_seconds=15):
        """Checks if current stored observation is recent and valid."""
        if not self._current_observation:
            return False
        ts = self._current_observation.get("timestamp", 0)
        return (time.time() - ts) <= max_age_seconds

    def clear_observation(self):
        """Clears stored observation (e.g. after UI-modifying actions)."""
        self._current_observation = None

    def find_element(self, element_id_or_text):
        """
        Look up a UI element by ID or text match in the current observation.
        Returns ScreenElement dictionary, ambiguity dictionary, or None.
        """
        if not self._current_observation:
            return None

        query = str(element_id_or_text).lower().strip()
        if not query:
            return None

        elements = self._current_observation.get("elements", [])
        
        # 1. Exact ID match (unambiguous)
        for elem in elements:
            if isinstance(elem, dict):
                if str(elem.get("id", "")).lower() == query:
                    return elem

        # 2. Text matches (collect candidates to detect ambiguity)
        matches = []
        for elem in elements:
            if isinstance(elem, dict):
                e_text = str(elem.get("text", "")).lower()
                if query == e_text or (len(query) > 1 and query in e_text):
                    matches.append(elem)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Check if all matches have identical ID (exact duplicate object)
            first_id = matches[0].get("id")
            if all(m.get("id") == first_id for m in matches):
                return matches[0]
            # Ambiguous target detected
            return {"ambiguous": True, "query": element_id_or_text, "matches": matches}

        return None


# Global default vision manager instance
default_vision = VisionProvider()

