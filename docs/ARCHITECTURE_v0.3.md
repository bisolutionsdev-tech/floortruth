# FloorTruth v0.3 — Architecture

Two linked loops, one store, deterministic governance between them.

```
UI (mobile-first, static) --> FastAPI (deterministic governance)
  API --> DemoStore (observations, cases, hash-chained events)
  API --> FinOpsStore (workflow runs, inference events, pricebook,
                       budget policies/decisions, outcome assessments)
  Case & Evidence Graph <-- InferenceProvider (Mock active / Meta when keyed)
  Simulated human review --> reversible experiment --> measured outcome
```

## Planes
1. **Experience** — capture, case board, experiments, governance & token-economics console.
2. **Evidence** — source records separate from hypotheses; fingerprints; contradictions preserved.
3. **Governance** — budget ALLOW/WARN/HOLD pre-call; fingerprint-checked approvals; 409 on stale; rollback; typed 429 holds.
4. **Learning/value** — descriptive baseline math; inference costs joined by `workflow_run_id`/`case_id`; attribution clamped to evidence.

## Key modules
| Path | Role |
|---|---|
| `app/main.py` | Routes; budget-gated `/ai`; value/workflow/governance/finops endpoints |
| `app/store.py` | v0.2 event store + `INFERENCE_RECORDED` timeline linking |
| `app/domain.py` | Deterministic classify/correlate/measure/redact |
| `app/meta_adapter.py` | Meta Chat Completions + schema + source-ID validation (inactive w/o key) |
| `app/finops/pricing.py` | Versioned pricebook (seed `2026-10-29`, Meta Standard rates, provenance URLs); integer-micros cost math |
| `app/finops/ledger.py` | `FinOpsStore`: runs, events (idempotent on request+attempt), decisions, assessments, summaries |
| `app/finops/policy.py` | Env-configurable budget evaluation; typed hold reasons |
| `app/finops/value.py` | Outcome math; attribution clamp; double-count refusal; Simpson's-paradox check |
| `app/integrations/meta_chat.py` | `InferenceProvider` protocol; `MockProvider` active; `MetaChatProvider` keyed |
| `app/integrations/contracts.py` / `registry.py` | Typed contracts; honest Available/Mocked/Planned/Disabled registry |
| `migrations/` | Idempotent schema migrations (`schema_migrations` table) |

## Invariants (enforced in code, not prose)
- Money: integer USD micros; `None` = unknown, never `$0.00`.
- Cost is a deterministic function of versioned pricebook × observed usage; models never compute money.
- `cached_input_tokens > input_tokens` raises; it is never silently capped.
- Attribution never exceeds `DESCRIPTIVE_ONLY` without comparator (+ human review for causal).
- No numeric confidence probabilities; evidence quality is qualitative.
- Model output is `SUGGESTED`; approvals, budgets, and arithmetic are server-enforced.
- External writes disabled (`NOT_CONFIGURED`); connectors carry no credentials.

## Data flow: one AI call
`POST /api/cases/{id}/ai` → start `WorkflowRun` (fingerprint) → `BudgetDecision` (quote vs policy)
→ HOLD ⇒ 429, run marked held → provider.analyze → `InferenceEvent` (usage, micros cost,
pricebook version) → `INFERENCE_RECORDED` timeline event → run completed.
Duplicate `(request_id, attempt_no)` callbacks are absorbed, not double-counted.
