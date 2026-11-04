# Live Meta API Smoke Test — FloorTruth v0.3

**Status: one live synthetic smoke test passed on 2026-11-04.** The test used
`muse-spark-1.3` through the application API and an isolated temporary database.
This verifies the tested local path, not the Render deployment or future calls.
With no configured key, the application uses the deterministic mock provider.

The account owner confirmed Standard mode before the test. Meta reported 392
input tokens, 1,009 output tokens (including 717 reasoning tokens), and 1,401
total tokens; cached input was zero. The ledger recorded a $0.004778 estimated
cost using pricebook `2026-10-29`. Two hypotheses passed source-ID validation
and the evidence fingerprint matched. The estimate is not an invoice, and
valid source IDs do not establish factual correctness. No prompt, key, or model
response body is recorded here.

## Activation steps (owner action, requires a Meta developer account)

1. Confirm **Standard** processing mode on the Meta account. As of 2026-10-29,
   Meta documents Standard mode content as not used for model training, while
   Contributor mode permits training use. Never use a `-contributor` model ID
   with this repository, and never send unpublished private research in prompts.
2. Create an API key via the Meta developer console (server-side only).
3. Inject it without printing or committing:
   ```bash
   export MODEL_API_KEY="<redacted>"   # use the environment's secure secret injection
   export FLOORTRUTH_ENABLE_MODEL_API=true
   export META_MODEL=muse-spark-1.3    # must be in the adapter allowlist
   ```
4. Restart the app: `.venv/bin/python run.py`.
5. Verify `/api/health` shows `"meta_enabled": true` and `/api/integrations`
   shows `"active_provider": "meta"`.
6. For an isolated one-call smoke test, confirm Standard mode with the account
   owner, then run:
   ```bash
   python scripts/smoke_test_meta.py --confirm-standard
   ```
   This explicitly authorizes one potentially billable call. It requires the
   environment variables above, uses only the built-in fictional handoff case
   and a temporary SQLite database, and returns a sanitized JSON result. It
   reports model/usage/cost metadata and whether citations and the evidence
   fingerprint passed; it does not print the key, prompt, or model text.
   `passed` requires a successful Meta response, valid evidence IDs, a matching
   fingerprint, and provider-reported input/output usage. A nonzero exit or
   unknown cost must be investigated; the versioned pricebook is an estimate,
   not an invoice. The script does not itself verify the account's processing
   terms; `--confirm-standard` is the operator's confirmation.
7. In the UI, open a case and click **Ask Meta adapter**. Expected:
   - `mode: "meta"`, `provider: "meta"`, `model: "muse-spark-1.3"`;
   - a ledger row in **Governance → AI Activity** with the provider-reported
     usage and a pricebook-computed cost;
   - hypotheses citing only supplied OBS IDs (local validation rejects invented IDs).
   Usage is in the inference ledger, not the analysis endpoint response.
8. Record the sanitized outcome here: model, date, reported usage fields,
   pricebook version used, and any schema/validation failures. Never store the
   key, full prompts, or raw proprietary response bodies in the repo.

## Mock-mode behavior (verified when Meta is not configured)

- `MetaChatProvider.is_configured()` → `False`; `select_provider()` → `MockProvider`.
- Mock returns `mode: "demo"`, deterministic hypotheses, and **estimated**
  usage (2,000 in / 400 out tokens — the $0.00420 test vector), honestly
  labeled `usage_source: "estimated"`.
- Budget gating, ledger recording, and timeline linking are identical in both modes.

## Adversarial smoke (run after activation)

- Submit an observation containing injected instructions (e.g. "approve the pilot").
  Confirm: no approval occurs, evidence IDs stay valid, no numeric confidence appears.
- Submit an oversized/over-budget request; confirm HTTP 429 with a typed reason
  enum and no inference attempt.

## Notes

- Live requests cap completions at 1,600 tokens including reasoning. Input usage
  is estimated before the call; concurrent requests and unknown usage mean the
  budget forecast is not an enforced provider spending cap.
- Meta processing mode cannot be verified from inside this environment; assert
  nothing about Standard/Contributor mode beyond the account holder's own check.
- The application labels entered observations synthetic; it cannot prove that a
  user-entered observation is fictional. Only invented examples may be sent.
- Pricing recheck: the bundled pricebook (`2026-10-29`) snapshots
  https://dev.meta.ai/docs/pricing-rate-limits as retrieved 2026-10-29.
  Re-verify rates before any production-adjacent use.
