# FloorTruth — Day 1 build review (October 26, 2026)

## Executive decision

Build a **governed organizational learning loop**, not a generalized HR assistant. The demo's differentiation is inspectable signal-to-decision lineage, not merely model conversation or automatic issue classification.

**Current technical decision:** preserve the responsive v0.1 experience; upgrade the state and inference contracts before broadening functionality.

## Findings from v0.1

| Finding | Why it mattered | v0.2 disposition |
| --- | --- | --- |
| Pilot approvals lost on server restart | A session reset could erase a consequential decision | SQLite event log and deterministic replay implemented |
| Approval remained valid after evidence changes | A reviewer might authorize action against an outdated evidence set | Evidence fingerprint freezes the review snapshot; changed evidence forces re-review |
| Prototype lacked rollback | Governance was one-way | Explicit simulated rollback with event record |
| Model's freeform response couldn't be checked | Could cite fabricated source IDs and sound persuasive | Meta JSON schema + local evidence-ID validation |
| Model usage was opaque | Weak Cognitive FinOps | Token usage recorded as a model event when returned by provider |
| All data synthetic; no AuthN/AuthZ | Great for a demo, unsuitable for deployment | Remains intentionally demo-only; no deceptive production-readiness claims |

## Live technical contracts

- `GET /api/health` — version, synthetic environment, adapter state.
- `GET /api/dashboard` — counts plus integrity verification.
- `GET /api/cases/{id}` — evidence IDs, competing hypotheses, source fingerprint, decision trail.
- `POST /api/cases/{id}/approve` — requires the currently displayed `evidence_fingerprint`; stale snapshots return HTTP 409.
- `POST /api/cases/{id}/measure` — rejects measurement without fresh simulated approval.
- `POST /api/cases/{id}/rollback` — reversible local experiment state; cannot change external operations.
- `GET /api/cases/{id}/timeline` — append-only event history and chain status.
- `GET /api/audit/verify` — recomputes the recorded event chain.
- `POST /api/cases/{id}/ai` — optional model analysis; constrained to synthetic source IDs and governed by local validation.

**Event types:** `SIGNAL_ADDED`, `PILOT_APPROVED`, `OUTCOME_RECORDED`, `PILOT_ROLLED_BACK`, `MODEL_EVALUATED`.

The SQLite hash chain is **not authenticated, signed, immutable, or tamper-proof**. Someone with database write access could rewrite records and recompute hashes. This is a demo proving the *shape* of provenance and replay, not production-grade evidence integrity.

## Confirmed hackathon alignment

- Dates: Oct 26–Nov 4; submission 9 p.m. Eastern on Nov 4, per official event listing.
- Themes: *Build for Your World* and *Push the Frontier*. FloorTruth best matches *Build for Your World* with operations/organizational intelligence as its lived domain.
- Tracks: indie developer and startup. If competing individually, use indie as provisional track, pending track-selection/rules confirmation.
- Core Meta integration: Muse Spark 1.3 via Meta Model API Chat Completions and schema-constrained outputs; optional later SAM 3.1 / Muse Voice Transcribe only if they genuinely improve the vertical slice.
- **Rules gate is open:** The publicly accessible event listing still says official rules will be published, but doesn't expose the complete competition terms; read/accept the event account/Discord-provided rules and specifically check pre-event scaffold reuse, team membership, public repo conditions, platform usage and IP.

## Ethical / IP boundary

The demo data, names, locations, shift schedules, and issues are fictional. The project should not ingest actual employer materials or claims about unseen vendor internals. Generalizable enterprise patterns and original architecture are the intellectual contribution.

## Immediate next slice after credits activate

1. Set `MODEL_API_KEY` locally (never commit or paste token to chat).
2. Enable `FLOORTRUTH_ENABLE_MODEL_API=true` and make a single test call on `CASE-HANDOFF`.
3. Inspect model-provided usage; verify every `evidence_id` is in the case.
4. Add a deliberately misleading synthetic source designed to provoke an invented cause; confirm the system labels hypotheses and lacks auto-approval.
5. Save demo screenshots of a single entire trace: capture → case → Meta hypotheses → approval → measurement → rollback.
6. Spend remaining cycles on replayable evaluation and a polished 3-minute judge demo, not a broad feature catalog.

## Acceptance criteria for v0.2

- Server starts with no external credentials.
- Synthetic observation→case→approval→measurement→rollback works.
- Restart restores recorded events and state.
- Wrong source fingerprint returns 409.
- Unauthorized hypothetical action is not possible: only demo state changes are coded; note there is **no actual login/auth**.
- Model citations to any unknown observation ID are rejected.
- All evidence/impact claims remain explicitly synthetic and non-causal.
- Tests run offline and are deterministic.
