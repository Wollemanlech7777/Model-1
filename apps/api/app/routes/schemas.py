from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PolicyReviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    environment_id: str | None = Field(
        default=None,
        description="Optional environment UUID. Defaults to Demo Environment when omitted.",
    )

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned

    @field_validator("environment_id")
    @classmethod
    def _normalize_environment_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return str(UUID(cleaned))
        except ValueError as exc:
            raise ValueError("environment_id must be a valid UUID") from exc


class JobAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def _normalize_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be empty")
        return cleaned


class PolicyReviewResponse(BaseModel):
    id: str
    status: str
    workflow_key: str
    policy_id: str | None
    input_message: str
    decision: str
    allow_external_write: bool
    avatar_state: str
    running_avatar_state: str | None = None
    crm_write: dict
    sources: dict
    timeline: list
    evidence: list
    progress: list[str]
    assistant_summary: str
    reasons: list[str]
    facts: dict = Field(default_factory=dict)
    interpretation: dict | None = None
    interpretation_source: str | None = None
    presentation: dict | None = None
