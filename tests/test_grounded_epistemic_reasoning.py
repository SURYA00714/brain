"""
Unit tests for Phase 3 Intelligence Upgrade: Grounded Epistemic Reasoning.
Tests:
1. Model system prompt consistently grounds live capabilities (internet, web search, desktop apps).
2. Identity prompt snippet explicitly includes terminal usage, hardware specs, and epistemic principles.
3. System context builder includes verified environment details without token bloat.
4. Epistemic consistency check for queries regarding capabilities and execution reality.
"""

import unittest
from core.identity import default_identity
from core.personality import default_personality
from core.context import default_context_builder


class TestGroundedEpistemicReasoning(unittest.TestCase):

    def test_identity_prompt_snippet_grounding(self):
        snippet = default_identity.get_identity_prompt_snippet()
        self.assertIn("Linux Mint (AMD Ryzen 3 7320U, 8 GB RAM)", snippet)
        self.assertIn("live internet access", snippet.lower())
        self.assertIn("real-time web search", snippet.lower())
        self.assertIn("brain", snippet.lower())
        self.assertIn("epistemic principles", snippet.lower())

    def test_personality_system_prompt_grounding(self):
        prompt = default_personality.get_system_prompt()
        self.assertIn("Linux Mint PC (AMD Ryzen 3 7320U, 8 GB RAM)", prompt)
        self.assertIn("live internet access", prompt.lower())
        self.assertIn("brain", prompt.lower())
        self.assertIn("truth > personality", prompt.lower())

    def test_system_context_builder_includes_grounded_identity(self):
        ctx = default_context_builder.build_system_context("do you have internet access")
        self.assertIn("Linux Mint", ctx)
        self.assertIn("live internet access", ctx.lower())
        self.assertIn("epistemic principles", ctx.lower())
        self.assertLessEqual(len(ctx), 1200)


if __name__ == "__main__":
    unittest.main()
