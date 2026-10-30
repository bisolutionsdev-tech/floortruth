# Live Meta API Smoke Test — FloorTruth v0.3

**Status: `LIVE_API_NOT_VERIFIED`.** No Meta API key exists in this environment.
No live call has been attempted, and none is claimed. The application runs its
full demonstration on the deterministic mock provider.

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
6. In the UI, open a case and click **Ask Meta adapter**. Expected:
   - `mode: "meta"`, `provider: "meta"`, `model: "muse-spark-1.3"`;
   - `usage.usage_source: "reported"` with prompt/completion token counts;
   - a ledger row in **Governance → AI Activity** with the provider-reported
     usage and a pricebook-computed cost;
   - hypotheses citing only supplied OBS IDs (local validation rejects invented IDs).
7. Record the sanitized outcome here: model, date, reported usage fields,
   pricebook version used, and any schema/validation failures. Never store the
   key, full prompts, or raw proprietary response bodies in the repo.

## Mock-mode behavior (current, verified)

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

- Meta processing mode cannot be verified from inside this environment; assert
  nothing about Standard/Contributor mode beyond the account holder's own check.
- Pricing recheck: the bundled pricebook (`2026-10-29`) snapshots
  https://dev.meta.ai/docs/pricing-rate-limits as retrieved 2026-10-29.
  Re-verify rates before any production-adjacent use.
