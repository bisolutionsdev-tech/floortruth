"""FinOps ledger tests: pricing math, micros integrity, value assessment.

No live Meta calls. Money assertions use integer USD micros, never float.
"""
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.store import DemoStore
from app.finops.ledger import FinOpsStore
from app.finops import value as value_mod
from app.finops.pricing import (
    PRICEBOOK_VERSION, PRICING_SOURCE_URL, cost_for_usage, InvalidUsageError,
    UnknownPriceError, micros_to_usd_str,
)
from migrations import run_migrations


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    db = tmp_path / "finops.sqlite3"
    monkeypatch.setattr(main, "store", DemoStore(db_path=db))
    monkeypatch.setattr(main, "finops", FinOpsStore(db_path=db))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FLOORTRUTH_ENABLE_MODEL_API", raising=False)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_pricebook_seeded_with_provenance():
    with main.finops._conn() as db:
        rows = db.execute(
            "SELECT model, meter, rate_per_unit_micros, effective_from, citation_url, last_verified_at "
            "FROM pricebook_entries WHERE version=?", (PRICEBOOK_VERSION,)).fetchall()
    assert len(rows) == 17
    spark = [r for r in rows if r["model"] == "muse-spark-1.3"]
    rates = {r["meter"]: r["rate_per_unit_micros"] for r in spark}
    assert rates == {"input_text": 1_250_000, "cached_input_text": 150_000, "output_text": 4_250_000}
    assert all(r["citation_url"] == PRICING_SOURCE_URL and r["effective_from"] == "2026-10-29"
               and r["last_verified_at"] == "2026-10-29" for r in rows)


def test_cost_vector_2000_400_spark(client):
    r = client.post("/api/finops/estimate",
                    json={"model": "muse-spark-1.3", "input_tokens": 2000, "output_tokens": 400}).json()
    assert r["estimated_cost_usd_micros"] == 4200
    assert r["estimated_cost_usd"] == "0.004200"
    assert isinstance(r["estimated_cost_usd_micros"], int)  # never float


def test_cached_input_deducted_once():
    with main.finops._conn() as db:
        r = cost_for_usage(db, "muse-spark-1.3", input_tokens=2000,
                           cached_input_tokens=500, output_tokens=400)
    # 1500 @ $1.25 + 500 @ $0.15 + 400 @ $4.25  (per 1M)
    assert r.cost_usd_micros == 1875 + 75 + 1700
    assert r.breakdown_micros["cached_input_text_micros"] == 75


def test_unknown_usage_is_null_not_zero(client):
    r = client.post("/api/finops/estimate", json={"model": "muse-spark-1.3"}).json()
    assert r["estimated_cost_usd_micros"] is None
    assert r["estimated_cost_usd"] is None


def test_invalid_usage_rejected():
    with main.finops._conn() as db:
        with pytest.raises(InvalidUsageError):
            cost_for_usage(db, "muse-spark-1.3", input_tokens=100, cached_input_tokens=200)
        with pytest.raises(UnknownPriceError):
            cost_for_usage(db, "model-does-not-exist", input_tokens=10, output_tokens=10)


def test_credits_do_not_change_economic_cost():
    """A credit is billing relief, not lower compute cost: economic cost is invariant."""
    with main.finops._conn() as db:
        r = cost_for_usage(db, "muse-spark-1.3", input_tokens=2000, output_tokens=400)
    economic = r.cost_usd_micros
    credit_micros = 4200
    out_of_pocket = max(0, economic - credit_micros)
    assert economic == 4200 and out_of_pocket == 0  # ledger keeps the economic figure


def test_micros_display_never_float():
    assert micros_to_usd_str(4200) == "0.004200"
    assert micros_to_usd_str(1) == "0.000001"
    assert micros_to_usd_str(None) is None


def test_migrations_idempotent(tmp_path):
    db = sqlite3.connect(tmp_path / "m.sqlite3")
    assert run_migrations(db) == 2
    assert run_migrations(db) == 2  # re-run is a no-op
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"events", "workflow_runs", "inference_events", "pricebook_entries",
            "budget_policies", "budget_decisions", "outcome_assessments",
            "schema_migrations"} <= tables


def test_ledger_survives_restart(client, tmp_path):
    fp = client.get("/api/cases/CASE-HANDOFF").json()["evidence_fingerprint"]
    client.post("/api/cases/CASE-HANDOFF/ai")
    client.post("/api/cases/CASE-HANDOFF/approve", json={"evidence_fingerprint": fp})
    client.post("/api/cases/CASE-HANDOFF/measure", json={})
    before = client.get("/api/finops/summary").json()
    assert before["inference_events"] >= 1
    fresh = FinOpsStore(db_path=main.finops.db_path)
    after = fresh.summary()
    assert after["total_economic_cost_usd_micros"] == before["total_economic_cost_usd_micros"]
    assert after["inference_events"] == before["inference_events"]


def test_baseline_value_math_preserved_and_inference_added(client):
    fp = client.get("/api/cases/CASE-HANDOFF").json()["evidence_fingerprint"]
    client.post("/api/cases/CASE-HANDOFF/ai")  # 4200 micros recorded
    client.post("/api/cases/CASE-HANDOFF/approve", json={"evidence_fingerprint": fp})
    meas = client.post("/api/cases/CASE-HANDOFF/measure", json={}).json()
    assert meas["estimated_gross_value"] == 280 and meas["estimated_net_value"] == 160  # v0.2 intact
    value = client.get("/api/cases/CASE-HANDOFF/value").json()
    a = value["assessment"]
    assert value["inference_cost_usd_micros"] == 4200
    # Net updates mathematically: 280.0000 - (120.0000 + 0.0042)
    assert a["modeled_net_usd_micros"] == 280_000_000 - 120_000_000 - 4_200
    assert a["attribution_status"] == "DESCRIPTIVE_ONLY"
    assert a["realization_type"] == "capacity_equivalent"


def test_roi_null_when_denominator_zero():
    a = value_mod.assess(case_id="CASE-X", baseline_minutes_per_period=34,
                         observed_minutes_per_period=22, periods=40,
                         loaded_hourly_rate_usd=35, intervention_cost_usd=0,
                         inference_cost_usd_micros=None, other_known_cost_usd=0)
    assert a.roi_percent is None
    assert a.modeled_net_usd_micros == 280_000_000


def test_double_count_refused():
    with pytest.raises(ValueError, match="Double count"):
        value_mod.assess(case_id="CASE-X", baseline_minutes_per_period=34,
                         observed_minutes_per_period=22, periods=40,
                         loaded_hourly_rate_usd=35, cash_labor_savings_usd=100.0)


def test_simpson_paradox_flagged():
    import pathlib
    fixture = json.loads(pathlib.Path("tests/fixtures/simpsons_paradox.json").read_text())
    check = value_mod.check_strata_reversal(fixture["strata"])
    assert check["reversal"] is True
    a = value_mod.assess(case_id="CASE-X", baseline_minutes_per_period=48,
                         observed_minutes_per_period=26, periods=10,
                         loaded_hourly_rate_usd=35, strata=fixture["strata"])
    assert any("SIMPSON_FLAG" in c for c in json.loads(a.caveats_json))


def test_attribution_clamp():
    assert value_mod.clamp_attribution("CAUSAL_EVIDENCE_REVIEWED",
                                       has_comparator=False, human_reviewed=True) == "DESCRIPTIVE_ONLY"
    assert value_mod.clamp_attribution("CAUSAL_EVIDENCE_REVIEWED",
                                       has_comparator=True, human_reviewed=False) == "CONTROLLED_ASSOCIATION"
    assert value_mod.clamp_attribution("CAUSAL_EVIDENCE_REVIEWED",
                                       has_comparator=True, human_reviewed=True) == "CAUSAL_EVIDENCE_REVIEWED"
