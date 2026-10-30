"""Outcome assessment: descriptive value math with hard causal guardrails.

- capacity_value_usd is potential economic capacity, NOT realized cash savings.
  realization_type stays 'capacity_equivalent' until documented redeployment or
  avoided expenditure exists.
- Claiming both capacity value and cash labor savings for the SAME saved
  minutes is double counting -> ValueError.
- attribution_status never exceeds DESCRIPTIVE_ONLY without a comparator and,
  for causal language, explicit human review. See clamp_attribution.
- No numeric confidence probabilities: evidence_quality is qualitative.
- check_strata_reversal flags Simpson's-paradox-style misleading aggregation:
  every stratum worsens while the mix-shifted aggregate appears to improve.
"""
from __future__ import annotations
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from app.domain import utc_now
from app.finops.models import AttributionStatus, OutcomeAssessmentRecord

MICROS = 1_000_000


def _to_micros(value: float | int | None) -> int | None:
    if value is None:
        return None
    return int((Decimal(str(value)) * MICROS).to_integral_value(rounding=ROUND_HALF_UP))


def clamp_attribution(requested: AttributionStatus, *, has_comparator: bool,
                      human_reviewed: bool) -> AttributionStatus:
    """Highest attribution level the support actually allows."""
    if requested == "CAUSAL_EVIDENCE_REVIEWED" and has_comparator and human_reviewed:
        return "CAUSAL_EVIDENCE_REVIEWED"
    if requested in ("CAUSAL_EVIDENCE_REVIEWED", "CONTROLLED_ASSOCIATION") and has_comparator:
        return "CONTROLLED_ASSOCIATION"
    return "DESCRIPTIVE_ONLY"


def check_strata_reversal(strata: list[dict]) -> dict:
    """Detect aggregate-vs-stratum reversal (Simpson's paradox fixture shape).

    Each stratum: {name, baseline, observed, weight_baseline, weight_observed}.
    delta = observed - baseline (negative = improvement for time metrics).
    Returns {reversal: bool, detail: str}.
    """
    if not strata:
        return {"reversal": False, "detail": "No strata supplied"}
    deltas = [s["observed"] - s["baseline"] for s in strata]
    agg_base = sum(s["baseline"] * s["weight_baseline"] for s in strata)
    agg_obs = sum(s["observed"] * s["weight_observed"] for s in strata)
    agg_delta = agg_obs - agg_base
    all_worse = all(d > 0 for d in deltas)
    reversal = all_worse and agg_delta < 0
    return {
        "reversal": reversal,
        "strata_deltas": deltas,
        "aggregate_delta": agg_delta,
        "detail": ("Every stratum worsened but the mix-shifted aggregate improved: "
                   "aggregation is misleading; do not report the aggregate as an effect."
                   if reversal else "No aggregate/stratum reversal detected."),
    }


def assess(
    *,
    case_id: str,
    baseline_minutes_per_period: float,
    observed_minutes_per_period: float,
    periods: int,
    loaded_hourly_rate_usd: float,
    intervention_cost_usd: float = 0.0,
    inference_cost_usd_micros: int | None = None,
    other_known_cost_usd: float = 0.0,
    cash_labor_savings_usd: float | None = None,
    realization: str = "capacity_equivalent",
    requested_attribution: AttributionStatus = "DESCRIPTIVE_ONLY",
    has_comparator: bool = False,
    human_reviewed: bool = False,
    evidence_quality: str = "MEASURED_DESCRIPTIVE",
    assumptions: list[str] | None = None,
    extra_caveats: list[str] | None = None,
    strata: list[dict] | None = None,
) -> OutcomeAssessmentRecord:
    if periods <= 0:
        raise ValueError("periods must be positive")
    for name, v in (("baseline_minutes_per_period", baseline_minutes_per_period),
                    ("observed_minutes_per_period", observed_minutes_per_period),
                    ("loaded_hourly_rate_usd", loaded_hourly_rate_usd),
                    ("intervention_cost_usd", intervention_cost_usd),
                    ("other_known_cost_usd", other_known_cost_usd)):
        if v < 0:
            raise ValueError(f"{name} must be non-negative")

    delta_minutes = (baseline_minutes_per_period - observed_minutes_per_period) * periods
    capacity_value_micros = _to_micros(Decimal(str(delta_minutes)) / 60 * Decimal(str(loaded_hourly_rate_usd)))

    if cash_labor_savings_usd is not None and (capacity_value_micros or 0) > 0:
        raise ValueError(
            "Double count refused: capacity value and cash labor savings describe the same "
            "saved minutes. Claim one, with its realization basis, not both.")

    benefit_micros = _to_micros(cash_labor_savings_usd) if cash_labor_savings_usd is not None else capacity_value_micros
    intervention_micros = _to_micros(intervention_cost_usd)
    other_micros = _to_micros(other_known_cost_usd)
    known_direct = (intervention_micros or 0) + (inference_cost_usd_micros or 0) + (other_micros or 0)

    modeled_net = (benefit_micros - known_direct) if benefit_micros is not None else None
    roi = round((modeled_net / known_direct) * 100, 1) if (modeled_net is not None and known_direct > 0) else None

    attribution = clamp_attribution(requested_attribution, has_comparator=has_comparator,
                                    human_reviewed=human_reviewed)

    caveats = [
        "Before/after comparison is descriptive; no causal attribution without a suitable control design.",
        "Capacity value is potential economic capacity, not realized cash savings, until redeployment or avoided expenditure is documented.",
        "The AI suggestion is not evidence that the intervention caused the observed change.",
    ]
    reversal = check_strata_reversal(strata or [])
    if reversal["reversal"]:
        caveats.append("SIMPSON_FLAG: " + reversal["detail"])
    caveats.extend(extra_caveats or [])

    assumptions = (assumptions or []) + [
        "Loaded hourly rate is an assumption, not a measured labor cost.",
        "Inference cost covers recorded AI calls for this case; unrecorded calls are excluded.",
    ]

    return OutcomeAssessmentRecord(
        id=uuid.uuid4().hex,
        case_id=case_id,
        baseline_json=json.dumps({"minutes_per_period": baseline_minutes_per_period, "periods": periods}),
        observed_json=json.dumps({"minutes_per_period": observed_minutes_per_period}),
        comparator_json=json.dumps({"present": has_comparator}) if has_comparator else None,
        opportunity_type="time_capacity",
        unit_economics_json=json.dumps({"loaded_hourly_rate_usd": loaded_hourly_rate_usd,
                                       "delta_minutes": delta_minutes}),
        operational_benefit_usd_micros=benefit_micros,
        intervention_cost_usd_micros=intervention_micros,
        inference_cost_usd_micros=inference_cost_usd_micros,
        other_known_cost_usd_micros=other_micros,
        modeled_net_usd_micros=modeled_net,
        roi_percent=roi,
        attribution_status=attribution,
        evidence_quality=evidence_quality,  # type: ignore[arg-type]
        assumptions_json=json.dumps(assumptions),
        caveats_json=json.dumps(caveats),
        realization_type=realization,  # type: ignore[arg-type]
        data_version="synthetic-v1",
        created_at=utc_now(),
    )
