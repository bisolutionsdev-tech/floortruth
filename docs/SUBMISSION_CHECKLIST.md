# FloorTruth v0.3 — Submission Checklist

**Owner decision required for every unchecked item. Nothing here has been submitted,
deployed, or published by the build agent.**

## Code & tests
- [x] 47/47 tests pass offline (`.venv/bin/python -m pytest -q`); 13 v0.2 baseline preserved
- [x] Deterministic demo trace generated (`docs/demo_trace_v0.3.json`, 8 steps, clean DB)
- [x] No credentials, keys, or secrets in the repo (`MODEL_API_KEY` server-side only)
- [x] 100% synthetic data; no employer internals, no real people, no private research IP
- [x] Stubs visibly labeled (Available / Mocked / Planned / Disabled); nothing marketed as functional

## Demo readiness
- [x] 3-minute script (`docs/DEMO_SCRIPT_v0.3.md`) rehearsed against the trace
- [x] Governance & token-economics screen with per-case drilldown
- [x] SYNTHETIC DEMO indicator on every view; descriptive (non-causal) labeling intact
- [ ] Screenshots captured from a live browser session (not available in build env)
- [ ] Live Meta smoke test (`docs/LIVE_API_SMOKE_TEST.md` — needs owner's key + Standard-mode check)

## Hackathon compliance (owner to verify)
- [ ] Accepted participant/Discord terms reviewed (public rules page was stale at build time)
- [ ] Track selection confirmed (provisional: Indie developer)
- [ ] Submission deliverables format confirmed (repo link? video? pitch deck?)
- [ ] Rights/waiver implications of submission understood (organizer license grant)
- [ ] `FloorTruth_Pitch_Deck_v0.1.pptx` reviewed — update only if a working feature changes the story

## Pre-submission hygiene
- [ ] Re-verify pricebook rates against https://dev.meta.ai/docs/pricing-rate-limits
- [ ] Fresh-DB demo rehearsal passes end to end
- [ ] `git log` reviewed; no unintended files (`.floortruth/*.sqlite3` is gitignored)
- [ ] Deadline: **Nov 4, 2026 — 9:00 PM US Eastern (7:00 PM Mountain)**; confirm no amendments

## Explicitly NOT done by the agent
Push, publish, deploy, contest submission, external service changes, key provisioning.
