# Submission readiness — 2 November 2026

FloorTruth is a synthetic demonstration, not a production organizational system. Reviewer labels are simulated and its hash chain is not a signed audit log.

## Verified locally

- Run the test suite with `python -m pytest -q` and the app with `python run.py`.
- Case analysis has a deterministic mock fallback. Its token figures are estimates, not measured Meta usage.
- Each case offers a downloadable JSON learning report with evidence, history, cost information and limitations. Model outputs are not stored in the report.
- Failed model calls are distinguished from successful calls in the ledger. Provider usage captured before output-validation failure remains available for cost accounting.

## Before sharing with judges

1. Confirm the accepted hackathon terms, track and required deliverables in the participant portal. The public event page does not settle all submission requirements.
2. Confirm Meta Standard processing mode and configure the key securely before testing live inference. Follow `LIVE_API_SMOKE_TEST.md`; do not claim a live test until it succeeds.
3. Review the hosted service's access controls and use the demo access gate when configured. A shared password does not authenticate individual reviewers or make the demo production-ready.
4. Verify Render's start command, persistent storage, instance count and live deployment. Local `run.py` binds to loopback; the in-memory replay model assumes a single process. SQLite on ephemeral storage may be lost on restart or redeploy.
5. Rehearse the entire demo with fresh synthetic data and verify current Meta prices. The budget quote is an estimate, not a hard provider spending limit; concurrent requests can exceed the demo budget.
6. Review the repository and submission package before disclosure. `MUSE_BUILD_HANDOFF_2026-10-29.md` is marked private and should not be included in a public submission without owner review.

No live Meta test, deployment update or submission is implied by this document.
