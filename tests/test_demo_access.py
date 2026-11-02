import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.demo_access import COOKIE_NAME, _attempts, _session, _signing_key


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("FLOORTRUTH_DEMO_ACCESS", "true")
    monkeypatch.setenv("FLOORTRUTH_DEMO_PASSWORD", "correct horse battery staple")
    monkeypatch.setenv("FLOORTRUTH_SESSION_SECRET", "a-different-secret-that-is-at-least-32-characters")
    _attempts.clear()


@pytest.fixture
def client():
    return TestClient(main.app, base_url="https://testserver", follow_redirects=False)


def login(client, password="correct horse battery staple"):
    return client.post("/demo-login", data={"password": password})


def test_gate_requires_login_and_sets_secure_cookie(client):
    assert client.get("/").headers["location"] == "/demo-login"
    assert client.get("/api/dashboard").status_code == 401
    assert login(client, "incorrect").status_code == 401
    response = login(client)
    assert response.status_code == 303
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/dashboard").status_code == 200


def test_public_health_is_minimal_and_authenticated_health_is_full(client, monkeypatch):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"ok": True}
    assert health.headers["cache-control"] == "no-store"
    head = client.head("/api/health")
    assert head.status_code == 200 and head.content == b""
    assert client.post("/api/health").status_code == 401
    login(client)
    authenticated = client.get("/api/health")
    assert authenticated.status_code == 200
    assert "inference_provider" in authenticated.json()
    monkeypatch.setenv("FLOORTRUTH_SESSION_SECRET", "short")
    assert client.get("/api/health").status_code == 503
    assert client.head("/api/health").status_code == 503


def test_tampering_expiry_and_rotation_invalidate_session(client, monkeypatch):
    login(client)
    cookie = client.cookies[COOKIE_NAME]
    client.cookies.set(COOKIE_NAME, cookie + "x", domain="testserver.local", path="/")
    assert client.get("/api/dashboard").status_code == 401
    login(client)
    monkeypatch.setenv("FLOORTRUTH_DEMO_PASSWORD", "different demo password")
    assert client.get("/api/dashboard").status_code == 401
    key = _signing_key("a-different-secret-that-is-at-least-32-characters", "different demo password")
    monkeypatch.setattr("app.demo_access.SESSION_SECONDS", -1)
    expired = _session(key)
    client.cookies.set(COOKIE_NAME, expired, domain="testserver.local", path="/")
    assert client.get("/api/dashboard").status_code == 401


def test_configuration_fails_closed_and_origin_rejected(client, monkeypatch):
    monkeypatch.setenv("FLOORTRUTH_SESSION_SECRET", "short")
    assert client.get("/").status_code == 503
    monkeypatch.setenv("FLOORTRUTH_SESSION_SECRET", "a-different-secret-that-is-at-least-32-characters")
    assert client.post("/demo-login", data={"password": "correct horse battery staple"},
                       headers={"Origin": "https://attacker.example"}).status_code == 403
    login(client)
    assert client.post("/api/cases/CASE-HANDOFF/ai", headers={"Origin": "https://attacker.example"}).status_code == 403


def test_login_attempts_are_throttled(client):
    for _ in range(10):
        assert login(client, "wrong").status_code == 401
    assert login(client).status_code == 429


def test_gate_can_be_disabled_for_local_demo(client, monkeypatch):
    monkeypatch.setenv("FLOORTRUTH_DEMO_ACCESS", "false")
    assert client.get("/api/health").status_code == 200
