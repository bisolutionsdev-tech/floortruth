"""Idempotent SQLite migrations for FloorTruth.

Rules:
- Migrations are versioned functions applied once, recorded in `schema_migrations`.
- Never hand-edit tables after deployment; add a new migration instead.
- All migrations are re-runnable: DDL uses IF NOT EXISTS / INSERT OR IGNORE semantics
  where re-application is possible.
"""
from __future__ import annotations
import sqlite3
from app.domain import utc_now

SCHEMA_VERSION = 2


def _001_events(db: sqlite3.Connection) -> None:
    """v0.2 event store (hash-chained audit events)."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_type TEXT NOT NULL, case_id TEXT, "
        "timestamp TEXT NOT NULL, payload TEXT NOT NULL, "
        "prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_event_case ON events(case_id)")


def _002_finops(db: sqlite3.Connection) -> None:
    """v0.3 token/economic ledger tables. Money is integer USD micros; NULL = unknown."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS workflow_runs ("
        "id TEXT PRIMARY KEY, case_id TEXT, experiment_id TEXT, "
        "workflow_name TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, "
        "status TEXT NOT NULL, evidence_fingerprint TEXT, metadata_json TEXT, "
        "synthetic INTEGER NOT NULL DEFAULT 1)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS inference_events ("
        "id TEXT PRIMARY KEY, request_id TEXT NOT NULL, attempt_no INTEGER NOT NULL DEFAULT 1, "
        "workflow_run_id TEXT, case_id TEXT, operation TEXT NOT NULL, "
        "provider TEXT NOT NULL, model TEXT, protocol TEXT, "
        "usage_source TEXT NOT NULL DEFAULT 'not_reported', "
        "request_started_at TEXT, completed_at TEXT, duration_ms INTEGER, "
        "status TEXT NOT NULL, error_class TEXT, "
        "input_tokens INTEGER, output_tokens INTEGER, cached_input_tokens INTEGER, "
        "reasoning_tokens INTEGER, provider_total_tokens INTEGER, raw_usage_json TEXT, "
        "provider_request_id TEXT, pricebook_version TEXT, "
        "estimated_cost_usd_micros INTEGER, budget_decision_id TEXT, "
        "content_logged INTEGER NOT NULL DEFAULT 0, synthetic INTEGER NOT NULL DEFAULT 1, "
        "UNIQUE(request_id, attempt_no))"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_inference_case ON inference_events(case_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_inference_run ON inference_events(workflow_run_id)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS pricebook_entries ("
        "version TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, "
        "mode TEXT NOT NULL, meter TEXT NOT NULL, unit TEXT NOT NULL, "
        "rate_per_unit_micros INTEGER, effective_from TEXT NOT NULL, effective_to TEXT, "
        "citation_url TEXT, last_verified_at TEXT, notes TEXT, "
        "PRIMARY KEY (version, provider, model, meter))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS budget_policies ("
        "id TEXT PRIMARY KEY, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL, "
        "daily_limit_usd_micros INTEGER, run_limit_usd_micros INTEGER, "
        "token_soft_limit INTEGER, request_limit INTEGER, "
        "per_call_estimate_cap_usd_micros INTEGER, action_on_limit TEXT NOT NULL DEFAULT 'HOLD', "
        "enabled INTEGER NOT NULL DEFAULT 1, synthetic INTEGER NOT NULL DEFAULT 1)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS budget_decisions ("
        "id TEXT PRIMARY KEY, workflow_run_id TEXT, scope TEXT NOT NULL, "
        "quoted_max_usd_micros INTEGER, current_spend_usd_micros INTEGER, "
        "decision TEXT NOT NULL, rule_version TEXT NOT NULL, reason TEXT NOT NULL, "
        "timestamp TEXT NOT NULL)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_budget_run ON budget_decisions(workflow_run_id)")
    db.execute(
        "CREATE TABLE IF NOT EXISTS outcome_assessments ("
        "id TEXT PRIMARY KEY, case_id TEXT NOT NULL, experiment_id TEXT, "
        "baseline_json TEXT NOT NULL, observed_json TEXT NOT NULL, comparator_json TEXT, "
        "opportunity_type TEXT, unit_economics_json TEXT, "
        "operational_benefit_usd_micros INTEGER, intervention_cost_usd_micros INTEGER, "
        "inference_cost_usd_micros INTEGER, other_known_cost_usd_micros INTEGER, "
        "modeled_net_usd_micros INTEGER, roi_percent REAL, "
        "attribution_status TEXT NOT NULL, evidence_quality TEXT NOT NULL, "
        "assumptions_json TEXT NOT NULL, caveats_json TEXT NOT NULL, "
        "realization_type TEXT NOT NULL, data_version TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_outcome_case ON outcome_assessments(case_id)")


MIGRATIONS = {1: _001_events, 2: _002_finops}


def run_migrations(db: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns the schema version reached."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in db.execute("SELECT version FROM schema_migrations")}
    for version in sorted(MIGRATIONS):
        if version not in applied:
            MIGRATIONS[version](db)
            db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, utc_now()),
            )
    db.commit()
    return max(applied | set(MIGRATIONS))
