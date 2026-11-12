import unittest
from unittest.mock import patch
from core.accuracy import AccuracyEngine, ObservableConfidence
from core.cognition import CognitiveEngine, EpistemicStatus
from core.context import ShortTermMemory


class TestAccuracyEngine(unittest.TestCase):
    def test_external_info_classification(self):
        self.assertEqual(AccuracyEngine.classify_external_info_need("What happened on Mars today?"), "WEB")
        self.assertEqual(AccuracyEngine.classify_external_info_need("Check my CPU and RAM usage"), "SYSTEM")
        self.assertEqual(AccuracyEngine.classify_external_info_need("What is my preferred browser?"), "MEMORY")
        self.assertEqual(AccuracyEngine.classify_external_info_need("What is 2 + 2?"), "NONE")

    def test_ambiguity_detection_without_conversational_referent(self):
        msg = AccuracyEngine.detect_ambiguity("fix this", recent_turns=[])
        self.assertIsNotNone(msg)
        self.assertIn("clarify", msg.lower())

        stm = ShortTermMemory()
        stm.add_turn("open brave", "Opened Brave.", referenced_app="brave")
        self.assertIsNone(AccuracyEngine.detect_ambiguity("fix this", recent_turns=stm.turns))

    def test_off_topic_evidence_rejected(self):
        res = AccuracyEngine.evaluate_evidence_relevance(
            "What happened on Mars today?",
            findings=["Blackrock, L Sunrise & Sunset Times with Golden Hour & Moon: Nov 8, 2026"],
            sources=["https://example.com/blackrock"]
        )
        self.assertEqual(res["relevant_findings"], [])
        self.assertEqual(res["evidence_coverage"], 0.0)

    def test_conflict_detection(self):
        findings = [
            "Ollama supports 8 GB RAM laptops.",
            "Ollama does not support 16 GB RAM models."
        ]
        res = AccuracyEngine.evaluate_evidence_relevance("Ollama RAM support", findings)
        self.assertTrue(len(res["conflicts"]) >= 1)
        self.assertLess(res["source_agreement"], 1.0)
        self.assertTrue(res["is_ambiguous"])

    def test_claim_verification_catches_fabricated_url_and_numbers(self):
        check = AccuracyEngine.verify_claims(
            "According to https://fake.example.com, CPU usage is 99%.",
            evidence=["CPU usage is 25% on Linux Mint."]
        )
        self.assertFalse(check["grounded"])
        self.assertTrue(any("fake.example.com" in c for c in check["unverified_claims"]))
        self.assertTrue(any("99" in c for c in check["unverified_claims"]))

    def test_observable_confidence_levels(self):
        unv = AccuracyEngine.compute_observable_confidence(0.0, 1.0, True, 1.0)
        self.assertEqual(unv.level, "UNVERIFIED")
        high = AccuracyEngine.compute_observable_confidence(1.0, 1.0, True, 1.0)
        self.assertEqual(high.level, "HIGH")
        self.assertEqual(high.score, 1.0)

    def test_cognition_ku01_and_ku03_grounding(self):
        eng = CognitiveEngine()
        eng.short_term_mem = ShortTermMemory()

        # KU_03: "fix this" with no prior conversation turn must be AMBIGUOUS
        intent = eng.understand_intent("fix this")
        self.assertEqual(intent["intent"], "AMBIGUOUS")
        self.assertIn("clarify", intent["clarification"].lower())

        # KU_01: off-topic web search must return UNKNOWN and state could not verify
        with patch("core.cognition.research_topic", return_value={
            "success": True,
            "findings": ["Blackrock, L Sunrise & Sunset Times with Golden Hour & Moon"],
            "sources": ["https://example.com"]
        }):
            res = eng.execute_web_research("What happened on Mars today?")
        self.assertEqual(res["epistemic_status"], EpistemicStatus.UNKNOWN)
        self.assertIn("could not verify", res["text"].lower())


if __name__ == "__main__":
    unittest.main()
