import unittest
import time
from bridge.protocol import (
    PROTOCOL_NAME, PROTOCOL_VERSION,
    ActionStatus, CapabilityStatus, CapabilityRegistry,
    make_request, make_response, make_error_response,
    validate_request, validate_response
)

class TestBridgeProtocol(unittest.TestCase):
    def test_make_request(self):
        req = make_request("health", {"param": 1})
        self.assertEqual(req["protocol"], PROTOCOL_NAME)
        self.assertEqual(req["version"], PROTOCOL_VERSION)
        self.assertEqual(req["action"], "health")
        self.assertEqual(req["arguments"], {"param": 1})
        self.assertIn("request_id", req)

    def test_validate_valid_request(self):
        req = make_request("health", {})
        self.assertIsNone(validate_request(req))

    def test_validate_invalid_request(self):
        req = make_request("set_emotion", {})  # Missing required param
        err = validate_request(req)
        self.assertIsNotNone(err)
        self.assertIn("Missing required parameter", err)

        req = {"action": "health"}  # Missing protocol
        self.assertIsNotNone(validate_request(req))

    def test_make_response(self):
        resp = make_response("req-123", "health", True, data={"ok": True})
        self.assertTrue(resp["success"])
        self.assertEqual(resp["request_id"], "req-123")
        self.assertEqual(resp["data"], {"ok": True})

    def test_capability_registry(self):
        reg = CapabilityRegistry()
        self.assertFalse(reg.is_available("health"))
        
        reg.set_capability("health", CapabilityStatus.VERIFIED)
        self.assertTrue(reg.is_available("health"))
        
        reg.set_capability("animation", CapabilityStatus.UNAVAILABLE)
        self.assertFalse(reg.is_available("animation"))
        
        reg.clear()
        self.assertFalse(reg.is_available("health"))

if __name__ == "__main__":
    unittest.main()
