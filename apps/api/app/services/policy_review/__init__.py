from app.services.policy_review.avatar_map import (
    avatar_state_for_idle,
    avatar_state_for_outcome,
    avatar_state_for_running,
)
from app.services.policy_review.extract import extract_policy_id
from app.services.policy_review.normalize import build_decision_context, normalize_status

__all__ = [
    "avatar_state_for_idle",
    "avatar_state_for_outcome",
    "avatar_state_for_running",
    "build_decision_context",
    "extract_policy_id",
    "normalize_status",
]


def __getattr__(name: str):
    if name == "PolicyReviewOrchestrator":
        from app.services.policy_review.orchestrator import PolicyReviewOrchestrator

        return PolicyReviewOrchestrator
    raise AttributeError(name)
