import unittest
from core.math_logic import evaluate_counterfactual_scenario

class TestCounterfactualReasoning(unittest.TestCase):
    def test_evaluate_counterfactual_numeric_change(self):
        scenario = "What if the application RAM requirement increased from 2 GB to 6 GB on an 8 GB system?"
        res = evaluate_counterfactual_scenario(scenario)
        self.assertTrue(res["valid"])
        self.assertIn("feasible", res["conclusion"].lower())
        self.assertEqual(res["metric"], "gb")

    def test_evaluate_counterfactual_exceeding_system(self):
        scenario = "What if the application RAM requirement increased from 4 GB to 12 GB on an 8 GB system?"
        res = evaluate_counterfactual_scenario(scenario)
        self.assertTrue(res["valid"])
        self.assertIn("exceeds", res["conclusion"].lower())

    def test_evaluate_non_counterfactual(self):
        res = evaluate_counterfactual_scenario("What time is it now?")
        self.assertFalse(res["valid"])

if __name__ == "__main__":
    unittest.main()
