"""Generate the deterministic v0.3 judge demo trace from a clean database.

Runs the full vertical slice against a throwaway SQLite DB:
capture -> correlate -> budget-gated mock AI -> human approval -> measurement ->
value assessment (with inference cost) -> rollback. Writes docs/demo_trace_v0.3.json.

Usage: .venv/bin/python scripts/generate_demo_trace.py
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
import app.main as main  # noqa: E402
from app.store import DemoStore  # noqa: E402
from app.finops.ledger import FinOpsStore  # noqa: E402

TRACE_PATH = ROOT / "docs" / "demo_trace_v0.3.json"


def main_trace() -> dict:
    tmp = tempfile.mkdtemp(prefix="floortruth-demo-")
    db = str(Path(tmp) / "demo.sqlite3")
    main.store = DemoStore(db_path=db)
    main.finops = FinOpsStore(db_path=db)
    client = TestClient(main.app)
    steps: list[dict] = []

    def step(name: str, payload: dict) -> dict:
        steps.append({"step": name, **payload})
        return payload

    # 1. Capture a synthetic night-shift observation.
    sig = client.post("/api/signals", json={
        "text": "Night shift handoff again missed the calibration step; startup delayed twenty minutes.",
        "shift": "Night", "channel": "Text", "location": "Zone B"}).json()
    step("capture", {"observation_id": sig["id"], "synthetic": True})

    # 2. Correlate: one evidence case across shifts.
    case = client.get("/api/cases/CASE-HANDOFF").json()
    step("correlate", {"case_id": case["id"], "report_count": case["report_count"],
                       "shifts": case["shifts"],
                       "evidence_fingerprint": case["evidence_fingerprint"][:16] + "..."})

    # 3. Budget-gated AI analysis (mock provider; deterministic).
    ai = client.post("/api/cases/CASE-HANDOFF/ai").json()
    step("ai_analysis", {"mode": ai["mode"], "provider": ai["provider"],
                         "budget_decision": ai["budget_decision"]["decision"],
                         "budget_reason": ai["budget_decision"]["reason"],
                         "inference_cost_usd": ai["inference_cost_usd"],
                         "hypotheses": len(ai.get("hypotheses", [])),
                         "hypothesis_status": [h["status"] for h in ai.get("hypotheses", [])]})

    # 4. Simulated human review approves a reversible pilot.
    fp = client.get("/api/cases/CASE-HANDOFF").json()["evidence_fingerprint"]
    approval = client.post("/api/cases/CASE-HANDOFF/approve",
                           json={"evidence_fingerprint": fp}).json()
    step("human_approval", {"status": approval["status"],
                            "reviewer_role": approval["reviewer_role"],
                            "approval_scope": approval["approval_scope"]})

    # 5. Measure the pilot (descriptive).
    measurement = client.post("/api/cases/CASE-HANDOFF/measure", json={}).json()
    step("measure", {"delta_minutes": measurement["delta_minutes"],
                     "estimated_gross_value": measurement["estimated_gross_value"],
                     "estimated_net_value": measurement["estimated_net_value"],
                     "causality": measurement["causality"]})

    # 6. Value assessment WITH inference cost.
    value = client.get("/api/cases/CASE-HANDOFF/value").json()
    a = value["assessment"]
    step("value", {"inference_cost_usd": value["inference_cost_usd"],
                   "modeled_net_usd_micros": a["modeled_net_usd_micros"],
                   "roi_percent": a["roi_percent"],
                   "attribution_status": a["attribution_status"],
                   "evidence_quality": a["evidence_quality"],
                   "realization_type": a["realization_type"]})

    # 7. Rollback demonstration (reversibility).
    rb = client.post("/api/cases/CASE-HANDOFF/rollback",
                     json={"reason": "Demo rollback: pilot window complete"}).json()
    step("rollback", {"status": rb["status"], "scope": rb["scope"]})

    # 8. Ledger + audit integrity.
    summary = client.get("/api/finops/summary").json()
    audit = client.get("/api/audit/verify").json()
    step("ledger", {"inference_events": summary["inference_events"],
                    "total_economic_cost_usd_micros": summary["total_economic_cost_usd_micros"],
                    "pricebook_version": summary["pricebook_version"],
                    "audit_integrity": audit["integrity"]})

    trace = {
        "trace_version": "0.3",
        "synthetic": True,
        "generated": "2026-10-29",
        "provider": "mock (LIVE_API_NOT_VERIFIED)",
        "pricebook_version": "2026-10-29",
        "steps": steps,
        "notes": [
            "All records invented. No employer data.",
            "Inference cost is modeled economic cost, not proof of token-attributable value.",
            "Attribution stays DESCRIPTIVE_ONLY: no causal claims.",
            "Hash chain is tamper-evident only, not signed; reviewer role is simulated.",
        ],
    }
    TRACE_PATH.write_text(json.dumps(trace, indent=2))
    return trace


if __name__ == "__main__":
    trace = main_trace()
    print(f"Wrote {TRACE_PATH} ({len(trace['steps'])} steps)")
