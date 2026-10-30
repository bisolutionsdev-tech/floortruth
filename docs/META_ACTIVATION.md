# Meta Model API — activation checklist

API reference: https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
Schema reference: https://dev.meta.ai/docs/structured-output

The integration is **prepared but has not been authenticated**, because the participant credits/key are not yet available in this workspace.

## Activate locally after receiving a key

```bash
# From the repository root; create a virtualenv and install requirements first.
export MODEL_API_KEY='YOUR_KEY'       # Never commit or paste a real token
export FLOORTRUTH_ENABLE_MODEL_API=true
export META_MODEL=muse-spark-1.3
python run.py
```

Open a case and click **Ask Meta adapter**. The server (not the browser) calls `https://api.meta.ai/v1/chat/completions` using a schema-constrained response. The adapter rejects cited IDs that are not included in the source case and records whether inference was successful, model name, and provider-reported usage in an event. Raw inference output is *not persisted*; capture an example output separately for the final submission after verifying it.

If the call fails, the UI reports `unavailable` or `invalid` and leaves the deterministic case and decision-gate usable. This is not a successful provider integration test.

## Token/compute governance

- Limit requests to a small synthetic evidence set (8 observations max).
- Record prompt/output tokens returned in the provider response.
- Add an explicit credit budget once the grant terms and available credit amount are known.
- Keep Model API usage entirely out of the browser and uploaded artifacts.
- Treat hypotheses as advisory; approval can only happen in the human demo workflow.

## Testing

```bash
python -m pytest -q
```

The suite tests schema shape and post-generation evidence validation using local fixtures, **not live Meta inference**. After credits are activated, separately perform an authenticated smoke test and document results and model version.
