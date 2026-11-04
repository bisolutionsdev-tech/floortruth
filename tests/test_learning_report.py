"""The portable report reflects the synthetic case and its decision history."""
from fastapi.testclient import TestClient

import app.main as main
from app.finops.ledger import FinOpsStore
from app.store import DemoStore


def test_report_tracks_case_history_and_marks_stale_outcomes(tmp_path, monkeypatch):
    db_path = tmp_path / "demo.sqlite3"
    monkeypatch.setattr(main, "store", DemoStore(db_path))
    monkeypatch.setattr(main, "finops", FinOpsStore(db_path))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FLOORTRUTH_ENABLE_MODEL_API", raising=False)
    client = TestClient(main.app)
    case_path = "/api/cases/CASE-HANDOFF"

    assert client.get("/api/cases/UNKNOWN/export").status_code == 404
    fingerprint = client.get(case_path).json()["evidence_fingerprint"]
    assert client.post(case_path + "/approve", json={"evidence_fingerprint": fingerprint}).status_code == 200
    assert client.post(case_path + "/measure", json={}).status_code == 200
    assert client.get(case_path + "/export").json()["assessment_is_current"] is True
    assert client.post(case_path + "/ai").status_code == 200

    response = client.get(case_path + "/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    report = response.json()
    assert report["synthetic"] is True
    assert report["case"]["status"] == "Measured"
    assert report["assessment_is_current"] is False
    assert client.get(case_path + "/value").json()["assessment_is_current"] is False
    assert {source["id"] for source in report["sources"]} == set(report["case"]["evidence_ids"])
    assert [e["event_type"] for e in report["decision_and_outcome_history"]] == [
        "PILOT_APPROVED", "OUTCOME_RECORDED", "INFERENCE_RECORDED"
    ]
    assert report["inference_cost_usd_micros"] == 4200
    assert report["latest_outcome_assessment"]["attribution_status"] == "DESCRIPTIVE_ONLY"
    assert report["audit_integrity"]["valid"] is True

    # A new measurement incorporates the additional inference cost.
    assert client.post(case_path + "/measure", json={}).status_code == 200
    assert client.get(case_path + "/export").json()["assessment_is_current"] is True

    assert client.post(case_path + "/rollback", json={"reason": "Demo rollback"}).status_code == 200
    rolled_back = client.get(case_path + "/export").json()
    assert rolled_back["case"]["status"] == "Rolled back"
    assert rolled_back["assessment_is_current"] is False
    assert rolled_back["decision_and_outcome_history"][-1]["event_type"] == "PILOT_ROLLED_BACK"


def test_report_does_not_treat_unknown_inference_cost_as_current(tmp_path, monkeypatch):
    db_path = tmp_path / "demo.sqlite3"
    monkeypatch.setattr(main, "store", DemoStore(db_path))
    monkeypatch.setattr(main, "finops", FinOpsStore(db_path))
    monkeypatch.setenv("MODEL_API_KEY", "test-only")
    monkeypatch.setenv("FLOORTRUTH_ENABLE_MODEL_API", "true")
    monkeypatch.setattr(main.meta_chat.MetaChatProvider, "analyze", lambda *args: {
        "mode": "unavailable", "model": "muse-spark-1.3",
        "usage": {"usage_source": "not_reported"},
    })
    client = TestClient(main.app)
    path = "/api/cases/CASE-HANDOFF"
    fingerprint = client.get(path).json()["evidence_fingerprint"]
    client.post(path + "/approve", json={"evidence_fingerprint": fingerprint})
    client.post(path + "/ai")
    client.post(path + "/measure", json={})
    report = client.get(path + "/export").json()
    assert report["inference_cost_usd_micros"] is None
    assert report["inference_events_with_unknown_cost"] == 1
    assert report["assessment_is_current"] is False
