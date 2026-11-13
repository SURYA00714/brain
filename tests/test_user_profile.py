import unittest
import tempfile
import os
import shutil
from pathlib import Path
from core.session import UserProfileManager, UserProfile

class TestUserProfile(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mgr = UserProfileManager(profiles_dir=Path(self.test_dir))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_profile_creation(self):
        profile = self.mgr.get_active_profile()
        self.assertEqual(profile.name, "default")
        self.assertEqual(profile.working_style, "concise")

    def test_create_and_switch_profile(self):
        self.mgr.create_profile("researcher", working_style="thorough", preferred_model="qwen3.5-brain:v2")
        self.mgr.switch_profile("researcher")
        active = self.mgr.get_active_profile()
        self.assertEqual(active.name, "researcher")
        self.assertEqual(active.working_style, "thorough")
        self.assertEqual(active.preferred_model, "qwen3.5-brain:v2")

    def test_list_profiles(self):
        self.mgr.create_profile("alice")
        self.mgr.create_profile("bob")
        profiles = self.mgr.list_profiles()
        self.assertIn("default", profiles)
        self.assertIn("alice", profiles)
        self.assertIn("bob", profiles)

if __name__ == "__main__":
    unittest.main()
