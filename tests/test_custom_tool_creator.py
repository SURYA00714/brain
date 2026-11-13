import unittest
from tools.registry import ToolRegistry

class TestCustomToolCreator(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()

    def test_register_dynamic_tool(self):
        def custom_greet(name="World"):
            return f"Hello, {name}!"

        self.registry.register_custom_tool(
            name="CUSTOM_GREET",
            func=custom_greet,
            description="Greets a user by name",
            parameters={"name": "str"}
        )

        self.assertTrue(self.registry.has_tool("CUSTOM_GREET"))
        res = self.registry.execute("CUSTOM_GREET", {"name": "Alice"})
        self.assertTrue(res["success"])
        self.assertEqual(res["data"], "Hello, Alice!")

    def test_register_duplicate_rejection(self):
        def dummy():
            return "ok"

        self.registry.register_custom_tool("DUMMY", dummy, "test")
        with self.assertRaises(ValueError):
            self.registry.register_custom_tool("DUMMY", dummy, "test duplicate")

if __name__ == "__main__":
    unittest.main()
