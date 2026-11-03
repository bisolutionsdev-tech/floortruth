"""Connector registry tests: honest labels, disabled writes, typed contracts."""
import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.store import DemoStore
from app.finops.ledger import FinOpsStore
from app.integrations import registry as connector_registry
from app.integrations.contracts import (
    ConnectorDescriptor, ConnectorStatus, NotificationDraft, ObservationBatch,
    SuggestedTicket,
)
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    db = tmp_path / "integ.sqlite3"
    monkeypatch.setattr(main, "store", DemoStore(db_path=db))
    monkeypatch.setattr(main, "finops", FinOpsStore(db_path=db))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FLOORTRUTH_ENABLE_MODEL_API", raising=False)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_registry_labels_are_honest(client):
    data = client.get("/api/integrations").json()
    connectors = data["connectors"]
    assert len(connectors) >= 8
    allowed = {"Available", "Mocked", "Planned", "Disabled"}
    for c in connectors:
        assert c["status"] in allowed, c["connector_id"]
        assert c["synthetic"] is True
    by_id = {c["connector_id"]: c for c in connectors}
    assert by_id["notification"]["status"] == "Disabled"
    assert by_id["policy-engine"]["status"] == "Available"
    assert by_id["ticketing-generic"]["status"] == "Planned"
    assert by_id["synthetic-mes-001"]["status"] == "Mocked"


def test_no_live_external_writes_claimed(client):
    data = client.get("/api/integrations").json()
    for c in data["connectors"]:
        if c["capability"] == "external_write":
            assert c["status"] == "Disabled", c["connector_id"]
    assert SuggestedTicket(title="t", body="b", case_id="CASE-HANDOFF").external_write_status == "NOT_CONFIGURED"
    assert NotificationDraft(audience="a", subject="s", body="b").send_status == "NOT_SENT_DEMO"


def test_provider_status_is_honest(client):
    status = client.get("/api/integrations").json()["inference_provider"]
    assert status["active_provider"] == "mock"
    assert status["meta_configured"] is False
    assert status["live_api"] == "LIVE_API_NOT_VERIFIED"


def test_configured_provider_status_reports_selected_model_without_key(client, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "secret-test-value")
    monkeypatch.setenv("FLOORTRUTH_ENABLE_MODEL_API", "true")
    monkeypatch.setenv("META_MODEL", "muse-spark-1.2")
    status = client.get("/api/integrations").json()["inference_provider"]
    assert status["meta_model"] == "muse-spark-1.2"
    assert status["meta_model_allowed"] is True
    assert status["active_provider"] == "meta"
    assert "unverified" in status["live_api"]
    assert "secret-test-value" not in str(status)
    monkeypatch.setenv("META_MODEL", "secret-test-value")
    status = client.get("/api/integrations").json()["inference_provider"]
    assert status["meta_model"] is None
    assert status["meta_model_allowed"] is False
    assert "secret-test-value" not in str(status)


def test_provider_normalizes_nested_usage_and_preserves_zero(monkeypatch, client):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("FLOORTRUTH_ENABLE_MODEL_API", "true")
    monkeypatch.setattr(main.meta_chat.meta_adapter, "suggest", lambda *args: {
        "mode": "meta", "model": "muse-spark-1.3", "usage": {
            "prompt_tokens": 2000, "completion_tokens": 400,
            "prompt_tokens_details": {"cached_tokens": 300},
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    })
    response = client.post("/api/cases/CASE-HANDOFF/ai")
    assert response.status_code == 200
    event = client.get("/api/finops/ledger").json()["items"][0]
    assert event["cached_input_tokens"] == 300
    assert event["reasoning_tokens"] == 0


@pytest.mark.parametrize("code,category", [(401, "AUTHENTICATION_OR_ACCESS"), (402, "BILLING_OR_CREDITS"),
                                          (429, "RATE_LIMIT"), (503, "PROVIDER_UNAVAILABLE")])
def test_meta_http_failures_are_classified_without_exposing_body(client, monkeypatch, code, category):
    from io import BytesIO
    from urllib.error import HTTPError
    monkeypatch.setenv("MODEL_API_KEY", "secret-test-value")
    monkeypatch.setenv("FLOORTRUTH_ENABLE_MODEL_API", "true")
    def reject(*args, **kwargs):
        raise HTTPError("https://api.meta.ai/", code, "secret-test-value", None,
                        BytesIO(b"secret-test-value"))
    monkeypatch.setattr(main.meta_chat.meta_adapter, "urlopen", reject)
    response = client.post("/api/cases/CASE-HANDOFF/ai")
    data = response.json()
    assert data["error_category"] == category
    assert data["http_status"] == code
    assert "secret-test-value" not in response.text


def test_live_request_caps_completion_and_handles_truncation(client, monkeypatch):
    import json
    from io import BytesIO
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("FLOORTRUTH_ENABLE_MODEL_API", "true")
    seen = {}
    def incomplete(request, timeout):
        seen.update(json.loads(request.data))
        return BytesIO(json.dumps({
            "choices": [{"finish_reason": "length", "message": {"content": "partial"}}],
            "usage": {"prompt_tokens": 2000, "completion_tokens": 1600},
        }).encode())
    monkeypatch.setattr(main.meta_chat.meta_adapter, "urlopen", incomplete)
    result = client.post("/api/cases/CASE-HANDOFF/ai").json()
    assert seen["max_completion_tokens"] == main.meta_chat.meta_adapter.MAX_COMPLETION_TOKENS == 1600
    assert seen["reasoning_effort"] == "low"
    assert result["error_category"] == "OUTPUT_LIMIT"
    assert result.get("analysis") is None
    event = client.get("/api/finops/ledger").json()["items"][0]
    assert event["status"] == "unavailable"
    assert event["output_tokens"] == 1600


def test_provider_preserves_zero_reported_tokens(monkeypatch):
    monkeypatch.setattr(main.meta_chat.meta_adapter, "enabled", lambda: True)
    monkeypatch.setattr(main.meta_chat.meta_adapter, "suggest", lambda *args: {
        "mode": "meta", "model": "muse-spark-1.3",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    })
    result = main.meta_chat.MetaChatProvider().analyze({"id": "C", "title": "t"}, [], "fp")
    assert result["usage"]["input_tokens"] == 0
    assert result["usage"]["output_tokens"] == 0


def test_contracts_reject_bad_batches():
    with pytest.raises(ValidationError):
        ObservationBatch(batch_id="b", source_system="s", records="not-a-list",
                         idempotency_key="k")
    # No unrestricted URL fields anywhere on the descriptor (SSRF guard).
    fields = set(ConnectorDescriptor.model_fields)
    assert not ({"url", "endpoint", "callback_url"} & fields)


def test_registry_lookup():
    assert connector_registry.get_connector("csv-import")["status"] == "Mocked"
    assert connector_registry.get_connector("nope") is None
    assert all(c.status in ConnectorStatus for c in connector_registry.REGISTRY)
