"""
Brain Unified Confirmation Manager (Phase 7).
Ensures sensitive operations (terminal commands, destructive files, messages, purchases, credentials)
require explicit, short-lived user confirmation that the LLM cannot self-approve.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Tuple


CONFIRMATION_STATES = {"NOT_REQUIRED", "REQUIRED", "APPROVED", "DENIED", "EXPIRED"}

SENSITIVE_ACTIONS = {
    "SHELL", "EXECUTE_COMMAND", "SUBMIT_FORM", "SEND_MESSAGE",
    "PURCHASE", "ENTER_CREDENTIALS", "DELETE_FILE", "MODIFY_SYSTEM_CONFIG"
}


@dataclass
class ConfirmationRequest:
    """A bounded, short-lived confirmation request."""
    request_id: str
    action_name: str
    arguments: Dict[str, Any]
    status: str = "REQUIRED"  # REQUIRED, APPROVED, DENIED, EXPIRED
    reason: str = "Action requires explicit user confirmation"
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 60.0

    def is_expired(self) -> bool:
        if self.status == "EXPIRED":
            return True
        if self.status in ("APPROVED", "DENIED"):
            return False
        return (time.time() - self.created_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["expired"] = self.is_expired()
        return d


class ConfirmationManager:
    """Central manager for safe confirmation handling."""
    def __init__(self):
        self._pending_requests: Dict[str, ConfirmationRequest] = {}

    def evaluate_action(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, Optional[ConfirmationRequest]]:
        """
        Evaluates whether an action requires explicit user confirmation.
        Returns: (status: "NOT_REQUIRED" | "REQUIRED", request: Optional[ConfirmationRequest])
        """
        t_upper = str(tool_name).upper()

        # Direct check if action is in sensitive actions list
        is_sensitive = t_upper in SENSITIVE_ACTIONS

        # Argument content check for dangerous patterns
        arg_str = str(arguments).lower()
        if any(kw in arg_str for kw in ["sudo", "rm -rf", "delete", "/etc/shadow", "chmod"]):
            is_sensitive = True

        if not is_sensitive:
            return "NOT_REQUIRED", None

        req_id = f"conf_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        req = ConfirmationRequest(
            request_id=req_id,
            action_name=t_upper,
            arguments=arguments,
            status="REQUIRED",
            reason=f"Action '{t_upper}' is classified as sensitive and requires explicit user confirmation.",
            created_at=time.time()
        )
        self._pending_requests[req_id] = req

        # Broadcast event
        try:
            from core.event_bus import default_event_bus
            default_event_bus.publish("CONFIRMATION_REQUIRED", req.to_dict())
        except Exception:
            pass

        return "REQUIRED", req

    def approve(self, request_id: str, source: str = "user") -> bool:
        """Approves a pending request. Source MUST be user (LLM self-approval is rejected)."""
        if source != "user":
            return False

        req = self._pending_requests.get(request_id)
        if not req or req.is_expired():
            return False

        req.status = "APPROVED"
        return True

    def deny(self, request_id: str) -> bool:
        req = self._pending_requests.get(request_id)
        if not req:
            return False
        req.status = "DENIED"
        return True

    def get_request(self, request_id: str) -> Optional[ConfirmationRequest]:
        req = self._pending_requests.get(request_id)
        if req and req.is_expired():
            req.status = "EXPIRED"
        return req


default_confirmation_manager = ConfirmationManager()
