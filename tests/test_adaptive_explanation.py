import unittest
from core.cognition import CognitiveEngine

class TestAdaptiveExplanation(unittest.TestCase):
    def setUp(self):
        self.cognition = CognitiveEngine()

    def test_beginner_explanation_adaptation(self):
        concept = "RAM"
        definition = "Random Access Memory is volatile temporary semiconductor memory used by the operating system."
        adapted = self.cognition.adapt_explanation_level(concept, definition, level="beginner")
        self.assertIn("think of it like", adapted.lower())
        self.assertIn("desk", adapted.lower())

    def test_expert_explanation_adaptation(self):
        concept = "RAM"
        definition = "Random Access Memory is volatile temporary semiconductor memory used by the operating system."
        adapted = self.cognition.adapt_explanation_level(concept, definition, level="expert")
        self.assertIn("random access memory", adapted.lower())
        self.assertIn("volatile", adapted.lower())
        self.assertNotIn("think of it like", adapted.lower())

if __name__ == "__main__":
    unittest.main()
