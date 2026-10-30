"""Pure demo analysis and measurement logic.

All examples are synthetic. No employee-identifying records or actual site data.
The baseline engine is intentionally deterministic and auditable.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any

TOPICS = {
    "handoff": ("handoff", "start-up", "startup", "station ready", "readiness", "checklist", "calibration", "shift change"),
    "replenishment": ("replenishment", "supplies", "packing material", "cartons", "refill", "stock", "packaging"),
    "access": ("training", "access", "learning", "sign-in", "credential", "login"),
    "other": (),
}

TOPIC_NAMES = {
    "handoff": "Equipment readiness across shifts",
    "replenishment": "Materials replenishment delays",
    "access": "Learning access and readiness",
    "other": "Emerging observations",
}

HYPOTHESES = {
    "handoff": [
        {"claim": "Shift handoff procedure lacks a reliable equipment-readiness check", "verify": "Observe handoff checkpoints and compare documented versus actual steps"},
        {"claim": "A recurring equipment condition is driving delayed start-up", "verify": "Compare authorized maintenance summaries with observed stoppage times"},
    ],
    "replenishment": [
        {"claim": "Restocking cadence does not align with peak material consumption", "verify": "Compare aggregate material demand against refill cycle timing"},
        {"claim": "Visual stock signals are inconsistently available", "verify": "Audit bin-level replenishment triggers, without individual scoring"},
    ],
    "access": [
        {"claim": "Training access is affected by a shared account or authorization workflow", "verify": "Review de-identified access failures and approved help-desk categories"},
        {"claim": "Learning instructions are unclear during onboarding", "verify": "Test the instructions with voluntary participants"},
    ],
    "other": [
        {"claim": "The reported concern may represent an isolated event", "verify": "Collect additional voluntary observations and relevant aggregate evidence"},
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(text: str) -> str:
    value = text.lower()
    scores = {topic: sum(1 for phrase in words if phrase in value) for topic, words in TOPICS.items() if words}
    best = max(scores, key=scores.get)
    return best if scores[best] else "other"


def summarize_topic(topic: str, signals: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = [s for s in signals if s["topic"] == topic]
    shifts = sorted(set(s["shift"] for s in grouped))
    ids = [s["id"] for s in grouped]
    # Confidence remains qualitative: number of reports is not proof of a cause.
    corroboration = "Multiple independent reports" if len(grouped) >= 3 and len(shifts) >= 2 else "Preliminary observation"
    return {
        "id": "CASE-" + topic.upper(),
        "topic": topic,
        "title": TOPIC_NAMES[topic],
        "report_count": len(grouped),
        "shifts": shifts,
        "evidence_ids": ids,
        "corroboration": corroboration,
        "hypotheses": HYPOTHESES[topic],
        "missing_evidence": "Independent process measurement and an authorized operational comparator",
    }


def correlate(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((summarize_topic(t, signals) for t in TOPIC_NAMES if any(s["topic"] == t for s in signals)), key=lambda x: (-x["report_count"], x["id"]))


def measure(baseline_minutes: float, observed_minutes: float, periods: int, cost_per_hour: float, pilot_cost: float) -> dict[str, Any]:
    if any(x < 0 for x in (baseline_minutes, observed_minutes, periods, cost_per_hour, pilot_cost)) or periods == 0:
        raise ValueError("Values must be nonnegative and periods must be positive")
    delta_minutes = (baseline_minutes - observed_minutes) * periods
    gross = delta_minutes / 60 * cost_per_hour
    net = gross - pilot_cost
    return {
        "baseline_minutes_per_period": baseline_minutes,
        "observed_minutes_per_period": observed_minutes,
        "periods": periods,
        "delta_minutes": round(delta_minutes, 2),
        "estimated_gross_value": round(gross, 2),
        "pilot_cost": pilot_cost,
        "estimated_net_value": round(net, 2),
        "roi_percent": round((net / pilot_cost) * 100, 1) if pilot_cost else None,
        "causality": "Descriptive pilot comparison only. No causal attribution without an appropriate control.",
        "source": "Synthetic demonstration inputs; assumptions stated, not externally verified",
    }


def redact(text: str) -> str:
    """Demo-only safety check: basic email/phone scrub, NOT production PII detection."""
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email-redacted]", text)
    return re.sub(r"(?<!\w)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)", "[phone-redacted]", text)
