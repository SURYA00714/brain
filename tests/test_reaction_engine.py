import pytest
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

def test_reaction_engine_basic():
    bridge = MockBridge()
    engine = ReactionEngine(bridge)

    # Initial event should trigger
    evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "SUCCESS"})
    assert engine.handle_event(evt) is True
    assert len(bridge.emotion_calls) == 1
    assert bridge.emotion_calls[0] == "happy"

def test_reaction_engine_cooldown():
    bridge = MockBridge()
    engine = ReactionEngine(bridge)
    engine.MIN_REACTION_INTERVAL = 0.5

    # First event
    evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
    assert engine.handle_event(evt) is True
    
    # Second event immediately (should be blocked by cooldown)
    evt2 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "SEARCHING"})
    assert engine.handle_event(evt2) is False

    # Wait for cooldown
    time.sleep(0.6)
    assert engine.handle_event(evt2) is True

def test_reaction_engine_priority_bypass():
    bridge = MockBridge()
    engine = ReactionEngine(bridge)
    
    # Trigger low priority
    evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
    assert engine.handle_event(evt) is True

    # High priority should bypass MIN_REACTION_INTERVAL
    evt2 = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "ERROR"})
    assert engine.handle_event(evt2) is True
    assert bridge.emotion_calls[-1] == "sad"

def test_reaction_engine_same_state():
    bridge = MockBridge()
    engine = ReactionEngine(bridge)
    
    evt = CompanionEvent(event_type="STATE_CHANGE", data={"activity": "THINKING"})
    assert engine.handle_event(evt) is True
    
    # Same state should be ignored entirely
    assert engine.handle_event(evt) is False
