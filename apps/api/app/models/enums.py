from enum import StrEnum


class ConnectorType(StrEnum):
    CRM = "crm"
    LEGACY = "legacy"
    EMAIL = "email"
    PORTAL = "portal"


class ConnectorStatus(StrEnum):
    DISCOVERED = "discovered"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    FAILED = "failed"
    DISABLED = "disabled"


class EnvironmentStatus(StrEnum):
    DRAFT = "draft"
    CONFIGURING = "configuring"
    READY = "ready"
    ERROR = "error"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionOutcome(StrEnum):
    """Operational authority outcomes. Avatar/UI state is separate."""

    EXECUTE = "execute"
    REVIEW = "review"
    FAIL = "fail"


class EvidenceKind(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    CALCULATED = "calculated"


class ExecutionEventType(StrEnum):
    CONFIG = "config"
    INTEGRATION = "integration"
    EXTRACTION = "extraction"
    NORMALIZATION = "normalization"
    AI = "ai"
    VALIDATION = "validation"
    DECISION = "decision"
    ACTION = "action"
    ERROR = "error"


class SemanticSystemState(StrEnum):
    """Presentation-layer states for the compact status character."""

    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    SUCCESS = "success"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"
    FAILED = "failed"


class AvatarExpression(StrEnum):
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    FOCUSED = "focused"
    PROUD = "proud"
    QUIZZICAL = "quizzical"
    ALERT = "alert"
    STRESSED = "stressed"
