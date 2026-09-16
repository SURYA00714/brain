"""
Centralized Configuration Manager for Brain PC Assistant and Companion Layer.
Loads settings from config/companion.json with safe fallbacks and zero external dependencies.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "companion.json"

FALLBACK_CONFIG: Dict[str, Any] = {
    "avatar": {
        "enabled": True,
        "always_on_top": True,
        "click_through": False,
        "scale": 1.0,
        "theme": "dark_glass",
        "mouse_tracking": True,
        "port": 8765
    },
    "voice": {
        "enabled": True,
        "provider": "auto",
        "speed": 1.0,
        "natural_pauses": True
    },
    "presence": {
        "enabled": True,
        "poll_interval_sec": 3.0
    },
    "debug": {
        "enabled": False
    }
}


class CompanionConfig:
    """Manages persistent companion configuration settings."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """Loads configuration from JSON file, falling back to defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                return
            except Exception:
                pass
        self._data = dict(FALLBACK_CONFIG)

    def save(self) -> bool:
        """Persists current settings to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            return True
        except Exception:
            return False

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        sec_data = self._data.get(section, {})
        if key is None:
            return sec_data
        if isinstance(sec_data, dict):
            return sec_data.get(key, default)
        return default

    @property
    def avatar(self):
        class SectionView:
            def __init__(self, data):
                self.__dict__.update(data)
            def get(self, k, default=None):
                return getattr(self, k, default)
        return SectionView(self._data.get("avatar", {}))

    @property
    def voice(self):
        class SectionView:
            def __init__(self, data):
                self.__dict__.update(data)
            def get(self, k, default=None):
                return getattr(self, k, default)
        return SectionView(self._data.get("voice", {}))

    @property
    def presence(self):
        class SectionView:
            def __init__(self, data):
                self.__dict__.update(data)
            def get(self, k, default=None):
                return getattr(self, k, default)
        return SectionView(self._data.get("presence", {}))


default_config = CompanionConfig()
companion_config = default_config

