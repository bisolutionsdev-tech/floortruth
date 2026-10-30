"""Durable FinOps ledger: workflow runs, inference events, budget decisions, outcomes.

Shares the demo SQLite database with DemoStore; tables are created by the
idempotent migration module (migrations/_002_finops). Retries are billable only
when usage was incurred: (request_id, attempt_no) is unique, so duplicate
callbacks never double-post a ledger event.
"""
from __future__ import annotations
import json
import os
import sqlite3
import uuid
from pathlib import Path
from threading import RLock
from app.domain import utc_now
from app.finops.models import (
    BudgetDecisionRecord, BudgetPolicyRecord, InferenceEventRecord,
    OutcomeAssessmentRecord, WorkflowRunRecord,
)
from app.finops.pricing import PRICEBOOK_VERSION, seed_pricebook
from migrations import run_migrations


def _new_id() -> str:
    return uuid.uuid4().hex


class FinOpsStore:
    def __init__(self, db_path: str | Path | None = None):
        default = Path(__file__).resolve().parent.parent.parent / ".floortruth" / "demo.sqlite3"
        self.db_path = Path(db_path or os.getenv("FLOORTRUTH_DB_PATH", str(default)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self._conn() as db:
            run_migrations(db)
            seed_pricebook(db)
        self._ensure_default_policy()

    def _conn(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    # ---- workflow runs ----------------------------------------------------
    def start_run(self, workflow_name: str, case_id: str | None = None,
                  evidence_fingerprint: str | None = None,
                  metadata: dict | None = None) -> WorkflowRunRecord:
        record = WorkflowRunRecord(
            id=_new_id(), case_id=case_id, workflow_name=workflow_name,
            started_at=utc_now(), status="running",
            evidence_fingerprint=evidence_fingerprint,
            metadata_json=json.dumps(metadata or {}), synthetic=True)
        with self.lock, self._conn() as db:
            db.execute(
                "INSERT INTO workflow_runs (id, case_id, workflow_name, started_at, status, "
                "evidence_fingerprint, metadata_json, synthetic) VALUES (?,?,?,?,?,?,?,?)",
                (record.id, record.case_id, record.workflow_name, record.started_at,
                 record.status, record.evidence_fingerprint, record.metadata_json, 1))
        return record

    def complete_run(self, run_id: str, status: str = "completed") -> None:
        with self.lock, self._conn() as db:
            db.execute("UPDATE workflow_runs SET status=?, completed_at=? WHERE id=?",
                       (status, utc_now(), run_id))

    # ---- inference events --------------------------------------------------
    def record_inference_event(self, event: InferenceEventRecord) -> tuple[InferenceEventRecord, bool]:
        """Insert an inference event. Returns (record, created). Duplicate
        (request_id, attempt_no) callbacks return the existing row, created=False."""
        cols = ["id","request_id","attempt_no","workflow_run_id","case_id","operation",
                "provider","model","protocol","usage_source","request_started_at","completed_at",
                "duration_ms","status","error_class","input_tokens","output_tokens",
                "cached_input_tokens","reasoning_tokens","provider_total_tokens","raw_usage_json",
                "provider_request_id","pricebook_version","estimated_cost_usd_micros",
                "budget_decision_id","content_logged","synthetic"]
        values = (event.id, event.request_id, event.attempt_no, event.workflow_run_id,
                  event.case_id, event.operation, event.provider, event.model, event.protocol,
                  event.usage_source, event.request_started_at, event.completed_at,
                  event.duration_ms, event.status, event.error_class, event.input_tokens,
                  event.output_tokens, event.cached_input_tokens, event.reasoning_tokens,
                  event.provider_total_tokens, event.raw_usage_json, event.provider_request_id,
                  event.pricebook_version, event.estimated_cost_usd_micros,
                  event.budget_decision_id, int(event.content_logged), int(event.synthetic))
        assert len(cols) == len(values) == 27, "ledger column drift"
        placeholders = ",".join("?" * len(cols))
        with self.lock, self._conn() as db:
            cursor = db.execute(f"INSERT OR IGNORE INTO inference_events ({','.join(cols)}) "
                                f"VALUES ({placeholders})", values)
            if cursor.rowcount == 0:
                row = db.execute("SELECT * FROM inference_events WHERE request_id=? AND attempt_no=?",
                                 (event.request_id, event.attempt_no)).fetchone()
                return InferenceEventRecord(**{k: row[k] for k in row.keys()
                    if k in InferenceEventRecord.model_fields} | {"content_logged": bool(row["content_logged"]),
                    "synthetic": bool(row["synthetic"])}), False
        return event, True

    # ---- budget policies & decisions ---------------------------------------
    def _ensure_default_policy(self) -> None:
        from app.finops.policy import default_policy
        policy = default_policy()
        with self.lock, self._conn() as db:
            db.execute(
                "INSERT OR IGNORE INTO budget_policies (id, scope_type, scope_id, "
                "daily_limit_usd_micros, run_limit_usd_micros, token_soft_limit, request_limit, "
                "per_call_estimate_cap_usd_micros, action_on_limit, enabled, synthetic) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (policy.id, policy.scope_type, policy.scope_id, policy.daily_limit_usd_micros,
                 policy.run_limit_usd_micros, policy.token_soft_limit, policy.request_limit,
                 policy.per_call_estimate_cap_usd_micros, policy.action_on_limit,
                 int(policy.enabled), 1))

    def get_policy(self, policy_id: str = "default-global") -> BudgetPolicyRecord:
        with self._conn() as db:
            row = db.execute("SELECT * FROM budget_policies WHERE id=?", (policy_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown budget policy {policy_id}")
        data = {k: row[k] for k in row.keys() if k in BudgetPolicyRecord.model_fields}
        data["enabled"] = bool(row["enabled"]); data["synthetic"] = bool(row["synthetic"])
        return BudgetPolicyRecord(**data)

    def list_policies(self) -> list[BudgetPolicyRecord]:
        with self._conn() as db:
            rows = db.execute("SELECT * FROM budget_policies").fetchall()
        out = []
        for row in rows:
            data = {k: row[k] for k in row.keys() if k in BudgetPolicyRecord.model_fields}
            data["enabled"] = bool(row["enabled"]); data["synthetic"] = bool(row["synthetic"])
            out.append(BudgetPolicyRecord(**data))
        return out

    def record_budget_decision(self, decision: BudgetDecisionRecord) -> BudgetDecisionRecord:
        with self.lock, self._conn() as db:
            db.execute(
                "INSERT INTO budget_decisions (id, workflow_run_id, scope, quoted_max_usd_micros, "
                "current_spend_usd_micros, decision, rule_version, reason, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (decision.id, decision.workflow_run_id, decision.scope,
                 decision.quoted_max_usd_micros, decision.current_spend_usd_micros,
                 decision.decision, decision.rule_version, decision.reason, decision.timestamp))
        return decision

    def list_budget_decisions(self, limit: int = 100) -> list[BudgetDecisionRecord]:
        with self._conn() as db:
            rows = db.execute("SELECT * FROM budget_decisions ORDER BY timestamp DESC LIMIT ?",
                              (limit,)).fetchall()
        return [BudgetDecisionRecord(**{k: r[k] for k in r.keys()
                if k in BudgetDecisionRecord.model_fields}) for r in rows]

    # ---- spend accounting ---------------------------------------------------
    def estimate(self, model: str, max_input_tokens: int, max_output_tokens: int,
                 version: str = PRICEBOOK_VERSION):
        """Deterministic pre-call cost forecast (upper bound, no LLM involved)."""
        from app.finops.pricing import estimate_cost
        with self._conn() as db:
            return estimate_cost(db, model, max_input_tokens, max_output_tokens, version)

    def price_for_usage(self, model: str, **usage):
        """Deterministic cost for reported/estimated usage. Integer micros or None."""
        from app.finops.pricing import cost_for_usage
        with self._conn() as db:
            return cost_for_usage(db, model, **usage)
    def spend_since(self, since_iso: str, scope_case_id: str | None = None) -> tuple[int, int]:
        """(total_cost_micros of known costs, call_count) for inference events."""
        with self._conn() as db:
            if scope_case_id:
                rows = db.execute(
                    "SELECT estimated_cost_usd_micros FROM inference_events "
                    "WHERE request_started_at >= ? AND case_id = ? AND status='succeeded'",
                    (since_iso, scope_case_id)).fetchall()
                count = db.execute(
                    "SELECT COUNT(*) FROM inference_events "
                    "WHERE request_started_at >= ? AND case_id = ?",
                    (since_iso, scope_case_id)).fetchone()[0]
            else:
                rows = db.execute(
                    "SELECT estimated_cost_usd_micros FROM inference_events "
                    "WHERE request_started_at >= ? AND status='succeeded'", (since_iso,)).fetchall()
                count = db.execute(
                    "SELECT COUNT(*) FROM inference_events WHERE request_started_at >= ?",
                    (since_iso,)).fetchone()[0]
        return sum(r[0] for r in rows if r[0] is not None), count

    def case_inference_cost_micros(self, case_id: str) -> tuple[int | None, int]:
        """(total known inference cost micros, events with unknown cost) for a case."""
        with self._conn() as db:
            rows = db.execute(
                "SELECT estimated_cost_usd_micros FROM inference_events "
                "WHERE case_id=? AND status='succeeded'", (case_id,)).fetchall()
        known = [r[0] for r in rows if r[0] is not None]
        unknown = len(rows) - len(known)
        return (sum(known) if known else (None if unknown else 0)), unknown

    # ---- queries ------------------------------------------------------------
    def list_inference_events(self, *, case_id: str | None = None,
                              workflow_run_id: str | None = None,
                              model: str | None = None,
                              limit: int = 100, offset: int = 0) -> list[dict]:
        query = "SELECT * FROM inference_events WHERE 1=1"
        params: list = []
        if case_id: query += " AND case_id=?"; params.append(case_id)
        if workflow_run_id: query += " AND workflow_run_id=?"; params.append(workflow_run_id)
        if model: query += " AND model=?"; params.append(model)
        query += " ORDER BY request_started_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["content_logged"] = bool(d["content_logged"]); d["synthetic"] = bool(d["synthetic"])
            d["raw_usage_json"] = None  # redacted from API surface; counts retained
            out.append(d)
        return out

    def list_workflow_runs(self, case_id: str | None = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM workflow_runs"
        params: list = []
        if case_id: query += " WHERE case_id=?"; params.append(case_id)
        query += " ORDER BY started_at DESC LIMIT ?"; params.append(limit)
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(r) | {"synthetic": bool(r["synthetic"])} for r in rows]

    def summary(self) -> dict:
        with self._conn() as db:
            n_events = db.execute("SELECT COUNT(*) FROM inference_events").fetchone()[0]
            n_runs = db.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
            n_decisions = db.execute("SELECT COUNT(*) FROM budget_decisions").fetchone()[0]
            totals = db.execute(
                "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                "COALESCE(SUM(cached_input_tokens),0), COALESCE(SUM(estimated_cost_usd_micros),0), "
                "SUM(CASE WHEN estimated_cost_usd_micros IS NULL THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN usage_source='reported' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN usage_source='estimated' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN usage_source='not_reported' THEN 1 ELSE 0 END) "
                "FROM inference_events WHERE status='succeeded'").fetchone()
            by_model = db.execute(
                "SELECT model, COUNT(*), COALESCE(SUM(input_tokens),0), "
                "COALESCE(SUM(output_tokens),0), COALESCE(SUM(estimated_cost_usd_micros),0) "
                "FROM inference_events WHERE status='succeeded' GROUP BY model").fetchall()
            decisions = db.execute(
                "SELECT decision, COUNT(*) FROM budget_decisions GROUP BY decision").fetchall()
        return {
            "synthetic": True,
            "pricebook_version": PRICEBOOK_VERSION,
            "workflow_runs": n_runs,
            "inference_events": n_events,
            "budget_decisions": n_decisions,
            "total_input_tokens": totals[0],
            "total_output_tokens": totals[1],
            "total_cached_input_tokens": totals[2],
            "total_economic_cost_usd_micros": totals[3],
            "events_with_unknown_cost": totals[4] or 0,
            "usage_sources": {"reported": totals[5] or 0, "estimated": totals[6] or 0,
                              "not_reported": totals[7] or 0},
            "by_model": [{"model": r[0], "events": r[1], "input_tokens": r[2],
                          "output_tokens": r[3], "cost_usd_micros": r[4]} for r in by_model],
            "budget_decisions_by_type": {r[0]: r[1] for r in decisions},
            "note": "Economic cost is modeled from provider-reported usage and the versioned "
                    "pricebook. Cost unknown is null, never $0.00. Spend is a cost, not proof "
                    "of token-attributable value.",
        }

    # ---- outcome assessments -------------------------------------------------
    def record_outcome_assessment(self, record: OutcomeAssessmentRecord) -> OutcomeAssessmentRecord:
        with self.lock, self._conn() as db:
            db.execute(
                "INSERT INTO outcome_assessments (id, case_id, experiment_id, baseline_json, "
                "observed_json, comparator_json, opportunity_type, unit_economics_json, "
                "operational_benefit_usd_micros, intervention_cost_usd_micros, "
                "inference_cost_usd_micros, other_known_cost_usd_micros, modeled_net_usd_micros, "
                "roi_percent, attribution_status, evidence_quality, assumptions_json, "
                "caveats_json, realization_type, data_version, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (record.id, record.case_id, record.experiment_id, record.baseline_json,
                 record.observed_json, record.comparator_json, record.opportunity_type,
                 record.unit_economics_json, record.operational_benefit_usd_micros,
                 record.intervention_cost_usd_micros, record.inference_cost_usd_micros,
                 record.other_known_cost_usd_micros, record.modeled_net_usd_micros,
                 record.roi_percent, record.attribution_status, record.evidence_quality,
                 record.assumptions_json, record.caveats_json, record.realization_type,
                 record.data_version, record.created_at))
        return record

    def latest_outcome_assessment(self, case_id: str) -> OutcomeAssessmentRecord | None:
        with self._conn() as db:
            row = db.execute("SELECT * FROM outcome_assessments WHERE case_id=? "
                             "ORDER BY created_at DESC LIMIT 1", (case_id,)).fetchone()
        if row is None:
            return None
        return OutcomeAssessmentRecord(**{k: row[k] for k in row.keys()
                                          if k in OutcomeAssessmentRecord.model_fields})
