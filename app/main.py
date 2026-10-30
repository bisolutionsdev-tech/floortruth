"""FloorTruth v0.3 synthetic, locally runnable demonstration API.

v0.2 routes are preserved unchanged. v0.3 adds the FinOps token/economic ledger,
pre-call budget governance, evidence-linked inference events, case value
assessment with inference costs, a typed connector registry, and governance APIs.
All demo data is synthetic; no live Meta calls occur without a configured key.
"""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.domain import measure, redact
from app.store import DemoStore
from app.meta_adapter import enabled
from app.finops.ledger import FinOpsStore
from app.finops import policy as budget_policy
from app.finops import value as value_mod
from app.finops.models import InferenceEventRecord
from app.finops.pricing import micros_to_usd_str, PRICEBOOK_VERSION
from app.integrations import meta_chat
from app.integrations import registry as connector_registry

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title="FloorTruth Synthetic Demo API",version="0.2.0")
store=DemoStore()
finops=FinOpsStore()
app.mount("/static",StaticFiles(directory=ROOT/"web"),name="static")

class ObservationIn(BaseModel):
    text: str = Field(min_length=15,max_length=1000)
    shift: str = Field(pattern="^(Day|Swing|Night)$")
    channel: str = Field(pattern="^(Text|Voice)$")
    location: str = Field(min_length=2,max_length=40)

class DecisionIn(BaseModel):
    evidence_fingerprint: str = Field(min_length=64,max_length=64)
    reviewer_role: str = Field(default="Demo Reviewer",max_length=80)
    note: str = Field(default="Pilot approved for synthetic demonstration",max_length=500)

class RollbackIn(BaseModel):
    reason: str = Field(min_length=5,max_length=500)

class MeasurementIn(BaseModel):
    baseline_minutes: float = Field(default=34,ge=0,le=10000)
    observed_minutes: float = Field(default=22,ge=0,le=100000)
    periods: int = Field(default=40,ge=1,le=100000)
    cost_per_hour: float = Field(default=35,ge=0,le=100000)
    pilot_cost: float = Field(default=120,ge=0,le=1000000)

class EstimateIn(BaseModel):
    model: str = Field(default="muse-spark-1.3",max_length=80)
    input_tokens: int | None = Field(default=None,ge=0)
    cached_input_tokens: int | None = Field(default=None,ge=0)
    output_tokens: int | None = Field(default=None,ge=0)

@app.get("/")
def index(): return FileResponse(ROOT/"web"/"index.html")

@app.get("/api/health")
def health():
    status=meta_chat.provider_status()
    return {"ok":True,"version":"0.2.0","mode":"synthetic","meta_enabled":enabled(),
            "persistence":"sqlite-demo","pricebook_version":PRICEBOOK_VERSION,
            "inference_provider":status["active_provider"],
            "live_api":status["live_api"]}

@app.get("/api/dashboard")
def dashboard():
    cases=store.cases()
    summary=finops.summary()
    return {"project":"FloorTruth","synthetic":True,"signals":len(store.signals),"cases":len(cases),
            "multi_shift_cases":sum(1 for c in cases if len(c['shifts'])>=2),
            "under_review":sum(1 for c in cases if c['status'] in ('Awaiting review','Needs re-review')),
            "experiments":len(store.experiments),"audit":store.verify_chain(),"cases_summary":cases,
            "inference_economic_cost_usd_micros":summary["total_economic_cost_usd_micros"],
            "inference_events":summary["inference_events"]}

@app.get("/api/signals")
def signals(): return {"synthetic":True,"items":store.signals}

@app.post("/api/signals",status_code=201)
def add_signal(value:ObservationIn):
    return store.add(redact(value.text),value.shift,value.channel,redact(value.location))

@app.get("/api/cases")
def cases(): return {"synthetic":True,"items":store.cases()}

def get_case(case_id):
    case=next((c for c in store.cases() if c['id']==case_id),None)
    if not case: raise HTTPException(404,"Case not found")
    return case

@app.get("/api/cases/{case_id}")
def case(case_id:str): return get_case(case_id)

@app.post("/api/cases/{case_id}/approve")
def approve(case_id:str,value:DecisionIn):
    c=get_case(case_id)
    try: return store.approve(c['id'],value.reviewer_role,value.note,value.evidence_fingerprint)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc

@app.post("/api/cases/{case_id}/measure")
def add_measurement(case_id:str,value:MeasurementIn):
    c=get_case(case_id)
    result=measure(**value.model_dump())
    try: store.record_measurement(c['id'],result,value.model_dump())
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    # v0.3: outcome assessment including recorded inference costs (descriptive only).
    inference_micros,_unknown=finops.case_inference_cost_micros(c['id'])
    assessment=value_mod.assess(
        case_id=c['id'],
        baseline_minutes_per_period=value.baseline_minutes,
        observed_minutes_per_period=value.observed_minutes,
        periods=value.periods,
        loaded_hourly_rate_usd=value.cost_per_hour,
        intervention_cost_usd=value.pilot_cost,
        inference_cost_usd_micros=inference_micros,
        human_reviewed=True,  # approval gate passed above
        has_comparator=False,
        evidence_quality="MEASURED_DESCRIPTIVE",
        assumptions=["Inputs are synthetic demonstration values."],
    )
    finops.record_outcome_assessment(assessment)
    return {"case_id":c['id'],**result,"synthetic":True}

@app.post("/api/cases/{case_id}/rollback")
def rollback(case_id:str,value:RollbackIn):
    c=get_case(case_id)
    try: store.rollback(c['id'],value.reason)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    return {"case_id":c['id'],"status":"Rolled back","synthetic":True,"scope":"Demonstration only"}

@app.get("/api/cases/{case_id}/timeline")
def case_timeline(case_id:str):
    get_case(case_id)
    return {"case_id":case_id,"events":store.timeline(case_id),"integrity":store.verify_chain()}

@app.get("/api/audit/verify")
def verify_audit(): return store.verify_chain()

@app.get("/api/cases/{case_id}/value")
def case_value(case_id:str):
    """Outcome assessment: modeled value WITH recorded inference costs, caveats attached."""
    c=get_case(case_id)
    inference_micros,unknown=finops.case_inference_cost_micros(c['id'])
    assessment=finops.latest_outcome_assessment(c['id'])
    return {"case_id":c['id'],"synthetic":True,
            "status":"assessed" if assessment else "not_measured",
            "inference_cost_usd_micros":inference_micros,
            "inference_cost_usd":micros_to_usd_str(inference_micros),
            "inference_events_with_unknown_cost":unknown,
            "assessment":assessment.model_dump() if assessment else None,
            "note":"Modeled value is descriptive, not causal. Inference spend is a cost, "
                   "not proof of token-attributable value."}

@app.get("/api/cases/{case_id}/workflows")
def case_workflows(case_id:str):
    """Inference/decision/outcome lineage for one case."""
    get_case(case_id)
    runs=finops.list_workflow_runs(case_id)
    run_ids={r["id"] for r in runs}
    decisions=[d.model_dump() for d in finops.list_budget_decisions(limit=500)
               if d.workflow_run_id in run_ids]
    return {"case_id":case_id,"synthetic":True,
            "workflow_runs":runs,
            "inference_events":finops.list_inference_events(case_id=case_id,limit=200),
            "budget_decisions":decisions,
            "outcome_assessment":(lambda a: a.model_dump() if a else None)(
                finops.latest_outcome_assessment(case_id))}

@app.post("/api/cases/{case_id}/ai")
def ai_case(case_id:str):
    """Budget-gated, evidence-linked AI analysis. Deterministic governance first."""
    c=get_case(case_id)
    fingerprint=store.fingerprint(c['id'])
    evidence=[s for s in store.signals if s['id'] in c['evidence_ids']]

    # 1. Open a workflow run carrying the evidence fingerprint.
    run=finops.start_run("case_ai_analysis",case_id=c['id'],
                         evidence_fingerprint=fingerprint,
                         metadata={"operation":"hypothesis_generation","synthetic":True})

    # 2. Pre-call budget decision (deterministic; quote the expected call).
    quote=finops.estimate("muse-spark-1.3",2000,400)
    current_spend,current_calls=finops.spend_since(budget_policy.day_start_iso())
    decision=budget_policy.evaluate(
        finops.get_policy(),current_spend_usd_micros=current_spend,
        current_calls=current_calls,
        projected_cost_usd_micros=quote.cost_usd_micros,
        projected_tokens=2400,workflow_run_id=run.id,scope="global")
    finops.record_budget_decision(decision)

    if decision.decision=="HOLD":
        finops.complete_run(run.id,"held")
        raise HTTPException(status_code=429,detail={
            "error":"budget_hold",
            "reason":decision.reason,
            "quoted_max_usd":micros_to_usd_str(decision.quoted_max_usd_micros),
            "current_spend_usd":micros_to_usd_str(decision.current_spend_usd_micros),
            "budget_decision_id":decision.id,
            "workflow_run_id":run.id,
            "synthetic":True,
            "note":"Deterministic offline baseline remains available; no inference was attempted."})

    # 3. Provider call (Meta when configured, otherwise the deterministic mock).
    provider=meta_chat.select_provider()
    result=provider.analyze(c,evidence,fingerprint)
    usage=result.get("usage") or {}
    usage_source=usage.get("usage_source","not_reported")

    # 4. Deterministic cost accounting (never computed by a model).
    cost_micros=None
    priced_model="muse-spark-1.3"
    if usage.get("input_tokens") is not None or usage.get("output_tokens") is not None:
        try:
            priced=finops.price_for_usage(
                priced_model,input_tokens=usage.get("input_tokens"),
                cached_input_tokens=usage.get("cached_input_tokens"),
                output_tokens=usage.get("output_tokens"),usage_source=usage_source)
            cost_micros=priced.cost_usd_micros
        except Exception:
            cost_micros=None  # unknown price -> null, never $0.00

    event,created=finops.record_inference_event(InferenceEventRecord(
        id=result.get("request_id") or run.id,request_id=result.get("request_id") or run.id,
        attempt_no=1,workflow_run_id=run.id,case_id=c['id'],
        operation="hypothesis_generation",provider=provider.name,
        model=result.get("model"),protocol="chat_completions" if provider.name=="meta" else "mock",
        usage_source=usage_source,completed_at=result.get("completed_at"),
        duration_ms=result.get("duration_ms"),status="succeeded",
        input_tokens=usage.get("input_tokens"),output_tokens=usage.get("output_tokens"),
        cached_input_tokens=usage.get("cached_input_tokens"),
        provider_total_tokens=usage.get("provider_total_tokens"),
        raw_usage_json=None,provider_request_id=usage.get("provider_request_id"),
        pricebook_version=PRICEBOOK_VERSION if cost_micros is not None else None,
        estimated_cost_usd_micros=cost_micros,budget_decision_id=decision.id,
        content_logged=False,synthetic=True))
    finops.complete_run(run.id,"completed")

    # 5. Link into the hash-chained case timeline.
    store.audit_inference(c['id'],event.request_id,provider.name,result.get("model"),
                          fingerprint,usage_source,cost_micros,decision.id,run.id)

    response={"mode":result.get("mode"),"provider":provider.name,
              "model":result.get("model"),"synthetic":True,
              "evidence_fingerprint":fingerprint,
              "budget_decision":{"decision":decision.decision,"reason":decision.reason,
                                 "quoted_max_usd":micros_to_usd_str(decision.quoted_max_usd_micros),
                                 "id":decision.id},
              "inference_cost_usd":micros_to_usd_str(cost_micros),
              "inference_cost_usd_micros":cost_micros,
              "workflow_run_id":run.id,"duplicate_callback":not created}
    if result.get("mode")=="meta":
        response.update({"analysis":result.get("analysis"),"text":result.get("text"),
                         "evidence_ids":result.get("evidence_ids",[]),
                         "warning":result.get("warning")})
    else:
        # Mock/demo path: advisory text only; hypotheses stay UNVERIFIED suggestions.
        analysis=result.get("analysis") or {}
        response.update({"text":("Mock advisory analysis (deterministic). Competing hypotheses "
                                 "remain UNVERIFIED suggestions; human review required."),
                         "hypotheses":analysis.get("hypotheses",[]),
                         "missing_evidence":analysis.get("missing_evidence",[]),
                         "causal_limit":analysis.get("causal_limit"),
                         "warning":result.get("warning")})
    if result.get("mode")=="unavailable":
        response.update({"error_type":result.get("error_type"),"text":result.get("text")})
    return response

# ---- FinOps API ------------------------------------------------------------

@app.get("/api/finops/summary")
def finops_summary(): return finops.summary()

@app.get("/api/finops/ledger")
def finops_ledger(case_id:str|None=Query(default=None),
                  workflow_run_id:str|None=Query(default=None),
                  model:str|None=Query(default=None),
                  limit:int=Query(default=100,ge=1,le=500),
                  offset:int=Query(default=0,ge=0)):
    return {"synthetic":True,"pricebook_version":PRICEBOOK_VERSION,
            "items":finops.list_inference_events(case_id=case_id,
                                                 workflow_run_id=workflow_run_id,
                                                 model=model,limit=limit,offset=offset)}

@app.get("/api/finops/pricebook")
def finops_pricebook():
    with finops._conn() as db:
        rows=db.execute("SELECT version,provider,model,mode,meter,unit,rate_per_unit_micros,"
                        "effective_from,effective_to,citation_url,last_verified_at,notes "
                        "FROM pricebook_entries WHERE version=? ORDER BY model,meter",
                        (PRICEBOOK_VERSION,)).fetchall()
    return {"synthetic":True,"version":PRICEBOOK_VERSION,
            "source":"https://dev.meta.ai/docs/pricing-rate-limits",
            "verified_at":"2026-10-29",
            "disclaimer":"Historical/illustrative snapshot. Recheck before production use; "
                         "do not hard-code rates forever.",
            "entries":[dict(r) for r in rows]}

@app.post("/api/finops/estimate")
def finops_estimate(value:EstimateIn):
    """Deterministic cost forecast for typed usage. No LLM involved."""
    try:
        result=finops.price_for_usage(value.model,input_tokens=value.input_tokens,
                                      cached_input_tokens=value.cached_input_tokens,
                                      output_tokens=value.output_tokens,
                                      usage_source="estimated")
    except Exception as exc:
        raise HTTPException(422,f"Cannot price this usage: {exc}") from exc
    return {"synthetic":True,"model":value.model,
            "estimated_cost_usd_micros":result.cost_usd_micros,
            "estimated_cost_usd":result.cost_usd_6dp,
            "pricebook_version":result.pricebook_version,
            "breakdown_micros":result.breakdown_micros,
            "assumptions":result.assumptions}

# ---- Governance API --------------------------------------------------------

@app.get("/api/governance/policies")
def governance_policies():
    return {"synthetic":True,
            "note":"Demo declarative rules. Reviewer roles are simulated, not authenticated; "
                   "hash-linked events are tamper-evident, not signed.",
            "policies":[p.model_dump() for p in finops.list_policies()]}

@app.get("/api/governance/decisions")
def governance_decisions(limit:int=Query(default=100,ge=1,le=500)):
    return {"synthetic":True,
            "note":"Budget decisions are deterministic and recorded pre-call. Human approval "
                   "events live in each case timeline.",
            "decisions":[d.model_dump() for d in finops.list_budget_decisions(limit=limit)]}

# ---- Integrations ----------------------------------------------------------

@app.get("/api/integrations")
def integrations():
    return {"synthetic":True,
            "inference_provider":meta_chat.provider_status(),
            "connectors":connector_registry.list_connectors()}
