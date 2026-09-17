import unittest
import json
import asyncio
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.protocol import ActionStatus, BRAIN_USABLE_EXPRESSIONS

class TestEmotionAction(unittest.TestCase):
    def test_invalid_emotion_rejected(self):
        bridge = DesktopMateBridge()
        res = bridge.set_emotion("invalid_expression_xyz")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.FAILED.value)
        self.assertIn("Unknown expression", res["error"])

    def test_emotion_when_disconnected(self):
        bridge = DesktopMateBridge()
        res = bridge.set_emotion("happy")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

    def test_usable_expressions_contains_standard(self):
        for emo in ["happy", "sad", "angry", "relaxed", "surprised", "neutral"]:
            self.assertIn(emo, BRAIN_USABLE_EXPRESSIONS)

if __name__ == "__main__":
    unittest.main()
