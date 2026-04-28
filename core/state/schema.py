from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.utils.ids import audit_id, incident_id, pr_branch_name, utc_now


class IncidentSource(str, Enum):
    AZURE_DEVOPS = "azure_devops"
    SERVICE_BUS = "service_bus"
    LOGIC_APP = "logic_app"
    ADF = "adf"
    DATABRICKS = "databricks"
    MANUAL = "manual"


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    DIAGNOSING = "diagnosing"
    REMEDIATION_DRAFTED = "remediation_drafted"
    AWAITING_APPROVAL = "awaiting_approval"
    CLOSED = "closed"


class LogTaxonomy(str, Enum):
    INFRA = "infra"
    CODE = "code"
    CONFIG = "config"
    DATA = "data"
    AUTH = "auth"
    NETWORK = "network"
    UNKNOWN = "unknown"


class GovernanceOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MessageTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=40000)
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    incident_id: str = Field(default_factory=incident_id, min_length=8, max_length=128)
    source: IncidentSource
    source_event_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(default="", max_length=20000)
    service_name: str = Field(min_length=1, max_length=200)
    environment: Literal["dev", "test", "stage", "prod"] = "dev"
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.NEW
    detected_at: datetime = Field(default_factory=utc_now)
    tags: dict[str, str] = Field(default_factory=dict)
    evidence_uris: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    requires_human: bool = False

    @field_validator("detected_at")
    @classmethod
    def ensure_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class DiagnosticReport(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    incident_id: str = Field(min_length=8, max_length=128)
    summary: str = Field(min_length=10, max_length=10000)
    confidence: float = Field(ge=0.0, le=1.0)
    taxonomy: LogTaxonomy = LogTaxonomy.UNKNOWN
    root_cause_hypotheses: list[str] = Field(default_factory=list, max_length=10)
    correlated_signals: list[str] = Field(default_factory=list)
    evidence_uris: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("root_cause_hypotheses")
    @classmethod
    def ensure_non_empty_root_cause(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("At least one root cause hypothesis is required.")
        return values


class PullRequestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    incident_id: str = Field(min_length=8, max_length=128)
    repository: str = Field(min_length=1, max_length=256)
    source_branch: str = Field(min_length=5, max_length=256)
    target_branch: str = Field(default="main", min_length=1, max_length=128)
    title: str = Field(min_length=8, max_length=240)
    body: str = Field(min_length=20, max_length=50000)
    diff_patch: str = Field(default="", max_length=1_500_000)
    files_changed: list[str] = Field(default_factory=list)
    rollback_notes: str = Field(default="", max_length=10000)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_source_branch(self) -> PullRequestSpec:
        if not self.source_branch.startswith("acrge/fix/"):
            self.source_branch = pr_branch_name(self.incident_id)
        return self


class GovernanceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    incident_id: str = Field(min_length=8, max_length=128)
    decision: GovernanceOutcome = GovernanceOutcome.NEEDS_HUMAN_REVIEW
    requires_human_approval: bool = True
    reasons: list[str] = Field(default_factory=list, max_length=20)
    policy_version: str = Field(default="v1", min_length=1, max_length=64)
    approver: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime = Field(default_factory=utc_now)

    @field_validator("reasons")
    @classmethod
    def ensure_reasons(cls, value: list[str]) -> list[str]:
        if not value:
            return ["Governance review is required by default policy."]
        return value


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    audit_id: str = Field(default_factory=audit_id, min_length=8, max_length=128)
    incident_id: str = Field(min_length=8, max_length=128)
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    outcome: Literal["success", "failure", "skipped"] = "success"
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    immutable: bool = True


class ACRGEState(BaseModel):
    """
    Canonical graph state container.

    This model is strict enough for persistence and validation, while
    `to_langgraph_state`/`update_from_node` provide dict-based compatibility for
    LangGraph node I/O.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    incident: IncidentEvent
    messages: list[MessageTrace] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    diagnostic_report: DiagnosticReport | None = None
    log_summary: str = Field(default="", max_length=50000)
    pr_spec: PullRequestSpec | None = None
    governance_decision: GovernanceDecision | None = None
    audit_trail: list[AuditEntry] = Field(default_factory=list)

    def to_langgraph_state(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def update_from_node(self, update: dict[str, Any]) -> ACRGEState:
        merged = self.model_dump(mode="python")
        merged.update(update)
        return ACRGEState.model_validate(merged)


class ACRGEGraphState(TypedDict, total=False):
    """TypedDict state for LangGraph node function signatures."""

    incident: IncidentEvent
    messages: list[MessageTrace]
    reasoning_trace: list[str]
    diagnostic_report: NotRequired[DiagnosticReport | None]
    log_summary: NotRequired[str]
    pr_spec: NotRequired[PullRequestSpec | None]
    governance_decision: NotRequired[GovernanceDecision | None]
    audit_trail: list[AuditEntry]
