# Agent Instructions — FloorTruth Hackathon

Read `docs/MUSE_BUILD_HANDOFF_2026-10-29.md` **before editing code**. This document is the source of truth for the v0.3 implementation goals. The current checked-in tree is **v0.2** and is a real executable baseline, not the promised v0.3.

- Preserve current endpoints and deterministic tests. `python -m pytest -q` was confirmed **13 passed** before handoff.
- Build sequentially: baseline audit → usage/pricebook/ledger → budgets and case value → grounded Meta calls → UI → connector mocks → evaluation/demo.
- Keep `MODEL_API_KEY` server-side only. Confirm Meta Standard mode; no Contributor mode for this repository or private research content. Never commit credentials.
- Preserve data classification: **synthetic only**. No employer data, screenshots or confidential AIPP implementation materials.
- Treat model outputs as proposals, never approvals; validate every source ID; implement budget and finances in deterministic code.
- No actual third-party integrations or external writes without explicitly configured authorization. Stubs must be visibly labeled as stubs.
- No public Git push, deployment, contest submission or disclosure without owner approval.
- Favor a working 3-minute evidence-to-value demo over optional features. Do not spend excessive tokens on redundant architecture plans.
- Return a build summary with files changed, tested functionality, known limitations, commands to run and anything requiring human action.
