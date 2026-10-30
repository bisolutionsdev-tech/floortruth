"""Typed connector registry with honest availability labels.

Nothing here performs external writes or holds credentials. Statuses are
factual about this build: Available (works locally), Mocked (fixture-backed),
Planned (contract only), Disabled (blocked by policy).
"""
from __future__ import annotations
from app.integrations.contracts import (
    ConnectorCapability, ConnectorDescriptor, ConnectorStatus,
)

REGISTRY: list[ConnectorDescriptor] = [
    ConnectorDescriptor(
        connector_id="synthetic-mes-001",
        name="Synthetic MES aggregate feed",
        connector_type="operational_metrics",
        direction="read", capability=ConnectorCapability.READ,
        status=ConnectorStatus.MOCKED,
        description="Fixture-backed operational aggregates (counts, timestamps, units, mix). "
                    "Read-only; bounded synthetic input for demos.",
    ),
    ConnectorDescriptor(
        connector_id="csv-import",
        name="CSV/JSON observation import",
        connector_type="form_survey",
        direction="read", capability=ConnectorCapability.READ,
        status=ConnectorStatus.MOCKED,
        description="Validated synthetic batch import (ObservationBatch). Rejects non-synthetic "
                    "or schema-invalid rows; idempotency keys deduplicate.",
    ),
    ConnectorDescriptor(
        connector_id="ticketing-generic",
        name="Issue/ticketing (Jira/ServiceNow-style)",
        connector_type="issue_ticketing",
        direction="propose_write", capability=ConnectorCapability.PROPOSE_WRITE,
        status=ConnectorStatus.PLANNED,
        description="Read IssueRef / propose SuggestedTicket. External creation is never "
                    "performed; typed contract only.",
    ),
    ConnectorDescriptor(
        connector_id="cmms-summary",
        name="Equipment maintenance summary",
        connector_type="maintenance",
        direction="read", capability=ConnectorCapability.READ,
        status=ConnectorStatus.MOCKED,
        description="De-identified MaintenanceEventSummary fixture for falsification tests. "
                    "No equipment identities.",
    ),
    ConnectorDescriptor(
        connector_id="notification",
        name="Notification / collaboration",
        connector_type="notification",
        direction="propose_write", capability=ConnectorCapability.PROPOSE_WRITE,
        status=ConnectorStatus.DISABLED,
        description="Produces NotificationDraft only. External sending is disabled and "
                    "returns NOT_CONFIGURED; human approval would be required.",
    ),
    ConnectorDescriptor(
        connector_id="bi-export",
        name="BI / data-lake export",
        connector_type="export",
        direction="export", capability=ConnectorCapability.READ,
        status=ConnectorStatus.AVAILABLE,
        description="Local versioned aggregate report (CSV/JSON) with provenance. "
                    "Works offline on synthetic data.",
    ),
    ConnectorDescriptor(
        connector_id="webhook-bus",
        name="Generic webhook / event bus",
        connector_type="event_bus",
        direction="propose_write", capability=ConnectorCapability.PROPOSE_WRITE,
        status=ConnectorStatus.MOCKED,
        description="Signed-envelope contract placeholder. Outbound delivery disabled in demo.",
    ),
    ConnectorDescriptor(
        connector_id="policy-engine",
        name="Local governance policy engine",
        connector_type="governance",
        direction="read", capability=ConnectorCapability.READ,
        status=ConnectorStatus.AVAILABLE,
        description="Declarative demo rules: budget gates, evidence-fingerprint checks, "
                    "review requirements. Public interface only; no private AIPP internals.",
    ),
    ConnectorDescriptor(
        connector_id="identity-oidc",
        name="Identity / OIDC & RBAC",
        connector_type="identity",
        direction="context", capability=ConnectorCapability.READ,
        status=ConnectorStatus.PLANNED,
        description="ActorContext from a trusted future auth server. Current build uses "
                    "simulated demo roles only — not production authorization.",
    ),
    ConnectorDescriptor(
        connector_id="voice-transcribe",
        name="Voice observation transcription",
        connector_type="voice",
        direction="read", capability=ConnectorCapability.READ,
        status=ConnectorStatus.PLANNED,
        description="Batch transcription hook (muse-voice-transcribe-1.0). Transcript shown "
                    "for user review before submitting; raw audio not retained.",
    ),
]


def list_connectors() -> list[dict]:
    return [c.model_dump() for c in REGISTRY]


def get_connector(connector_id: str) -> dict | None:
    for c in REGISTRY:
        if c.connector_id == connector_id:
            return c.model_dump()
    return None
