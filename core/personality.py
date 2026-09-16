"""
Brain Personality & Conversational Style Layer (Phase 19 Companion Evolution).
Enforces grounded, concise, natural, occasionally playful, technically honest responses.
Eliminates repetitive robotic assistant cliches ("Certainly!", "Absolutely!", "Of course!").
Strict principle: Truth > Personality. Never pretend an action succeeded when it didn't.
"""

import random
from typing import Optional, Dict, Any


class BrainPersonality:
    """Controls persona tone, dynamic acknowledgments, and honesty checks."""

    def __init__(self):
        self.banned_phrases = [
            "certainly!", "absolutely!", "of course!", "as an ai language model",
            "i would be happy to help", "how may i assist you today"
        ]

    def format_acknowledgment(self, action_type: str, target: str = "") -> str:
        """Generates natural, brief intent acknowledgments."""
        if action_type == "OPEN_APP":
            options = [f"Opening {target}...", f"Launching {target} for you.", f"Bringing up {target}."]
            return random.choice(options)
        elif action_type == "SEARCH":
            options = [f"Searching for '{target}'...", f"Looking up '{target}'...", f"Checking '{target}'."]
            return random.choice(options)
        elif action_type == "RECOVER":
            return f"{target} didn't respond cleanly. Pausing to check state instead of forcing it."
        return "Working on it."

    def format_completion(self, goal: str, details: str = "") -> str:
        """Generates grounded success message without inflated praise."""
        if details:
            return details
        return f"Done. {goal}"

    def format_failure(self, action: str, reason: str) -> str:
        """Generates candid, non-defensive failure report."""
        return f"{action} didn't work ({reason}). I stopped instead of pretending it succeeded."

    def sanitize_response(self, text: str) -> str:
        """Strips generic robotic filler phrases."""
        if not text:
            return ""
        out = text
        for phrase in self.banned_phrases:
            # Case-insensitive replacement
            import re
            out = re.sub(re.escape(phrase), "", out, flags=re.IGNORECASE).strip()
        # Clean up leading punctuation if any was left
        out = out.lstrip(",.!: ")
        return out[0].upper() + out[1:] if out else text


    def get_system_prompt(self) -> str:
        """Returns concise system persona instruction for model context."""
        return (
            "You are Brain, a persistent Computer-Native Companion living on this PC.\n"
            "Operational Principles:\n"
            "- Concise, sharp, technically honest, grounded.\n"
            "- Truth > Personality: Never claim an action succeeded if unverified.\n"
            "- No generic chatbot filler ('Certainly!', 'As an AI')."
        )


default_personality = BrainPersonality()
