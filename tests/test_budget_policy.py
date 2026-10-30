"""Budget policy tests: deterministic ALLOW/WARN/HOLD, pre-call gating, idempotency."""
import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.store import DemoStore
from app.finops.ledger import FinOpsStore
from app.finops import policy as budget_policy
from app.finops.models import BudgetPolicyRecord, InferenceEventRecord


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    db = tmp_path / "budget.sqlite3"
    monkeypatch.setattr(main, "store", DemoStore(db_path=db))
    monkeypatch.setattr(main, "finops", FinOpsStore(db_path=db))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FLOORTRUTH_ENABLE_MODEL_API", raising=False)


@pytest.fixture
def client():
    return TestClient(main.app)


def _policy(**over):
    base = dict(id="test", scope_type="global", scope_id="test",
                daily_limit_usd_micros=15_000_000, run_limit_usd_micros=None,
                token_soft_limit=None, request_limit=100,
                per_call_estimate_cap_usd_micros=250_000,
                action_on_limit="HOLD", enabled=True, synthetic=True)
    base.update(over)
    return BudgetPolicyRecord(**base)


def test_allow_within_budget():
    d = budget_policy.evaluate(_policy(), current_spend_usd_micros=0, current_calls=0,
                               projected_cost_usd_micros=4_200, projected_tokens=2400)
    assert d.decision == "ALLOW" and d.reason == budget_policy.REASON_WITHIN_BUDGET


def test_hold_per_call_cap():
    d = budget_policy.evaluate(_policy(), current_spend_usd_micros=0, current_calls=0,
                               projected_cost_usd_micros=300_000)
    assert d.decision == "HOLD" and d.reason == budget_policy.REASON_PER_CALL_CAP


def test_hold_daily_limit():
    d = budget_policy.evaluate(_policy(daily_limit_usd_micros=5_000),
                               current_spend_usd_micros=4_000, current_calls=0,
                               projected_cost_usd_micros=4_200)
    assert d.decision == "HOLD" and d.reason == budget_policy.REASON_DAILY_LIMIT


def test_hold_request_limit():
    d = budget_policy.evaluate(_policy(request_limit=2),
                               current_spend_usd_micros=0, current_calls=2,
                               projected_cost_usd_micros=100)
    assert d.decision == "HOLD" and d.reason == budget_policy.REASON_REQUEST_LIMIT


def test_warn_token_soft_limit():
    d = budget_policy.evaluate(_policy(token_soft_limit=1000),
                               current_spend_usd_micros=0, current_calls=0,
                               projected_cost_usd_micros=100, projected_tokens=5000)
    assert d.decision == "WARN" and d.reason == budget_policy.REASON_TOKEN_SOFT


def test_disabled_policy_allows_with_reason():
    d = budget_policy.evaluate(_policy(enabled=False), current_spend_usd_micros=10**12,
                               current_calls=10**6, projected_cost_usd_micros=10**12)
    assert d.decision == "ALLOW" and d.reason == budget_policy.REASON_POLICY_DISABLED


def test_env_configures_defaults(monkeypatch):
    monkeypatch.setenv("FLOORTRUTH_MAX_MODEL_SPEND_USD", "7.50")
    monkeypatch.setenv("FLOORTRUTH_MAX_CALLS_PER_RUN", "10")
    monkeypatch.setenv("FLOORTRUTH_PER_CALL_ESTIMATE_CAP_USD", "0.10")
    p = budget_policy.default_policy()
    assert p.daily_limit_usd_micros == 7_500_000
    assert p.request_limit == 10
    assert p.per_call_estimate_cap_usd_micros == 100_000


def test_hold_precedes_model_call(client, monkeypatch):
    """A budget HOLD returns 429 and records the decision; no inference is attempted."""
    monkeypatch.setenv("FLOORTRUTH_PER_CALL_ESTIMATE_CAP_USD", "0.0001")  # $0.0001 < $0.0042 quote
    main.finops._ensure_default_policy()  # policy row already exists; re-seed is ignored
    # Force the in-memory policy path: patch the stored policy via a fresh policy row
    with main.finops._conn() as db:
        db.execute("UPDATE budget_policies SET per_call_estimate_cap_usd_micros=? WHERE id='default-global'",
                   (100,))
    before = client.get("/api/finops/summary").json()["inference_events"]
    r = client.post("/api/cases/CASE-HANDOFF/ai")
    assert r.status_code == 429
    body = r.json()["detail"]
    assert body["reason"] == budget_policy.REASON_PER_CALL_CAP
    assert body["budget_decision_id"]
    after = client.get("/api/finops/summary").json()["inference_events"]
    assert after == before  # no inference event recorded
    decisions = client.get("/api/governance/decisions").json()["decisions"]
    assert any(d["decision"] == "HOLD" and d["reason"] == budget_policy.REASON_PER_CALL_CAP
               for d in decisions)
    runs = client.get("/api/cases/CASE-HANDOFF/workflows").json()["workflow_runs"]
    assert runs and runs[0]["status"] == "held"


def test_duplicate_callback_does_not_double_post():
    evt = InferenceEventRecord(id="evt-1", request_id="req-dup", attempt_no=1,
                               operation="hypothesis_generation", provider="mock",
                               model="mock-deterministic-v1", usage_source="estimated",
                               input_tokens=2000, output_tokens=400,
                               estimated_cost_usd_micros=4200, status="succeeded",
                               synthetic=True)
    _, created1 = main.finops.record_inference_event(evt)
    _, created2 = main.finops.record_inference_event(evt)
    assert created1 is True and created2 is False
    assert main.finops.summary()["inference_events"] == 1
    assert main.finops.summary()["total_economic_cost_usd_micros"] == 4200
