"""
Brain ↔ Desktop Mate Protocol Layer (v1).

Defines the versioned message protocol, capability registry,
action validation, and VRM 1.0 expression mapping.

RULE: Never fake success. Every capability must be discovered, not assumed.
"""

import uuid
import time
from enum import Enum
from typing import Dict, Any, Optional, List


# ---------------------------------------------------------------------------
# Protocol Constants
# ---------------------------------------------------------------------------

PROTOCOL_NAME = "brain-desktopmate"
PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 8192  # 8 KB hard limit


class ActionStatus(str, Enum):
    """Honest result statuses for bridge actions."""
    SUCCESS = "success"                     # Action executed AND verified
    EXECUTED_UNVERIFIED = "executed_unverified"  # Action sent, no runtime confirmation
    FAILED = "failed"                       # Action attempted, explicit failure
    UNAVAILABLE = "unavailable"             # Capability not present
    NOT_CONNECTED = "not_connected"         # Bridge WS not connected
    NOT_IMPLEMENTED = "not_implemented"     # Stub — no runtime adapter yet
    BLOCKED_BY_ENVIRONMENT = "blocked_by_environment"  # e.g. Wine/Linux limitation


class CapabilityStatus(str, Enum):
    """Discovery status for each capability category."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"
    BLOCKED_BY_ENVIRONMENT = "blocked_by_environment"


# ---------------------------------------------------------------------------
# VRM 1.0 Standard Expression Presets
# ---------------------------------------------------------------------------

VRM10_EXPRESSIONS = {
    # Emotions (verified present in Desktop Mate VRM10 metadata)
    "happy":     {"type": "emotion", "vrm_key": "happy"},
    "angry":     {"type": "emotion", "vrm_key": "angry"},
    "sad":       {"type": "emotion", "vrm_key": "sad"},
    "relaxed":   {"type": "emotion", "vrm_key": "relaxed"},
    "surprised": {"type": "emotion", "vrm_key": "surprised"},
    # Neutral is achieved by setting all expression weights to 0
    "neutral":   {"type": "reset",   "vrm_key": None},
    # Visemes (for lip-sync — controlled by uLipSync, not direct Brain control)
    "aa":        {"type": "viseme",  "vrm_key": "aa"},
    "ih":        {"type": "viseme",  "vrm_key": "ih"},
    "ou":        {"type": "viseme",  "vrm_key": "ou"},
    "ee":        {"type": "viseme",  "vrm_key": "ee"},
    "oh":        {"type": "viseme",  "vrm_key": "oh"},
    # Blink
    "blink":     {"type": "blink",   "vrm_key": "blink"},
}

# Emotions that Brain's reaction engine may use
BRAIN_USABLE_EXPRESSIONS = {"happy", "angry", "sad", "relaxed", "surprised", "neutral"}


# ---------------------------------------------------------------------------
# Known Actions
# ---------------------------------------------------------------------------

KNOWN_ACTIONS = {
    "health",
    "capabilities",
    "set_emotion",
    "play_animation",
    "look_at",
    "play_voice",
    "get_character_state",
}

# Required parameters per action
ACTION_PARAMS: Dict[str, List[str]] = {
    "health": [],
    "capabilities": [],
    "set_emotion": ["emotion"],
    "play_animation": ["name"],
    "look_at": ["target"],
    "play_voice": ["file"],
    "get_character_state": [],
}


# ---------------------------------------------------------------------------
# Protocol Message Builders
# ---------------------------------------------------------------------------

def make_request(action: str, arguments: Optional[Dict[str, Any]] = None,
                 request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a protocol-compliant request envelope."""
    return {
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "request_id": request_id or str(uuid.uuid4())[:8],
        "action": action,
        "arguments": arguments or {},
    }


def make_response(request_id: str, action: str, success: bool,
                  data: Optional[Dict[str, Any]] = None,
                  error: Optional[Dict[str, str]] = None,
                  status: Optional[str] = None) -> Dict[str, Any]:
    """Build a protocol-compliant response envelope."""
    resp = {
        "protocol": PROTOCOL_NAME,
        "version": PROTOCOL_VERSION,
        "request_id": request_id,
        "action": action,
        "success": success,
    }
    if status:
        resp["status"] = status
    if data is not None:
        resp["data"] = data
    if error is not None:
        resp["error"] = error
    return resp


def make_error_response(request_id: str, action: str,
                        code: str, message: str) -> Dict[str, Any]:
    """Build a protocol-compliant error response."""
    return make_response(
        request_id=request_id,
        action=action,
        success=False,
        error={"code": code, "message": message},
        status=ActionStatus.FAILED.value,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_request(msg: Dict[str, Any]) -> Optional[str]:
    """
    Validate an incoming request envelope.
    Returns None if valid, or an error string if invalid.
    """
    if not isinstance(msg, dict):
        return "Message must be a JSON object"

    if msg.get("protocol") != PROTOCOL_NAME:
        return f"Unknown protocol: {msg.get('protocol')}"

    version = msg.get("version")
    if version != PROTOCOL_VERSION:
        return f"Unsupported protocol version: {version}"

    action = msg.get("action")
    if not action or not isinstance(action, str):
        return "Missing or invalid 'action' field"

    if action not in KNOWN_ACTIONS:
        return f"Unknown action: {action}"

    # Validate required parameters
    required = ACTION_PARAMS.get(action, [])
    arguments = msg.get("arguments", {})
    if not isinstance(arguments, dict):
        return "'arguments' must be a JSON object"

    for param in required:
        if param not in arguments:
            return f"Missing required parameter '{param}' for action '{action}'"

    return None


def validate_response(msg: Dict[str, Any]) -> Optional[str]:
    """Validate a response envelope. Returns None if valid, error string otherwise."""
    if not isinstance(msg, dict):
        return "Response must be a JSON object"
    if msg.get("protocol") != PROTOCOL_NAME:
        return f"Unknown protocol: {msg.get('protocol')}"
    if "success" not in msg:
        return "Missing 'success' field"
    if "request_id" not in msg:
        return "Missing 'request_id' field"
    return None


# ---------------------------------------------------------------------------
# Capability Registry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """
    Tracks which Desktop Mate capabilities are actually available.
    Starts empty — capabilities are populated only via runtime discovery.
    """

    def __init__(self):
        self._capabilities: Dict[str, Dict[str, Any]] = {}
        self._last_discovery: float = 0.0

    def set_capability(self, name: str, status: CapabilityStatus,
                       details: Optional[Dict[str, Any]] = None):
        self._capabilities[name] = {
            "status": status.value,
            "details": details or {},
            "discovered_at": time.time(),
        }

    def get_capability(self, name: str) -> Optional[Dict[str, Any]]:
        return self._capabilities.get(name)

    def is_available(self, name: str) -> bool:
        cap = self._capabilities.get(name)
        return cap is not None and cap["status"] == CapabilityStatus.VERIFIED.value

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._capabilities)

    def clear(self):
        self._capabilities.clear()
        self._last_discovery = 0.0

    def mark_discovery_done(self):
        self._last_discovery = time.time()

    @property
    def last_discovery_age(self) -> float:
        if self._last_discovery == 0.0:
            return float("inf")
        return time.time() - self._last_discovery
