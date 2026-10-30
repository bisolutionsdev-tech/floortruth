# FloorTruth v0.3 — API Contracts

All responses include `"synthetic": true` where demo data is involved. Money is
integer USD micros plus a 6-decimal display string; `null` = unknown, never `$0.00`.

## v0.2 routes (preserved)
`GET /api/health` · `GET /api/dashboard` · `GET /api/signals` · `POST /api/signals` ·
`GET /api/cases` · `GET /api/cases/{id}` · `POST /api/cases/{id}/approve` (409 stale) ·
`POST /api/cases/{id}/measure` (409 without approval) · `POST /api/cases/{id}/rollback` ·
`GET /api/cases/{id}/timeline` · `GET /api/audit/verify` · `POST /api/cases/{id}/ai`

## v0.3 additions

| Method | Route | Key response fields |
|---|---|---|
| GET | `/api/finops/summary` | `total_economic_cost_usd_micros`, token totals, `usage_sources`, `by_model`, `budget_decisions_by_type`, `pricebook_version` |
| GET | `/api/finops/ledger` | `items[]`: request/model/tokens/`estimated_cost_usd_micros`/`usage_source`/case; filters `case_id`, `workflow_run_id`, `model`, `limit`, `offset` |
| GET | `/api/finops/pricebook` | `version`, `source`, `verified_at`, `entries[]` with `citation_url`, `effective_from` |
| POST | `/api/finops/estimate` | `{model, input_tokens?, cached_input_tokens?, output_tokens?}` → `estimated_cost_usd_micros`, `estimated_cost_usd` (6dp), `breakdown_micros`, `assumptions`; 422 on unpriceable usage |
| GET | `/api/cases/{id}/value` | `inference_cost_usd_micros`, `assessment` (OutcomeAssessment: net micros, `roi_percent`, `attribution_status`, `evidence_quality`, `realization_type`, `assumptions_json`, `caveats_json`) |
| GET | `/api/cases/{id}/workflows` | `workflow_runs[]`, `inference_events[]`, `budget_decisions[]` (scoped), `outcome_assessment` |
| GET | `/api/governance/policies` | `policies[]` (limits in micros, `action_on_limit`, `enabled`) |
| GET | `/api/governance/decisions` | `decisions[]`: `decision` ALLOW/WARN/HOLD, `reason` enum, `quoted_max_usd_micros`, `current_spend_usd_micros` |
| GET | `/api/integrations` | `inference_provider` (`active_provider`, `live_api`), `connectors[]` with honest `status` |

## Changed behavior
- `POST /api/cases/{id}/ai` now: opens a `WorkflowRun` (evidence fingerprint) → records a
  `BudgetDecision` pre-call → **429** `{error: budget_hold, reason}` on HOLD (no inference
  attempted) → provider analysis → `InferenceEvent` with deterministic micros cost →
  `INFERENCE_RECORDED` timeline event. Mock path returns `mode: "demo"` (unchanged).
  Response adds `evidence_fingerprint`, `budget_decision`, `inference_cost_usd[_micros]`,
  `workflow_run_id`, `duplicate_callback`.
- `POST /api/cases/{id}/measure` additionally records an `OutcomeAssessment`
  (inference costs included); the v0.2 response shape is unchanged.
- `GET /api/dashboard` adds `inference_economic_cost_usd_micros`, `inference_events`.
- `GET /api/health` adds `pricebook_version`, `inference_provider`, `live_api`
  (version string stays `0.2.0` for contract compatibility).

## Error conventions
400 bad input · 404 unknown case · 409 stale/duplicate decision · 422 unpriceable usage or
schema issue · 429 budget hold/quota · 502 upstream (meta path). 401/403 reserved for
future real authentication. No stack traces or credentials in responses.
