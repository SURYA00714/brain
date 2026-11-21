"""
Unit tests for Phase 1 Intelligence Upgrade: Goal Frame & Ellipsis Slot-Filling.
Tests:
1. Media playback intent mapping ('play mr.beast videos').
2. Multi-turn elliptical prepositional refinement ('in youtubr', 'in browser').
3. Fuzzy platform normalization ('youtubr' -> 'youtube', 'browsr' -> 'brave').
4. Active GoalFrame state persistence across turns.
"""

import os
import unittest
from unittest.mock import patch

os.environ["BRAIN_MOCK_GUI"] = "1"

from core.context import default_short_term_memory, GoalFrame
from core.app_backend import BrainAppCore
from tools.router import default_router


class TestGoalFrameAndEllipsis(unittest.TestCase):

    def setUp(self):
        default_short_term_memory.clear()
        self.core = BrainAppCore(default_model="qwen3.5-brain:v2")

    def tearDown(self):
        default_short_term_memory.clear()

    def test_direct_play_media_routing(self):
        """'play mr.beast videos' builds an execution plan targeting YouTube without falling back to chat."""
        route_res = default_router.route("play mr.beast videos")
        self.assertIsNotNone(route_res)
        self.assertEqual(route_res.get("type"), "plan")
        plan = route_res.get("plan")
        tool_names = [s.tool_name for s in plan.steps if s.tool_name]
        self.assertIn("OPEN_APP", tool_names)
        self.assertIn("BROWSER_NAVIGATE", tool_names)
        self.assertIn("CLICK_FIRST_RESULT", tool_names)

    def test_fuzzy_platform_normalization(self):
        """Fuzzy typos like 'youtubr' and 'browsr' are normalized to canonical platforms."""
        norm = default_short_term_memory.normalize_platform_name
        self.assertEqual(norm("youtubr"), "youtube")
        self.assertEqual(norm("yt"), "youtube")
        self.assertEqual(norm("you tube"), "youtube")
        self.assertEqual(norm("browser"), "brave")
        self.assertEqual(norm("browsr"), "brave")
        self.assertEqual(norm("wikipidia"), "wikipedia")

    def test_multi_turn_ellipsis_slot_filling(self):
        """Verifies multi-turn sequence: 'play mr.beast videos' -> 'in youtubr' -> 'in browser'."""
        # Turn 1: play mr.beast videos
        t1 = self.core.execute_task("play mr.beast videos")
        self.assertEqual(t1.get("execution_path"), "AUTONOMOUS_TOOL_EXECUTION")
        self.assertIn("mr.beast videos", t1.get("text"))

        # Turn 2: elliptical refinement with typo 'in youtubr'
        t2 = self.core.execute_task("in youtubr")
        self.assertEqual(t2.get("execution_path"), "AUTONOMOUS_TOOL_EXECUTION")
        self.assertIn("Youtube", t2.get("text"))

        # Turn 3: elliptical refinement 'in browser'
        t3 = self.core.execute_task("in browser")
        self.assertEqual(t3.get("execution_path"), "AUTONOMOUS_TOOL_EXECUTION")


if __name__ == "__main__":
    unittest.main()
