import unittest
import time
from bridge.reaction_engine import ReactionEngine
from core.companion_state import CompanionEvent

class MockBridge:
    def __init__(self):
        self.emotion_calls = []
        self.animation_calls = []
        self.voice_calls = []

    def set_emotion(self, emotion):
        self.emotion_calls.append(emotion)
        return {"success": True, "status": "executed_unverified"}

    def play_animation(self, animation):
        self.animation_calls.append(animation)
        return {"success": True, "status": "executed_unverified"}
        
    def play_voice(self, file):
        self.voice_calls.append(file)
        return {"success": True, "status": "executed_unverified"}

class TestReactionEngine(unittest.TestCase):
    def test_reaction_engine_basic(self):
        bridge = MockBridge()
        engine = ReactionEngine(bridge)

        # Initial event should trigger
        evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "SUCCESS"})
        self.assertTrue(engine.handle_event(evt))
        self.assertEqual(len(bridge.emotion_calls), 1)
        self.assertEqual(bridge.emotion_calls[0], "happy")

    def test_reaction_engine_cooldown(self):
        bridge = MockBridge()
        engine = ReactionEngine(bridge)
        engine.MIN_REACTION_INTERVAL = 0.5

        # First event
        evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
        self.assertTrue(engine.handle_event(evt))
        
        # Second event immediately (should be blocked by cooldown)
        evt2 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "SEARCHING"})
        self.assertFalse(engine.handle_event(evt2))

        # Wait for cooldown
        time.sleep(0.6)
        self.assertTrue(engine.handle_event(evt2))

    def test_reaction_engine_priority_bypass(self):
        bridge = MockBridge()
        engine = ReactionEngine(bridge)
        
        # Trigger low priority
        evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
        self.assertTrue(engine.handle_event(evt))

        # High priority should bypass MIN_REACTION_INTERVAL
        evt2 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "ERROR"})
        self.assertTrue(engine.handle_event(evt2))
        self.assertEqual(bridge.emotion_calls[-1], "sad")

    def test_reaction_engine_same_state(self):
        bridge = MockBridge()
        engine = ReactionEngine(bridge)
        
        evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
        self.assertTrue(engine.handle_event(evt))
        
        # Same state should be ignored entirely
        self.assertFalse(engine.handle_event(evt))

if __name__ == "__main__":
    unittest.main()
