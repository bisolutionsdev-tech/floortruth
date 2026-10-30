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
