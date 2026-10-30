# FloorTruth v0.2 — organizational learning, with receipts

**Recursion Lab · Build-window iteration · October 26, 2026**

> **The frontline knows. The enterprise forgets. FloorTruth closes the loop.**

FloorTruth is an original **synthetic-data hackathon prototype** demonstrating a fully traceable flow from voluntary observations to grouped evidence, competing explanations, human-simulated review, reversible pilots, and honestly labeled outcome analysis.

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
python -m pytest -q
```

## What's new in v0.2

- Persisted SQLite event record of synthetic observations, approvals, measurements and rollback.
- Reproducible hash-linked event history with visible integrity verification (not cryptographically signed or truly immutable).
- Evidence snapshot fingerprints: adding a same-topic observation invalidates previous approval and forces re-review.
- Explicit simulated rollback; recorded results restore after server restart.
- Schema-constrained Meta Muse Spark output with second-stage local evidence-ID validation.
- Optional logging of provider usage with individual model evaluation events.
- Twelve deterministic tests across continuity, evidence, math and failure behaviors.

## Quick demo path

1. **Evidence cases → Equipment readiness across shifts**: inspect source IDs and competing hypotheses.
2. **Approve demo pilot**: simulated reviewer gate records the evidence fingerprint.
3. **Experiments**: enter baseline and observed minutes, calculate descriptive ROI.
4. **Evidence case → Roll back**: event and status recorded, no external action performed.
5. **Capture**: add an invented handoff observation and demonstrate that an earlier approval becomes stale.
6. **Meta adapter**: once credits are available, call Muse Spark and inspect cited evidence IDs.

## What this is NOT

There is no real employee login, reviewer authentication, organization connection, source-policy inference, production data integration, actual human impact evaluation, full audit security, or external operational action. The human approval gate is **simulated in local application state**. The hash chain is not digitally signed and can be rewritten by a database administrator. The model is advisory. The sample ROI is fictional and non-causal.

## Important project files

- `docs/DAY1_REVIEW.md` — assessment, decisions, scope and remaining rules gate.
- `docs/META_ACTIVATION.md` — safe server-side key setup and live verification steps.
- `docs/JUDGE_DEMO_v0.2.md` — 3-minute demonstration script.
- `docs/ARCHITECTURE.md` — v0.1 reference architecture, still applicable conceptually; see Day 1 for implementation changes.
- `docs/EVALUATION.md` — baseline evaluation matrix.
- `app/main.py` — API.
- `app/domain.py` — deterministic baseline analysis and estimates.
- `app/store.py` — persistence, event replay and evidence fingerprints.
- `app/meta_adapter.py` — optional structured Muse Spark request and provenance check.
- `web/` — responsive browser app.
- `tests/` — deterministic offline tests.

## API

`GET /api/health`, `GET /api/dashboard`, `GET /api/signals`, `POST /api/signals`, `GET /api/cases`, `GET /api/cases/{id}`, `POST /api/cases/{id}/approve`, `POST /api/cases/{id}/measure`, `POST /api/cases/{id}/rollback`, `GET /api/cases/{id}/timeline`, `GET /api/audit/verify`, `POST /api/cases/{id}/ai`.

## Model activation

After receiving your Meta Model API key, see [`docs/META_ACTIVATION.md`](docs/META_ACTIVATION.md). Set it only as a local environment variable. Do not share the token in chat or commit it.

## Rules and provenance

v0.1 was assembled **before** October 26 and v0.2 iterated **after** the event opened. Preserve those dates and check the full official participant rules for reuse, originality, public release, team, and submission requirements. If pre-event code reuse is restricted, treat v0.1 as reference and re-implement eligible work after kickoff. Do not claim v0.2 is eligible until the actual rules are checked.

Only invented operational records are included. No employer data, access logs, screenshots, tool integrations or proprietary details are part of the code.
