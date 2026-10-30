# FloorTruth v0.3 — organizational learning, with receipts

**Recursion Lab · Meta Global AI Developer Hackathon · October 29, 2026**

> **The frontline knows. The enterprise forgets. FloorTruth closes the loop.**

FloorTruth is an original **synthetic-data hackathon prototype** demonstrating a fully traceable flow from voluntary observations to grouped evidence, competing explanations, human-simulated review, reversible pilots, honestly labeled outcome analysis — and now a **token-level inference cost ledger**: every AI call is budget-gated, usage-recorded, priced from a versioned book, and joined to the value story without ever claiming tokens caused dollars.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**. No front-end build or Meta key required. SQLite demo state is stored at `.floortruth/demo.sqlite3` and survives server restarts. To reset, delete `.floortruth/demo.sqlite3` **while the server is stopped**. All records are fictional.

```bash
python -m pytest -q   # 47 tests, all offline
```

## What's new in v0.3

- **Durable FinOps ledger** (SQLite migrations, idempotent): workflow runs, inference events, versioned pricebook, budget policies/decisions, outcome assessments.
- **Integer-micro money math** — never float; unknown usage/prices stay `null`, never `$0.00`. Test vector: 2,000 in + 400 out Spark Standard tokens = **$0.004200**.
- **Pre-call budget governance**: ALLOW/WARN/HOLD decisions recorded before every model call; HOLD returns HTTP 429 with a typed reason enum. Configurable via `FLOORTRUTH_MAX_MODEL_SPEND_USD`, `FLOORTRUTH_MAX_CALLS_PER_RUN`, `FLOORTRUTH_PER_CALL_ESTIMATE_CAP_USD`.
- **Evidence-linked inference**: the server-computed evidence fingerprint travels through AI analysis, review, and the hash-chained timeline (`INFERENCE_RECORDED`).
- **Case value with inference cost**: `/api/cases/{id}/value` folds recorded AI spend into modeled net ($160 → $159.9958 in the demo), attribution locked to `DESCRIPTIVE_ONLY` without comparator + human review, Simpson's-paradox strata check included.
- **Governance & Token Economics screen**: AI Activity / Economics / Policies tabs, per-case drilldown, honest connector registry (Available / Mocked / Planned / Disabled).
- **Mock provider active**; Meta path activates with `MODEL_API_KEY` + `FLOORTRUTH_ENABLE_MODEL_API=true` (see `docs/LIVE_API_SMOKE_TEST.md` — `LIVE_API_NOT_VERIFIED`).

## Quick demo path (3 minutes)

See `docs/DEMO_SCRIPT_v0.3.md`. Deterministic replay: `.venv/bin/python scripts/generate_demo_trace.py` → `docs/demo_trace_v0.3.json`.

1. **Overview → ＋ Capture observation**: invented night-shift note, server-confirmed ID.
2. **Evidence cases → Equipment readiness**: source IDs, competing hypotheses, falsifiers.
3. **Ask Meta adapter**: budget ALLOW first, then two UNVERIFIED hypotheses — $0.004200 ledgered.
4. **Approve demo pilot**: simulated reviewer, fingerprint-checked, scope-labeled.
5. **Experiments**: 34→22 min × 40 @ $35/h → $280 gross, $120 cost, $160 modeled net (descriptive).
6. **Governance & tokens**: the $0.004200 inside the value story; policies and decisions.
7. **Roll back**: status flips, re-measurement blocked until fresh approval.

## API surface (v0.2 routes preserved)

FinOps: `GET /api/finops/summary` · `GET /api/finops/ledger` · `GET /api/finops/pricebook` · `POST /api/finops/estimate`
Cases: `GET /api/cases/{id}/value` · `GET /api/cases/{id}/workflows` (plus all v0.2 routes)
Governance: `GET /api/governance/policies` · `GET /api/governance/decisions`
Integrations: `GET /api/integrations`

## What this is NOT

No real employee login, reviewer authentication, organization connection, production data integration, actual human impact evaluation, full audit security, or external operational action. The human approval gate is **simulated**. The hash chain is tamper-evident, not signed. The model is advisory. The sample ROI is fictional and non-causal. **No live Meta call has been made from this environment.** Budget policies are demo defaults, not billing enforcement. The pricebook is a dated snapshot, not a live rate feed.

## Important project files

- `app/finops/` — pricing, ledger, budget policy, value assessment
- `app/integrations/` — provider layer (mock active), typed connector registry
- `migrations/` — idempotent schema migrations
- `docs/` — handoff, audit, architecture, demo script, evaluation, limitations, checklist, build summary
- `tests/` — 47 tests; `tests/fixtures/simpsons_paradox.json`
- `scripts/generate_demo_trace.py` — deterministic demo trace generator
