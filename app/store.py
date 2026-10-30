"""Synthetic-only state and inspectable SQLite event history.

Hash links detect accidental/tampered records, NOT provide cryptographic signatures
or an adversarially secure audit ledger. Auth is deliberately not implemented.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path
from threading import RLock
from app.domain import classify, correlate, utc_now
from migrations import run_migrations

SEED = [
    {"id":"OBS-1041","shift":"Day","channel":"Voice","location":"Zone B","text":"At shift change our station readiness checklist was not completed; startup was delayed again.","time":"2026-10-19T06:10:00Z"},
    {"id":"OBS-1042","shift":"Swing","channel":"Text","location":"Zone B","text":"Equipment calibration was missing at handoff; we spent time preparing the station before production.","time":"2026-10-19T14:20:00Z"},
    {"id":"OBS-1043","shift":"Night","channel":"Text","location":"Zone B","text":"Repeated startup delays at station due to unclear shift handoff responsibilities.","time":"2026-10-19T22:05:00Z"},
    {"id":"OBS-1044","shift":"Day","channel":"Voice","location":"Zone B","text":"Could we have a station ready sign-off checklist at shift change?", "time":"2026-10-20T06:15:00Z"},
    {"id":"OBS-1045","shift":"Swing","channel":"Text","location":"Zone C","text":"Packaging cartons run low during late peak; supplies take too long to refill.","time":"2026-10-20T15:40:00Z"},
    {"id":"OBS-1046","shift":"Night","channel":"Text","location":"Zone C","text":"Material replenishment seems to arrive after packing material runs out.","time":"2026-10-20T23:20:00Z"},
    {"id":"OBS-1047","shift":"Day","channel":"Text","location":"Zone C","text":"A visual signal for supply stock could reduce unexpected packaging shortages.","time":"2026-10-21T08:30:00Z"},
    {"id":"OBS-1048","shift":"Day","channel":"Voice","location":"Training","text":"Learning portal sign-in failed during the scheduled training session.","time":"2026-10-21T10:20:00Z"},
    {"id":"OBS-1049","shift":"Swing","channel":"Text","location":"Training","text":"Unable to access training modules after switching assignments.","time":"2026-10-21T16:35:00Z"},
]

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

class DemoStore:
    def __init__(self, db_path: str | Path | None = None):
        default = Path(__file__).resolve().parent.parent / ".floortruth" / "demo.sqlite3"
        self.db_path = Path(db_path or os.getenv("FLOORTRUTH_DB_PATH", str(default)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.signals = [{**s, "topic":classify(s["text"]), "synthetic":True} for s in deepcopy(SEED)]
        self.decisions = {}
        self.experiments = {}
        self.approved_fingerprints = {}
        self._init_db()
        self._replay()

    def _conn(self):
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self):
        with self._conn() as db:
            run_migrations(db)

    def _events(self):
        with self._conn() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id")]

    def verify_chain(self):
        events = self._events()
        previous = "GENESIS"
        for item in events:
            body = {"event_type":item["event_type"], "case_id":item["case_id"], "timestamp":item["timestamp"], "payload":json.loads(item["payload"]), "prev_hash":previous}
            if item["prev_hash"] != previous or sha(body) != item["event_hash"]:
                return {"valid":False, "checked":item["id"], "events":len(events), "integrity":"FAILED", "security_note":"Hash chain is tamper-evident only, not signed or access-controlled."}
            previous = item["event_hash"]
        return {"valid":True, "checked":len(events), "events":len(events), "head_hash":previous, "integrity":"VERIFIED", "security_note":"Hash chain is tamper-evident only, not signed or access-controlled."}

    def _append(self, event_type, case_id, payload):
        with self.lock, self._conn() as db:
            if not self.verify_chain()["valid"]:
                raise RuntimeError("Cannot append to a failed audit chain")
            last = db.execute("SELECT event_hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
            previous = last["event_hash"] if last else "GENESIS"
            timestamp = utc_now()
            body = {"event_type":event_type,"case_id":case_id,"timestamp":timestamp,"payload":payload,"prev_hash":previous}
            h = sha(body)
            cursor = db.execute("INSERT INTO events (event_type,case_id,timestamp,payload,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",
                                (event_type,case_id,timestamp,canonical(payload),previous,h))
            return {"id":cursor.lastrowid, **body, "event_hash":h}

    def _replay(self):
        integrity = self.verify_chain()
        if not integrity["valid"]:
            raise RuntimeError("FloorTruth demo audit chain failed verification; refusing to replay state")
        for event in self._events():
            payload = json.loads(event["payload"])
            kind, cid = event["event_type"], event["case_id"]
            if kind == "SIGNAL_ADDED": self.signals.insert(0, payload["signal"])
            if kind == "PILOT_APPROVED":
                self.decisions[cid] = "Pilot approved"
                self.approved_fingerprints[cid] = payload["evidence_fingerprint"]
                self.experiments.pop(cid, None)
            if kind == "OUTCOME_RECORDED":
                self.decisions[cid] = "Measured"
                self.experiments[cid] = payload["result"]
            if kind == "PILOT_ROLLED_BACK":
                self.decisions[cid] = "Rolled back"
                self.experiments.pop(cid, None)
                self.approved_fingerprints.pop(cid, None)

    def fingerprint(self, case_id):
        base = next((c for c in correlate(self.signals) if c["id"] == case_id), None)
        if base is None: raise KeyError("Unknown case")
        chosen = [{"id":s["id"],"text":s["text"],"topic":s["topic"],"shift":s["shift"]}
                  for s in self.signals if s["id"] in base["evidence_ids"]]
        return sha(sorted(chosen, key=lambda s:s["id"]))

    def status(self, cid):
        value = self.decisions.get(cid,"Awaiting review")
        if value in ("Pilot approved", "Measured") and self.approved_fingerprints.get(cid) != self.fingerprint(cid):
            return "Needs re-review"
        return value

    def add(self, text, shift, channel, location):
        with self.lock:
            ids = [int(s["id"].split("-")[-1]) for s in self.signals]
            record = {"id":f"OBS-{max(ids, default=1040)+1}","shift":shift,"channel":channel,"location":location,
                      "text":text,"time":utc_now(),"topic":classify(text),"synthetic":True}
            self._append("SIGNAL_ADDED",None,{"signal":record})
            self.signals.insert(0,record)
            return record

    def approve(self, cid, reviewer_role, note, expected_fingerprint):
        with self.lock:
            current = self.fingerprint(cid)
            if current != expected_fingerprint:
                raise ValueError("Evidence changed; reload the case before approving")
            if self.status(cid) in ("Pilot approved", "Measured"):
                raise ValueError("Pilot already approved; rollback or complete review before another approval")
            self._append("PILOT_APPROVED",cid,{"reviewer_role":reviewer_role,"note":note,
                          "evidence_fingerprint":current,"synthetic":True,"authentication":"NOT IMPLEMENTED"})
            self.decisions[cid]="Pilot approved"
            self.approved_fingerprints[cid]=current
            self.experiments.pop(cid,None)
            return {"case_id":cid,"status":"Pilot approved","evidence_fingerprint":current,
                    "reviewer_role":reviewer_role,"note":note,"synthetic":True,"approval_scope":"Simulated demonstration only; reviewer identity is not authenticated"}

    def record_measurement(self, cid, result, inputs):
        with self.lock:
            if self.status(cid) not in ("Pilot approved", "Measured"):
                raise ValueError("Fresh human approval required before recording a result")
            self._append("OUTCOME_RECORDED",cid,{"inputs":inputs,"result":result,
                         "evidence_fingerprint":self.approved_fingerprints[cid],"synthetic":True})
            self.decisions[cid]="Measured"
            self.experiments[cid]=result

    def rollback(self, cid, reason):
        with self.lock:
            if self.status(cid) not in ("Pilot approved","Measured","Needs re-review"):
                raise ValueError("No active or measured pilot to roll back")
            self._append("PILOT_ROLLED_BACK",cid,{"reason":reason,"synthetic":True,"effect":"DEMO_STATUS_ONLY"})
            self.decisions[cid]="Rolled back"
            self.experiments.pop(cid,None)
            self.approved_fingerprints.pop(cid,None)

    def timeline(self, cid):
        return [{"event_id":e["id"],"event_type":e["event_type"],"timestamp":e["timestamp"],
                 "event_hash":e["event_hash"],"payload":json.loads(e["payload"])}
                for e in self._events() if e["case_id"]==cid]

    def audit_model(self, cid, status, model, evidence_ids, usage=None):
        self._append("MODEL_EVALUATED",cid,{"result":status,"model":model,"evidence_ids":evidence_ids,
                     "usage":usage or {},"synthetic":True,"model_output_stored":False})

    def audit_inference(self, cid, request_id, provider, model, evidence_fingerprint,
                        usage_source, cost_usd_micros, budget_decision_id, workflow_run_id):
        """Link a ledger inference event into the hash-chained case timeline."""
        self._append("INFERENCE_RECORDED",cid,{"request_id":request_id,"provider":provider,
                     "model":model,"evidence_fingerprint":evidence_fingerprint,
                     "usage_source":usage_source,"estimated_cost_usd_micros":cost_usd_micros,
                     "budget_decision_id":budget_decision_id,"workflow_run_id":workflow_run_id,
                     "synthetic":True,"model_output_stored":False})

    def cases(self):
        result=[]
        for c in correlate(self.signals):
            cid=c["id"]
            result.append({**c,"status":self.status(cid),"evidence_fingerprint":self.fingerprint(cid),
                           "experiment":self.experiments.get(cid) if self.status(cid)=="Measured" else None,"timeline":self.timeline(cid)[-6:]})
        return result
