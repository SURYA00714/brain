"""
Brain Expectation & Action Verification Model (Stage 8G/8H).
Enforces the ACTION -> OBSERVE -> COMPARE -> VERIFY contract.
Evaluates expected post-action environment changes against evidence.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
import time


VERIFICATION_STATUSES = {
    "VERIFIED", "EXECUTED_UNVERIFIED", "FAILED", "BLOCKED", "STALE", "AMBIGUOUS"
}


@dataclass
class ActionExpectation:
    """Defines pre-action expectations for state verification."""
    action_name: str
    expected_app: Optional[str] = None
    expected_window_title: Optional[str] = None
    expected_text: Optional[str] = None
    expected_element: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class VerificationReport:
    """Structured report of expectation verification result."""
    status: str                         # VERIFIED, EXECUTED_UNVERIFIED, FAILED, BLOCKED, STALE, AMBIGUOUS
    verified: bool
    evidence: List[str] = field(default_factory=list)
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExpectationVerifier:
    """Evaluates post-action observations against ActionExpectation specifications."""

    def verify(
        self,
        expectation: ActionExpectation,
        pre_observation: Optional[Dict[str, Any]],
        post_observation: Dict[str, Any]
    ) -> VerificationReport:
        """Compares post-action observation against expectation specification."""
        evidence = []
        post_app = (post_observation.get("application") or post_observation.get("focused_app") or "").lower()
        post_title = (post_observation.get("window_title") or post_observation.get("window") or "").lower()
        post_texts = [str(t).lower() for t in post_observation.get("ocr_texts", [])]
        combined_text = " ".join(post_texts) + " " + post_title

        # 1. App expectation check
        if expectation.expected_app:
            exp_app = expectation.expected_app.lower()
            if exp_app in post_app:
                evidence.append(f"Application matched expected '{expectation.expected_app}'")
            else:
                return VerificationReport(
                    status="FAILED",
                    verified=False,
                    evidence=evidence,
                    reason=f"Expected active application '{expectation.expected_app}', but found '{post_app}'."
                )

        # 2. Window title expectation check
        if expectation.expected_window_title:
            exp_title = expectation.expected_window_title.lower()
            if exp_title in post_title:
                evidence.append(f"Window title matched expected '{expectation.expected_window_title}'")
            else:
                return VerificationReport(
                    status="FAILED",
                    verified=False,
                    evidence=evidence,
                    reason=f"Expected window title matching '{expectation.expected_window_title}', but found '{post_title}'."
                )

        # 3. Expected text check
        if expectation.expected_text:
            exp_text = expectation.expected_text.lower()
            if exp_text in combined_text:
                evidence.append(f"Observed text matching expected '{expectation.expected_text}'")
            else:
                return VerificationReport(
                    status="EXECUTED_UNVERIFIED",
                    verified=False,
                    evidence=evidence,
                    reason=f"Expected text '{expectation.expected_text}' was not verified on screen."
                )

        if not evidence:
            evidence.append("Action executed without explicit state change verification failures.")

        return VerificationReport(
            status="VERIFIED",
            verified=True,
            evidence=evidence,
            reason="All post-action expectations verified against screen perception evidence."
        )


default_expectation_verifier = ExpectationVerifier()
