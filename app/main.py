"""FloorTruth v0.2 synthetic, locally runnable demonstration API."""
from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.domain import measure, redact
from app.store import DemoStore
from app.meta_adapter import enabled, suggest

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title="FloorTruth Synthetic Demo API",version="0.2.0")
store=DemoStore()
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
    observed_minutes: float = Field(default=22,ge=0,le=10000)
    periods: int = Field(default=40,ge=1,le=100000)
    cost_per_hour: float = Field(default=35,ge=0,le=100000)
    pilot_cost: float = Field(default=120,ge=0,le=1000000)

@app.get("/")
def index(): return FileResponse(ROOT/"web"/"index.html")

@app.get("/api/health")
def health(): return {"ok":True,"version":"0.2.0","mode":"synthetic","meta_enabled":enabled(),"persistence":"sqlite-demo"}

@app.get("/api/dashboard")
def dashboard():
    cases=store.cases()
    return {"project":"FloorTruth","synthetic":True,"signals":len(store.signals),"cases":len(cases),
            "multi_shift_cases":sum(1 for c in cases if len(c['shifts'])>=2),
            "under_review":sum(1 for c in cases if c['status'] in ('Awaiting review','Needs re-review')),
            "experiments":len(store.experiments),"audit":store.verify_chain(),"cases_summary":cases}

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

@app.post("/api/cases/{case_id}/ai")
def ai_case(case_id:str):
    c=get_case(case_id)
    result=suggest(c,store.signals)
    if result.get("mode") not in ("demo",):
        store.audit_model(c['id'], result.get('mode'),result.get('model'),result.get('evidence_ids',[]),result.get('usage'))
    return result
