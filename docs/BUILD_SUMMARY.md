# FloorTruth v0.3 — Build Summary

**Built:** 2026-10-29 (overnight build agent) · **Baseline:** v0.2, 13/13 tests passing
**Result:** v0.3 P0 scope complete; **47/47 tests pass** (13 baseline preserved, 34 new).
No live Meta calls (no key in environment); mock provider active; `LIVE_API_NOT_VERIFIED`.

## What was built

**M1 — Durable token/economic ledger**
- `migrations/` — idempotent versioned migrations (`schema_migrations` table); v1 events, v2 finops tables.
- `app/finops/` — `models.py` (typed Pydantic entities), `pricing.py` (versioned pricebook seeded with handoff §5.3 Meta Standard rates + provenance URLs + effective dates; integer-USD-micros math), `ledger.py` (`FinOpsStore`: runs, idempotent inference events, policies/decisions, assessments, summaries), `policy.py` (env-configurable ALLOW/WARN/HOLD), `value.py` (outcome math, attribution clamp, double-count refusal, Simpson's-paradox check).
- Test vector verified: 2,000 in + 400 out Spark tokens = **$0.004200** (4,200 micros, six decimals). Unknown usage/prices → `null`, never `$0.00`.

**M2 — Evidence/governance integration**
- `POST /api/cases/{id}/ai` is budget-gated: workflow run → pre-call budget decision → 429 on HOLD (no inference attempted) → provider → ledgered inference event with micros cost → `INFERENCE_RECORDED` timeline event. Evidence fingerprint carried end to end.
- `GET /api/cases/{id}/value` folds recorded inference cost into modeled net ($160 → $159.9958); `GET /api/cases/{id}/workflows` gives full lineage; attribution locked to `DESCRIPTIVE_ONLY` without comparator + human review.

**M3 — Live Meta prep (no key; no calls)**
- `app/integrations/meta_chat.py`: `InferenceProvider` protocol, `MockProvider` (active, deterministic, estimated usage honestly labeled), `MetaChatProvider` (inactive without key). `docs/LIVE_API_SMOKE_TEST.md` documents exact activation + adversarial checks. Nothing claims a live test.

**M4 — UX + connector mocks**
- Governance & Token Economics screen: AI Activity / Economics / Policies tabs, per-case drilldown, connector registry (10 connectors, honest Available/Mocked/Planned/Disabled), SYNTHETIC DEMO chips, 375px-responsive.
- `GET /api/integrations`, `GET /api/governance/policies`, `GET /api/governance/decisions`.

**M5 — Evaluation & artifacts**
- 34 new tests: finops math, budget policy (incl. HOLD→429, duplicate-callback idempotency), adversarial evidence (prompt injection, invented IDs, fingerprint binding, no numeric confidence), integrations honesty, Simpson fixture.
- `docs/demo_trace_v0.3.json` (deterministic 8-step run via `scripts/generate_demo_trace.py`), `DEMO_SCRIPT_v0.3.md`, `EVALUATION_REPORT_v0.3.md`, `KNOWN_LIMITATIONS.md`, `SUBMISSION_CHECKLIST.md`, `ARCHITECTURE_v0.3.md`, `API_CONTRACTS.md`, `BASELINE_AUDIT.md`; README updated.

## Files changed (git log)
- `19c3c7d` v0.2 baseline · `eb03930` M1+M2 · `ae24adf` M4 UI · `8fcd4e0` M5 tests
- New: `migrations/`, `app/finops/`, `app/integrations/`, `scripts/`, `tests/test_finops|budget_policy|evidence|integrations.py`, `tests/fixtures/`, 10 new docs.
- Modified: `app/main.py`, `app/store.py`, `web/`, `README.md`. All v0.2 routes preserved.

## Commands
```bash
cd ~/workspace/floortruth/floortruth-starter
.venv/bin/python -m pytest -q          # 47 passed
.venv/bin/python run.py                # http://127.0.0.1:8000
.venv/bin/python scripts/generate_demo_trace.py
```

## Blockers / owner decisions
1. **Live Meta smoke test** needs the owner's key + Standard-mode confirmation (steps in `docs/LIVE_API_SMOKE_TEST.md`). Nothing is blocked without it.
2. **Hackathon submission**: not performed (per instructions). Checklist in `docs/SUBMISSION_CHECKLIST.md`; deadline Nov 4, 9 PM ET.
3. **Screenshots**: no live browser in this environment; capture from a real session before submitting.
4. **Participant rules**: public page was stale ("rules will be published"); verify accepted Discord/participant terms before submitting.
5. Meta processing mode cannot be verified here — no Standard/Contributor assertions made.
