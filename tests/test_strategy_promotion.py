import unittest
import tempfile
from pathlib import Path
from core.adaptive import AdaptiveIntelligenceEngine

class TestStrategyPromotion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.engine = AdaptiveIntelligenceEngine(db_path=Path(self.tmp.name))

    def tearDown(self):
        self.engine.close()

    def test_rank_strategies_by_performance(self):
        # Record 4 successes for FAST_ROUTER
        for _ in range(4):
            self.engine.record_experience(
                user_request="open brave",
                strategy_used="FAST_ROUTER",
                plan_dict={},
                tools_selected=["OPEN_APP"],
                tool_results=[{"success": True}],
                duration_ms=50.0,
                verification_outcome="VERIFIED",
                outcome="SUCCESS",
                task_category="APP_CONTROL"
            )

        # Record 3 failures for DEEP_PLANNING
        for _ in range(3):
            self.engine.record_experience(
                user_request="open brave",
                strategy_used="DEEP_PLANNING",
                plan_dict={},
                tools_selected=["OPEN_APP"],
                tool_results=[{"success": False}],
                duration_ms=4000.0,
                verification_outcome="FAILED",
                outcome="FAILURE",
                task_category="APP_CONTROL"
            )

        ranked = self.engine.rank_strategies_for_category("APP_CONTROL")
        self.assertGreater(len(ranked), 0)
        self.assertEqual(ranked[0]["strategy_used"], "FAST_ROUTER")
        self.assertEqual(ranked[0]["task_success_rate"], 1.0)

if __name__ == "__main__":
    unittest.main()
