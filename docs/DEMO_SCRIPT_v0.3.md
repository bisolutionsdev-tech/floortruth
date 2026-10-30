# FloorTruth v0.3 — 3-Minute Judge Demo Script

**Setup (before the clock starts):** `.venv/bin/python run.py` → http://127.0.0.1:8000.
Fresh DB recommended: `rm -rf .floortruth/demo.sqlite3` (demo data re-seeds on launch).
Deterministic replay: `.venv/bin/python scripts/generate_demo_trace.py` → `docs/demo_trace_v0.3.json`.

All data on screen is **synthetic** — the SYNTHETIC DEMO chip is visible on every view.

---

## 0:00–0:30 — Capture: the frontline knows
- **Overview** → "＋ Capture observation". Read aloud (invented): *"Night shift handoff missed the calibration step; startup delayed twenty minutes."*
- Submit. Server returns a real ID (OBS-1050). Note the consent line: invented data only, no real company info.

## 0:30–1:00 — Correlate: evidence, not people
- **Evidence cases** → open *Equipment readiness across shifts*. Five observations, three shifts.
- Point at the provenance ledger: every claim links to source IDs. Competing hypotheses are side by side, each with a falsification test and a missing-evidence banner.
- Say it: *"Correlation suggests investigation. It does not establish causality."*

## 1:00–1:30 — Challenge & govern: the AI proposes, the human disposes
- Click **Ask Meta adapter**. A budget gate runs first (visible in the response: `ALLOW / WITHIN_BUDGET`), then the deterministic mock returns two UNVERIFIED hypotheses citing only real OBS IDs — $0.004200 of modeled inference cost recorded in the ledger.
- Click **Approve demo pilot**. Emphasize: the model cannot approve anything; the button, the fingerprint check, and the simulated reviewer do. Approval scope is labeled *"Simulated demonstration only"*.

## 1:30–2:15 — Measure: honest numbers
- **Experiments** → Calculate and record. Baseline 34 → observed 22 min × 40 periods @ $35/h.
- Outcome: 480 modeled minutes, $280 gross, $120 intervention cost, **$160 modeled net** — labeled descriptive, not causal, not cash.
- **Governance & tokens** → Economics tab: the $0.004200 inference cost now sits inside the case's modeled net ($159.9958). AI Activity tab shows the event, tokens, usage-source flags. Policies tab shows the ALLOW decision and the budget it ran under.

## 2:15–2:45 — Learn & reverse
- Case timeline: `INFERENCE_RECORDED → PILOT_APPROVED → OUTCOME_RECORDED`, hash-linked, integrity VERIFIED.
- Click **Roll back demo pilot**. Status flips; measurement is blocked until fresh approval. Nothing irreversible happened — because nothing real was ever touched.

## 2:45–3:00 — The thesis, in one breath
*"The frontline knows. The enterprise forgets. FloorTruth closes the loop — observations become evidence, evidence becomes governed experiments, and every inference token is accounted for: $0.004200, priced from a versioned book, gated by a deterministic budget, and never mistaken for proof of value."*

---

### If a judge asks…
- **"Is the AI live?"** — Mock provider is active; Meta path activates with `MODEL_API_KEY` + `FLOORTRUTH_ENABLE_MODEL_API=true`. See `docs/LIVE_API_SMOKE_TEST.md`. No live test has run here.
- **"Is that ROI real?"** — No. Descriptive, capacity-equivalent, synthetic. Attribution stays `DESCRIPTIVE_ONLY`.
- **"Is this production-secure?"** — No. Hash chain is tamper-evident, not signed; reviewer role is simulated. Labeled as such in the UI.
- **"What did the AI cost?"** — $0.004200 for the analysis call, from pricebook `2026-10-29` (Meta Standard Spark rates, source-linked). Unknown usage would show as *unknown*, never $0.00.
