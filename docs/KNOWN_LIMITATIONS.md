# FloorTruth v0.3 — Known Limitations

Honest accounting of what this build is not. Nothing here is marketed as functional.

## Inference & providers
- **No live Meta test has run.** `LIVE_API_NOT_VERIFIED`; the mock provider is active.
  Meta processing mode (Standard vs Contributor) cannot be verified in this environment.
- Mock usage (2,000 in / 400 out tokens) is **estimated**, not provider-reported.
- Only Chat Completions is wrapped. Responses API, voice transcription, SAM 3.1,
  and image generation are typed hooks/stubs, not implementations.

## Economics
- Pricebook `2026-10-29` is a historical snapshot of Meta Standard rates
  (source-linked). Rates change; recheck before production use.
- Credits/promotional balances are modeled as billing relief only; the demo tracks
  no actual credit balance.
- "Modeled net value" is descriptive and capacity-equivalent — not cash, not causal.
  Attribution never exceeds `DESCRIPTIVE_ONLY` in this build.

## Governance & security
- Reviewer role is **simulated** (user-supplied label). The optional shared-password demo gate does not authenticate individual reviewers or provide role-based authorization. See `docs/DEMO_ACCESS.md`.
- Hash-chained events are **tamper-evident only** — not cryptographically signed,
  not access-controlled, not an immutable ledger.
- Budget policies are demo defaults from environment variables; no multi-tenant
  isolation, no real quota enforcement against a billing account.
- Redaction is regex-only (email/phone); not production PII detection.

## Data & scope
- **100% synthetic data.** No employer systems, no real observations, no real people.
- Topic classifier is keyword-based and deliberately simple.
- Connector registry is honest but mostly Mocked/Planned; external writes are disabled
  and return `NOT_CONFIGURED`.
- UI verified by static checks and API contract tests only in this environment
  (no live browser automation ran here); layout targets 375px and desktop.
- Simpson's-paradox detection covers mix-shift reversal on supplied strata; it is
  not a general causal-inference engine.

## Process
- Hackathon participant rules page was unreachable at build time ("rules will be
  published"); accepted Discord/participant terms govern and were not re-verified here.
- No submission, deployment, or publication has been performed — owner decision.
