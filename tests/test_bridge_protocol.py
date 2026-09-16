import pytest
import time
from bridge.protocol import (
    PROTOCOL_NAME, PROTOCOL_VERSION,
    ActionStatus, CapabilityStatus, CapabilityRegistry,
    make_request, make_response, make_error_response,
    validate_request, validate_response
)

def test_make_request():
    req = make_request("health", {"param": 1})
    assert req["protocol"] == PROTOCOL_NAME
    assert req["version"] == PROTOCOL_VERSION
    assert req["action"] == "health"
    assert req["arguments"] == {"param": 1}
    assert "request_id" in req

def test_validate_valid_request():
    req = make_request("health", {})
    assert validate_request(req) is None

def test_validate_invalid_request():
    req = make_request("set_emotion", {})  # Missing required param
    err = validate_request(req)
    assert err is not None
    assert "Missing required parameter" in err

    req = {"action": "health"}  # Missing protocol
    assert validate_request(req) is not None

def test_make_response():
    resp = make_response("req-123", "health", True, data={"ok": True})
    assert resp["success"] is True
    assert resp["request_id"] == "req-123"
    assert resp["data"] == {"ok": True}

def test_capability_registry():
    reg = CapabilityRegistry()
    assert not reg.is_available("health")
    
    reg.set_capability("health", CapabilityStatus.VERIFIED)
    assert reg.is_available("health")
    
    reg.set_capability("animation", CapabilityStatus.UNAVAILABLE)
    assert not reg.is_available("animation")
    
    reg.clear()
    assert not reg.is_available("health")
