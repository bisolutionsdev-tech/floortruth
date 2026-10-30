"""Typed ledger entities. Pydantic validation at every boundary.

Conventions:
- Money: integer USD micros. None = unknown (never silently zero).
- Tokens: non-negative ints or None when the provider did not report them.
- attribution_status may only reach CONTROLLED_ASSOCIATION / CAUSAL_EVIDENCE_REVIEWED
  when supporting evidence exists; see app.finops.value.clamp_attribution.
- No numeric confidence probabilities anywhere: evidence_quality is qualitative.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator

UsageSource = Literal["reported", "estimated", "not_reported"]
BudgetDecisionType = Literal["ALLOW", "WARN", "HOLD"]
AttributionStatus = Literal["DESCRIPTIVE_ONLY", "CONTROLLED_ASSOCIATION", "CAUSAL_EVIDENCE_REVIEWED"]
EvidenceQuality = Literal["PRELIMINARY", "CORROBORATED", "MEASURED_DESCRIPTIVE", "CONTROLLED"]
RealizationType = Literal["capacity_equivalent", "documented_redeployment", "avoided_expenditure", "unknown"]
InferenceStatus = Literal["succeeded", "failed", "held", "unavailable"]
WorkflowStatus = Literal["running", "completed", "failed", "held"]


class WorkflowRunRecord(BaseModel):
    id: str
    case_id: str | None = None
    experiment_id: str | None = None
    workflow_name: str
    started_at: str
    completed_at: str | None = None
    status: WorkflowStatus = "running"
    evidence_fingerprint: str | None = None
    metadata_json: str | None = None
    synthetic: bool = True


class InferenceEventRecord(BaseModel):
    id: str
    request_id: str
    attempt_no: int = Field(default=1, ge=1)
    workflow_run_id: str | None = None
    case_id: str | None = None
    operation: str
    provider: str
    model: str | None = None
    protocol: str | None = None
    usage_source: UsageSource = "not_reported"
    request_started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    status: InferenceStatus = "succeeded"
    error_class: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    provider_total_tokens: int | None = Field(default=None, ge=0)
    raw_usage_json: str | None = None
    provider_request_id: str | None = None
    pricebook_version: str | None = None
    estimated_cost_usd_micros: int | None = Field(default=None, ge=0)
    budget_decision_id: str | None = None
    content_logged: bool = False
    synthetic: bool = True

    @field_validator("cached_input_tokens")
    @classmethod
    def _cache_within_input(cls, v, info):
        total = info.data.get("input_tokens")
        if v is not None and total is not None and v > total:
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        return v


class PriceBookEntryRecord(BaseModel):
    version: str
    provider: str
    model: str
    mode: str
    meter: str
    unit: str
    rate_per_unit_micros: int | None = Field(default=None, ge=0)
    effective_from: str
    effective_to: str | None = None
    citation_url: str | None = None
    last_verified_at: str | None = None
    notes: str | None = None


class BudgetPolicyRecord(BaseModel):
    id: str
    scope_type: str = "global"
    scope_id: str = "default"
    daily_limit_usd_micros: int | None = Field(default=None, ge=0)
    run_limit_usd_micros: int | None = Field(default=None, ge=0)
    token_soft_limit: int | None = Field(default=None, ge=0)
    request_limit: int | None = Field(default=None, ge=0)
    per_call_estimate_cap_usd_micros: int | None = Field(default=None, ge=0)
    action_on_limit: Literal["HOLD", "WARN"] = "HOLD"
    enabled: bool = True
    synthetic: bool = True


class BudgetDecisionRecord(BaseModel):
    id: str
    workflow_run_id: str | None = None
    scope: str
    quoted_max_usd_micros: int | None = Field(default=None, ge=0)
    current_spend_usd_micros: int | None = Field(default=None, ge=0)
    decision: BudgetDecisionType
    rule_version: str = "budget-policy-v1"
    reason: str
    timestamp: str


class OutcomeAssessmentRecord(BaseModel):
    id: str
    case_id: str
    experiment_id: str | None = None
    baseline_json: str
    observed_json: str
    comparator_json: str | None = None
    opportunity_type: str | None = None
    unit_economics_json: str | None = None
    operational_benefit_usd_micros: int | None = Field(default=None, ge=0)
    intervention_cost_usd_micros: int | None = Field(default=None, ge=0)
    inference_cost_usd_micros: int | None = Field(default=None, ge=0)
    other_known_cost_usd_micros: int | None = Field(default=None, ge=0)
    modeled_net_usd_micros: int | None = None
    roi_percent: float | None = None
    attribution_status: AttributionStatus = "DESCRIPTIVE_ONLY"
    evidence_quality: EvidenceQuality = "PRELIMINARY"
    assumptions_json: str = "[]"
    caveats_json: str = "[]"
    realization_type: RealizationType = "capacity_equivalent"
    data_version: str = "synthetic-v1"
    created_at: str
