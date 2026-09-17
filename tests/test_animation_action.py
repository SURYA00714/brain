import unittest
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.protocol import ActionStatus

class TestAnimationAction(unittest.TestCase):
    def test_invalid_animation_rejected(self):
        bridge = DesktopMateBridge()
        res = bridge.play_animation("")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.FAILED.value)

    def test_animation_when_disconnected(self):
        bridge = DesktopMateBridge()
        res = bridge.play_animation("idle")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

if __name__ == "__main__":
    unittest.main()
