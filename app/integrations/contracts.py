"""Typed public contracts for FloorTruth connectors (handoff §7).

No generic adapter accepts an unrestricted URL for server-side fetching
(SSRF guard for later deployments): connectors declare an allowlist scope.
All external writes remain disabled and return NOT_CONFIGURED until a future
authorized production project.
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ConnectorStatus(str, Enum):
    AVAILABLE = "Available"
    MOCKED = "Mocked"
    PLANNED = "Planned"
    DISABLED = "Disabled"


class ConnectorCapability(str, Enum):
    READ = "read"
    PROPOSE_WRITE = "propose_write"
    EXTERNAL_WRITE = "external_write"


class ConnectorDescriptor(BaseModel):
    connector_id: str
    name: str
    connector_type: str
    direction: str = Field(pattern="^(read|propose_write|external_write|export|context)$")
    capability: ConnectorCapability
    status: ConnectorStatus
    auth_scheme: str = "none (synthetic demo)"
    permissions_needed: list[str] = Field(default_factory=list)
    sensitivity_tier: str = "synthetic-only"
    description: str
    synthetic: bool = True


class ObservationIngested(BaseModel):
    observation_id: str
    text: str
    shift: str
    channel: str
    location: str
    observed_at: str
    retrieved_at: str
    consent: bool = True
    synthetic: bool = True


class ObservationBatch(BaseModel):
    batch_id: str
    source_system: str
    records: list[ObservationIngested]
    idempotency_key: str
    synthetic: bool = True


class IssueRef(BaseModel):
    issue_id: str
    system: str
    title: str
    status: str
    synthetic: bool = True


class SuggestedTicket(BaseModel):
    """A proposed ticket. Creating it externally is NOT performed by the demo."""
    title: str
    body: str
    case_id: str
    external_write_status: str = "NOT_CONFIGURED"


class OperationalMetricBatch(BaseModel):
    connector_id: str
    metric: str
    count: int = Field(ge=0)
    mean: float | None = None
    unit: str | None = None
    observed_at: str
    retrieved_at: str
    schema_version: str = "1.0"
    synthetic: bool = True
    quality: str = "SIMULATED"


class MaintenanceEventSummary(BaseModel):
    equipment_ref: str  # de-identified
    event_type: str
    observed_at: str
    synthetic: bool = True


class TelemetrySummary(BaseModel):
    device_ref: str  # de-identified aggregate
    metric: str
    aggregate_value: float
    window: str
    quality_flags: list[str] = Field(default_factory=list)
    synthetic: bool = True


class ScheduleAggregate(BaseModel):
    period: str
    headcount_planned: int = Field(ge=0)
    headcount_actual: int = Field(ge=0)
    synthetic: bool = True


class TrainingGapHypothesis(BaseModel):
    gap: str
    supporting_evidence_ids: list[str]
    status: str = "UNVERIFIED"
    synthetic: bool = True


class SafetySignal(BaseModel):
    signal: str
    severity: str = Field(pattern="^(info|elevated|urgent)$")
    routing: str = "human_review"  # urgent signals route to humans, never auto-intervene
    synthetic: bool = True


class NotificationDraft(BaseModel):
    """A draft notification. Sending requires human approval; demo never sends."""
    audience: str
    subject: str
    body: str
    send_status: str = "NOT_SENT_DEMO"


class ActorContext(BaseModel):
    actor_id: str = "demo-reviewer"
    role: str = "Demo Reviewer"
    authenticated: bool = False  # demo role selection, NOT production authorization
    note: str = "Simulated identity; no AuthN/AuthZ in this build"


class GovernanceDecision(BaseModel):
    decision_id: str
    subject: str
    decision: str = Field(pattern="^(ALLOW|WARN|HOLD|APPROVE|REJECT|NEEDS_EVIDENCE)$")
    reason: str
    decided_by: str
    timestamp: str
    synthetic: bool = True


class InferenceUsageEvent(BaseModel):
    request_id: str
    provider: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_source: str = "not_reported"
    synthetic: bool = True
