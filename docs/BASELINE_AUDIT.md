# FloorTruth v0.2 Baseline Audit — 29 Oct 2026

**Purpose:** Reproducible record of the v0.2 baseline before v0.3 build work. All facts verified by inspection/test run on 2026-10-29.

## Test suite

- Command: `.venv/bin/python -m pytest -q` (python 3.12)
- Result: **13 passed** (tests/test_app.py, 13 test functions — count verified, not assumed)
- Deps (requirements.txt): fastapi>=0.115,<1 · uvicorn>=0.30,<1 · pydantic>=2.7,<3 · pytest>=8,<10 · httpx>=0.27,<1

## Endpoints (all preserved for v0.3)

GET /api/health · GET /api/dashboard · GET /api/signals · POST /api/signals ·
GET /api/cases · GET /api/cases/{id} · POST /api/cases/{id}/approve ·
POST /api/cases/{id}/measure · POST /api/cases/{id}/rollback ·
GET /api/cases/{id}/timeline · GET /api/audit/verify · POST /api/cases/{id}/ai

## Data & behavior verified

- 9 fictional seed observations (OBS-1041..OBS-1049), 3 topic cases; all records synthetic.
- Deterministic keyword topic classifier; evidence fingerprint = sha256 of sorted evidence records.
- Stale fingerprint → HTTP 409; rollback blocks re-measurement until fresh approval.
- Hash-chained SQLite events (`.floortruth/demo.sqlite3`); chain tamper-evident only, **not signed, not access-controlled**; auth not implemented (reviewer role is demo-supplied).
- Deterministic math sanity case: 34 vs 22 min × 40 periods @ $35/h → 480 min, **$280 gross, $120 pilot cost, $160 net, 133.3% ROI** — descriptive only, not causal, not cash.
- Meta adapter (`app/meta_adapter.py`): Chat Completions + JSON schema + local source-ID validation; **disabled by default** (`FLOORTRUTH_ENABLE_MODEL_API=false`, no key in this environment).
- `main.py` uses global `DemoStore`; tests replace it via monkeypatch. `store.audit_model()` only logs when mode != "demo".

## Known debt (carried into v0.3, not regressions)

1. `docs/ARCHITECTURE.md` contains stale v0.1 notes — do not copy claims about missing persistence/grounding into new docs.
2. No token-level cost ledger, no per-workflow budgets, no durable model response records (v0.3 scope).
3. No authN/authZ; UI role labels are not authorization.
4. Redaction is regex-only (email/phone), not production PII detection.
5. No connector implementations beyond local synthetic flow.
6. UI is a single-file JS app (web/app.js ~22KB); no build step, no external assets.

## Rule uncertainties (hackathon)

- Public event page still shows outdated "rules will be published"; accepted participant/Discord terms govern. Logged here as unchecked — local development does not stall on it.
- Meta processing mode cannot be verified in this environment → no live Meta calls; Standard/Contributor mode asserts nothing.

## v0.3 build order (per handoff §12)

M1 durable token/economic ledger → M2 evidence/governance integration → M3 live-Meta prep (mock-active, no key) → M4 UX + connector mocks → M5 evaluation/demo/docs.
