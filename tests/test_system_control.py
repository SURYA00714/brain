import os
import unittest
from unittest.mock import patch
from tools.system_control import (
    volume_up, volume_down, volume_mute,
    brightness_up, brightness_down, lock_screen,
    wifi_status, wifi_on, wifi_off,
    bluetooth_status, bluetooth_on, bluetooth_off,
    get_system_info, memory_status, disk_status, cpu_status,
    shutdown, restart, suspend, logout,
    PowerOperationError, ConfirmationRequiredError
)
from tools.router import FastRouter, default_router
from tools.registry import default_registry

class TestSystemControl(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_MOCK_GUI"] = "1"

    def test_audio_and_display_tools(self):
        v_up = volume_up(5)
        self.assertTrue(v_up["success"])
        self.assertEqual(v_up["tool"], "VOLUME_UP")

        v_down = volume_down(5)
        self.assertTrue(v_down["success"])
        self.assertEqual(v_down["tool"], "VOLUME_DOWN")

        v_mute = volume_mute()
        self.assertTrue(v_mute["success"])
        self.assertEqual(v_mute["tool"], "VOLUME_MUTE")

        b_up = brightness_up(10)
        self.assertTrue(b_up["success"])
        self.assertEqual(b_up["tool"], "BRIGHTNESS_UP")

        b_down = brightness_down(10)
        self.assertTrue(b_down["success"])
        self.assertEqual(b_down["tool"], "BRIGHTNESS_DOWN")

        lock = lock_screen()
        self.assertTrue(lock["success"])
        self.assertEqual(lock["tool"], "LOCK_SCREEN")

    def test_network_tools(self):
        w_stat = wifi_status()
        self.assertTrue(w_stat["success"])
        self.assertEqual(w_stat["tool"], "WIFI_STATUS")

        w_on = wifi_on()
        self.assertTrue(w_on["success"])

        w_off = wifi_off()
        self.assertTrue(w_off["success"])

        bt_stat = bluetooth_status()
        self.assertTrue(bt_stat["success"])

        bt_on = bluetooth_on()
        self.assertTrue(bt_on["success"])

        bt_off = bluetooth_off()
        self.assertTrue(bt_off["success"])

    def test_system_info_and_metrics(self):
        sys_info = get_system_info()
        self.assertTrue(sys_info["success"])
        self.assertIn("Linux", sys_info["data"])

        mem = memory_status()
        self.assertTrue(mem["success"])

        disk = disk_status("/")
        self.assertTrue(disk["success"])

        cpu = cpu_status()
        self.assertTrue(cpu["success"])

    def test_confirmation_gated_power_operations(self):
        s = shutdown(confirmed=True)
        self.assertTrue(s["success"])
        self.assertEqual(s["tool"], "SHUTDOWN")

        r = restart(confirmed=True)
        self.assertTrue(r["success"])
        self.assertEqual(r["tool"], "RESTART")

        sp = suspend(confirmed=True)
        self.assertTrue(sp["success"])
        self.assertEqual(sp["tool"], "SUSPEND")

        l = logout(confirmed=True)
        self.assertTrue(l["success"])
        self.assertEqual(l["tool"], "LOGOUT")

    def test_power_operation_exceptions(self):
        # Temporarily clear BRAIN_MOCK_GUI to test explicit exception raising when raise_on_confirmation is requested
        with patch.dict(os.environ, {"BRAIN_MOCK_GUI": "0", "BRAIN_NO_POWER_OPS": "0"}):
            with self.assertRaises(ConfirmationRequiredError):
                shutdown(confirmed=False, raise_on_confirmation=True)
            with self.assertRaises(ConfirmationRequiredError):
                restart(confirmed=False, raise_on_confirmation=True)
            with self.assertRaises(ConfirmationRequiredError):
                suspend(confirmed=False, raise_on_confirmation=True)
            with self.assertRaises(ConfirmationRequiredError):
                logout(confirmed=False, raise_on_confirmation=True)

    def test_registry_integration(self):
        registered_tools = [t["name"] for t in default_registry.list_tools()]
        expected = [
            "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
            "BRIGHTNESS_UP", "BRIGHTNESS_DOWN", "LOCK_SCREEN",
            "WIFI_STATUS", "WIFI_ON", "WIFI_OFF",
            "BLUETOOTH_STATUS", "BLUETOOTH_ON", "BLUETOOTH_OFF",
            "SYSTEM_INFO", "MEMORY_STATUS", "DISK_STATUS", "CPU_STATUS",
            "SHUTDOWN", "RESTART", "SUSPEND", "LOGOUT"
        ]
        for t in expected:
            self.assertIn(t, registered_tools, f"Tool {t} not found in ToolRegistry.")

    def test_fast_router_zero_llm(self):
        router = FastRouter()
        queries = [
            ("volume up", "VOLUME_UP"),
            ("volume down", "VOLUME_DOWN"),
            ("mute", "VOLUME_MUTE"),
            ("brightness up", "BRIGHTNESS_UP"),
            ("brightness down", "BRIGHTNESS_DOWN"),
            ("lock screen", "LOCK_SCREEN"),
            ("wifi status", "WIFI_STATUS"),
            ("wifi on", "WIFI_ON"),
            ("wifi off", "WIFI_OFF"),
            ("bluetooth status", "BLUETOOTH_STATUS"),
            ("bluetooth on", "BLUETOOTH_ON"),
            ("bluetooth off", "BLUETOOTH_OFF"),
            ("system info", "SYSTEM_INFO"),
            ("memory status", "MEMORY_STATUS"),
            ("disk status", "DISK_STATUS"),
            ("cpu status", "CPU_STATUS"),
            ("shutdown", "SHUTDOWN"),
            ("restart", "RESTART"),
            ("reboot", "RESTART"),
            ("suspend", "SUSPEND"),
            ("sleep", "SUSPEND"),
            ("logout", "LOGOUT")
        ]
        for text, expected_tool in queries:
            res = router.route(text)
            self.assertIsNotNone(res, f"Failed to route: {text}")
            self.assertEqual(res.get("type"), "tool")
            self.assertEqual(res.get("tool"), expected_tool)

if __name__ == "__main__":
    unittest.main()
