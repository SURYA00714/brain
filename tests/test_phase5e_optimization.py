import os
import unittest
from core.desktop_presence import DesktopPresenceManager
from bridge.desktopmate_bridge import DesktopMateBridge
from bridge.protocol import ActionStatus

class TestPhase5EOptimization(unittest.TestCase):
    def test_memory_usage_mb_returns_float(self):
        dpm = DesktopPresenceManager()
        mem = dpm.get_memory_usage_mb()
        self.assertIsInstance(mem, float)
        self.assertGreaterEqual(mem, 0.0)

    def test_trim_memory_when_disconnected(self):
        bridge = DesktopMateBridge()
        res = bridge.trim_memory()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

    def test_set_fps_when_disconnected(self):
        bridge = DesktopMateBridge()
        res = bridge.set_fps(15)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], ActionStatus.NOT_CONNECTED.value)

if __name__ == "__main__":
    unittest.main()
