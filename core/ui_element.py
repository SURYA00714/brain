"""
Brain Semantic UI Element Abstraction (Stage 8C).
Provides structured UI element representations with roles, labels, bounding boxes, sources, and confidence.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List


VALID_ROLES = {
    "button", "textbox", "link", "checkbox", "menu", "icon", "text", "dropdown", "tab", "unknown"
}

VALID_ELEMENT_SOURCES = {
    "OCR", "BROWSER_DOM", "ACCESSIBILITY", "WINDOW_METADATA", "VISION_MODEL", "HEURISTIC"
}


@dataclass
class UIElement:
    """Structured, evidence-grounded semantic representation of a UI element."""
    id: str
    role: str = "unknown"             # button, textbox, link, icon, text, etc.
    label: str = ""                   # Accessible label or button text
    text: str = ""                    # Display text content
    bounds: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "width": 0, "height": 0})
    enabled: bool = True
    visible: bool = True
    focused: bool = False
    source: str = "OCR"               # OCR, BROWSER_DOM, ACCESSIBILITY, etc.
    confidence: float = 1.0

    def center_coordinates(self) -> Dict[str, int]:
        """Calculates center x, y click coordinates from bounds."""
        cx = self.bounds.get("x", 0) + (self.bounds.get("width", 0) // 2)
        cy = self.bounds.get("y", 0) + (self.bounds.get("height", 0) // 2)
        return {"x": cx, "y": cy}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["center"] = self.center_coordinates()
        return d
