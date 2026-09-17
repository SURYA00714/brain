import unittest
from unittest.mock import patch, MagicMock
from core.desktop_presence import DesktopPresenceManager, DESKTOPMATE_EXE, PROTON_BIN

class TestDesktopPresenceManager(unittest.TestCase):
    def test_init_defaults(self):
        mgr = DesktopPresenceManager()
        self.assertEqual(mgr.max_recovery_attempts, 3)
        self.assertEqual(mgr.recovery_count, 0)

    @patch("subprocess.run")
    def test_is_process_running_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="123 S DesktopMate.exe Z:\\DesktopMate.exe\n")
        mgr = DesktopPresenceManager()
        self.assertTrue(mgr.is_process_running())

    @patch("subprocess.run")
    def test_is_process_running_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        mgr = DesktopPresenceManager()
        self.assertFalse(mgr.is_process_running())

    @patch("subprocess.run")
    def test_get_window_id_found(self, mock_run):
        mock_tree = MagicMock(returncode=0, stdout='0x8200005 "DesktopMate"\n', stderr="")
        mock_id = MagicMock(returncode=0, stdout='xwininfo: Window id: 0x8200005 "DesktopMate"', stderr="")
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="123 S DesktopMate.exe Z:\\DesktopMate.exe\n"),
            mock_tree,
            mock_id,
        ]
        mgr = DesktopPresenceManager()
        win_id = mgr.get_window_id()
        self.assertEqual(win_id, "0x8200005")

    @patch.object(DesktopPresenceManager, "is_process_running", return_value=True)
    @patch.object(DesktopPresenceManager, "get_window_id", return_value="0x8200005")
    def test_ensure_running_already_running(self, mock_win, mock_proc):
        mgr = DesktopPresenceManager()
        res = mgr.ensure_running()
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "already_running")
        self.assertEqual(res["window_id"], "0x8200005")

    def test_recovery_retry_limit(self):
        mgr = DesktopPresenceManager(max_recovery_attempts=2)
        mgr.recovery_count = 2
        res = mgr.recover()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "recovery_exhausted")
        self.assertIn("Exceeded maximum recovery attempts", res["error"])

if __name__ == "__main__":
    unittest.main()
