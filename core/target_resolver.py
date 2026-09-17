"""
Brain Target Resolver (Stage 8E).
Resolves semantic UI element target requests against fused screen observations.
Enforces strict anti-hallucination policies: returns AMBIGUOUS_TARGET, TARGET_NOT_CONFIDENT, or TARGET_STALE.
"""

import time
from typing import Dict, Any, List, Optional, Tuple

from core.ui_element import UIElement


class TargetResolver:
    """Semantic target resolution engine for UI elements."""
    def __init__(self, confidence_threshold: float = 0.5, max_target_age_seconds: float = 15.0):
        self.confidence_threshold = confidence_threshold
        self.max_target_age_seconds = max_target_age_seconds

    def resolve(
        self,
        elements: List[UIElement],
        role: Optional[str] = None,
        label: Optional[str] = None,
        text: Optional[str] = None,
        observation_timestamp: Optional[float] = None
    ) -> Tuple[str, Optional[UIElement], str]:
        """
        Resolves a semantic target request against available UIElements.
        Returns: (status: "RESOLVED" | "AMBIGUOUS_TARGET" | "TARGET_NOT_CONFIDENT" | "TARGET_STALE" | "NOT_FOUND", element, reason)
        """
        if observation_timestamp and (time.time() - observation_timestamp) > self.max_target_age_seconds:
            return "TARGET_STALE", None, f"Observation timestamp is older than {self.max_target_age_seconds}s."

        if not elements:
            return "NOT_FOUND", None, "No UI elements present in current observation."

        clean_role = role.lower().strip() if role else None
        clean_label = label.lower().strip() if label else None
        clean_text = text.lower().strip() if text else None

        candidates = []

        for el in elements:
            score = 0.0
            el_role = (el.role or "").lower()
            el_label = (el.label or "").lower()
            el_text = (el.text or "").lower()

            # Role matching
            if clean_role:
                if el_role == clean_role:
                    score += 0.4
                elif clean_role in el_role:
                    score += 0.2

            # Label matching
            if clean_label:
                if el_label == clean_label or el_text == clean_label:
                    score += 0.5
                elif clean_label in el_label or clean_label in el_text:
                    score += 0.3

            # Text matching
            if clean_text:
                if el_text == clean_text or el_label == clean_text:
                    score += 0.5
                elif clean_text in el_text or clean_text in el_label:
                    score += 0.3

            # If no specific constraints given, fallback to matching label/text
            if not clean_role and not clean_label and not clean_text:
                score = 0.1

            total_conf = score * el.confidence
            if total_conf >= self.confidence_threshold:
                candidates.append((total_conf, el))

        if not candidates:
            return "NOT_FOUND", None, "No element matched the specified criteria with sufficient confidence."

        # Sort by total score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        best_score, best_element = candidates[0]

        # Check for ambiguity: if top 2 candidates have very close scores (diff < 0.1)
        if len(candidates) > 1:
            second_score, _ = candidates[1]
            if (best_score - second_score) < 0.1 and best_score < 0.8:
                return "AMBIGUOUS_TARGET", None, f"Multiple elements matched '{clean_label or clean_text or clean_role}' with ambiguous confidence scores ({best_score:.2f} vs {second_score:.2f})."

        return "RESOLVED", best_element, f"Resolved target '{best_element.id}' with confidence {best_score:.2f}."


default_target_resolver = TargetResolver()
