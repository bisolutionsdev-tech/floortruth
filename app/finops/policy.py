"""Deterministic pre-call budget policy.

Defaults are configurable via environment, never hard-coded into decisions:
  FLOORTRUTH_MAX_MODEL_SPEND_USD   (default 15.00)  — daily inference spend cap
  FLOORTRUTH_MAX_CALLS_PER_RUN     (default 100)    — max calls per workflow run
  FLOORTRUTH_PER_CALL_ESTIMATE_CAP_USD (default 0.25) — max quoted cost per call

These app-inference limits do NOT meter the Muse coding agent's own
subscription usage. A denied call returns a typed HOLD with a reason enum;
the caller decides how to surface it (HTTP 429 on the demo API).
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from app.domain import utc_now
from app.finops.models import BudgetDecisionRecord, BudgetPolicyRecord

RULE_VERSION = "budget-policy-v1"

# Safe, machine-readable hold reasons surfaced to the UI (no stack traces).
REASON_PER_CALL_CAP = "PROJECTED_COST_EXCEEDS_PER_CALL_CAP"
REASON_RUN_LIMIT = "RUN_SPEND_LIMIT_EXCEEDED"
REASON_DAILY_LIMIT = "DAILY_SPEND_LIMIT_EXCEEDED"
REASON_REQUEST_LIMIT = "REQUEST_LIMIT_EXCEEDED"
REASON_TOKEN_SOFT = "TOKEN_SOFT_LIMIT_EXCEEDED"
REASON_POLICY_DISABLED = "POLICY_DISABLED"
REASON_WITHIN_BUDGET = "WITHIN_BUDGET"


def _usd_env(name: str, default_usd: float) -> int:
    """Env USD value -> integer micros."""
    try:
        return int(round(float(os.getenv(name, str(default_usd))) * 1_000_000))
    except ValueError:
        return int(round(default_usd * 1_000_000))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def default_policy() -> BudgetPolicyRecord:
    return BudgetPolicyRecord(
        id="default-global",
        scope_type="global",
        scope_id="default",
        daily_limit_usd_micros=_usd_env("FLOORTRUTH_MAX_MODEL_SPEND_USD", 15.00),
        run_limit_usd_micros=None,  # per-run cap derived from daily policy unless set
        token_soft_limit=None,
        request_limit=_int_env("FLOORTRUTH_MAX_CALLS_PER_RUN", 100),
        per_call_estimate_cap_usd_micros=_usd_env("FLOORTRUTH_PER_CALL_ESTIMATE_CAP_USD", 0.25),
        action_on_limit="HOLD",
        enabled=True,
        synthetic=True,
    )


def _day_start_iso() -> str:
    return day_start_iso()


def day_start_iso() -> str:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def evaluate(
    policy: BudgetPolicyRecord,
    *,
    current_spend_usd_micros: int,
    current_calls: int,
    projected_cost_usd_micros: int | None,
    projected_tokens: int | None = None,
    workflow_run_id: str | None = None,
    scope: str = "global",
) -> BudgetDecisionRecord:
    """Deterministic ALLOW / WARN / HOLD decision, recorded by the caller."""
    base = dict(id=uuid.uuid4().hex, workflow_run_id=workflow_run_id, scope=scope,
                quoted_max_usd_micros=projected_cost_usd_micros,
                current_spend_usd_micros=current_spend_usd_micros,
                rule_version=RULE_VERSION, timestamp=utc_now())
    if not policy.enabled:
        return BudgetDecisionRecord(**base, decision="ALLOW", reason=REASON_POLICY_DISABLED)
    if projected_cost_usd_micros is not None and policy.per_call_estimate_cap_usd_micros is not None \
            and projected_cost_usd_micros > policy.per_call_estimate_cap_usd_micros:
        return BudgetDecisionRecord(**base, decision="HOLD", reason=REASON_PER_CALL_CAP)
    if policy.request_limit is not None and current_calls + 1 > policy.request_limit:
        return BudgetDecisionRecord(**base, decision="HOLD", reason=REASON_REQUEST_LIMIT)
    if projected_cost_usd_micros is not None:
        if policy.daily_limit_usd_micros is not None \
                and current_spend_usd_micros + projected_cost_usd_micros > policy.daily_limit_usd_micros:
            return BudgetDecisionRecord(**base, decision="HOLD", reason=REASON_DAILY_LIMIT)
        if policy.run_limit_usd_micros is not None \
                and current_spend_usd_micros + projected_cost_usd_micros > policy.run_limit_usd_micros:
            return BudgetDecisionRecord(**base, decision="HOLD", reason=REASON_RUN_LIMIT)
    if projected_tokens is not None and policy.token_soft_limit is not None \
            and projected_tokens > policy.token_soft_limit:
        return BudgetDecisionRecord(**base, decision="WARN", reason=REASON_TOKEN_SOFT)
    return BudgetDecisionRecord(**base, decision="ALLOW", reason=REASON_WITHIN_BUDGET)
