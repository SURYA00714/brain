import unittest
from tools.input import SecurityPolicyManager, PermissionRole

class TestSecurityRoles(unittest.TestCase):
    def setUp(self):
        self.policy = SecurityPolicyManager()

    def test_default_role_is_user(self):
        self.assertEqual(self.policy.current_role, PermissionRole.STANDARD_USER)

    def test_guest_role_blocks_file_modification(self):
        self.policy.set_role(PermissionRole.GUEST_READONLY)
        allowed, reason = self.policy.authorize_action("WRITE_TEXT_FILE", {"filepath": "test.txt", "content": "hi"})
        self.assertFalse(allowed)
        self.assertIn("Guest role", reason)

    def test_guest_role_allows_read_only(self):
        self.policy.set_role(PermissionRole.GUEST_READONLY)
        allowed, reason = self.policy.authorize_action("READ_TEXT_FILE", {"filepath": "test.txt"})
        self.assertTrue(allowed)

    def test_admin_role_allows_all_safe(self):
        self.policy.set_role(PermissionRole.ADMINISTRATOR)
        allowed, _ = self.policy.authorize_action("WRITE_TEXT_FILE", {"filepath": "test.txt"})
        self.assertTrue(allowed)

if __name__ == "__main__":
    unittest.main()
