"""Deterministic FloorTruth demo tests; never call Meta or employer systems."""
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.domain import classify, correlate, measure, redact
from app.meta_adapter import validate_grounding, RESPONSE_SCHEMA
from app.store import DemoStore

@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", DemoStore(db_path=tmp_path/"events.sqlite3"))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("FLOORTRUTH_ENABLE_MODEL_API", raising=False)

@pytest.fixture
def client(): return TestClient(main.app)

def _fingerprint(client, cid='CASE-HANDOFF'):
    return client.get(f'/api/cases/{cid}').json()['evidence_fingerprint']

def _approve(client, cid='CASE-HANDOFF'):
    return client.post(f'/api/cases/{cid}/approve',json={'evidence_fingerprint':_fingerprint(client,cid)})

def test_health_and_seed(client):
    assert client.get('/api/health').json()['version']=='0.2.0'
    dashboard=client.get('/api/dashboard').json()
    assert dashboard['synthetic'] and dashboard['signals']==9 and dashboard['multi_shift_cases']>=2
    assert dashboard['audit']['valid']

def test_correlation_preserves_provenance(client):
    handoff=client.get('/api/cases/CASE-HANDOFF').json()
    assert handoff['report_count'] >= 3
    assert len(handoff['evidence_ids'])==handoff['report_count']
    assert len(handoff['hypotheses']) >= 2
    assert len(handoff['evidence_fingerprint'])==64
    assert handoff['corroboration'] != 'Causation established'

def test_approval_gate_and_measurement(client):
    assert client.post('/api/cases/CASE-HANDOFF/measure',json={}).status_code==409
    assert _approve(client).status_code==200
    meas=client.post('/api/cases/CASE-HANDOFF/measure',json={}).json()
    assert meas['delta_minutes']==480 and meas['estimated_gross_value']==280
    assert meas['estimated_net_value']==160 and 'No causal attribution' in meas['causality']
    assert client.get('/api/cases/CASE-HANDOFF').json()['status']=='Measured'
    events=client.get('/api/cases/CASE-HANDOFF/timeline').json()
    assert [e['event_type'] for e in events['events']]==['PILOT_APPROVED','OUTCOME_RECORDED']
    assert events['integrity']['valid']

def test_evidence_change_requires_reapproval(client):
    assert _approve(client).status_code==200
    add=client.post('/api/signals',json={'text':'The shift handoff was again missing a calibration step.', 'shift':'Night','channel':'Text','location':'Zone B'})
    assert add.status_code==201
    assert client.get('/api/cases/CASE-HANDOFF').json()['status']=='Needs re-review'
    assert client.get('/api/cases/CASE-HANDOFF').json()['experiment'] is None  # never show stale result as current
    assert client.post('/api/cases/CASE-HANDOFF/measure',json={}).status_code==409
    assert _approve(client).status_code==200
    assert client.post('/api/cases/CASE-HANDOFF/measure',json={}).status_code==200

def test_stale_fingerprint_rejected(client):
    old=_fingerprint(client)
    client.post('/api/signals',json={'text':'Our handoff checklist had no signed readiness verification.', 'shift':'Swing','channel':'Text','location':'Zone B'})
    assert client.post('/api/cases/CASE-HANDOFF/approve',json={'evidence_fingerprint':old}).status_code==409

def test_rollback_blocks_measurement_and_logged(client):
    _approve(client)
    r=client.post('/api/cases/CASE-HANDOFF/rollback',json={'reason':'Synthetic safeguard test'})
    assert r.status_code==200
    assert client.post('/api/cases/CASE-HANDOFF/measure',json={}).status_code==409
    assert client.get('/api/cases/CASE-HANDOFF').json()['status']=='Rolled back'
    assert client.get('/api/audit/verify').json()['valid']

def test_replay_persists_decisions(client):
    _approve(client)
    client.post('/api/cases/CASE-HANDOFF/measure',json={})
    fresh=DemoStore(db_path=main.store.db_path)
    assert fresh.status('CASE-HANDOFF')=='Measured'
    assert fresh.experiments['CASE-HANDOFF']['estimated_net_value']==160
    assert len(fresh.timeline('CASE-HANDOFF'))==2

def test_audit_mutation_detected(client):
    _approve(client)
    assert main.store.verify_chain()['valid']
    with sqlite3.connect(main.store.db_path) as db:
        db.execute("UPDATE events SET payload=? WHERE id=1",(json.dumps({'oops':True}),))
    assert main.store.verify_chain()['valid'] is False
    with pytest.raises(RuntimeError): DemoStore(db_path=main.store.db_path)

def test_untrusted_model_evidence_ids_rejected():
    valid={"hypotheses":[{"claim":"Maybe the handoff is inconsistent","evidence_ids":["OBS-1041"],"falsifier":"Audit each shift"},
                          {"claim":"Maybe machinery has defects","evidence_ids":["OBS-1041"],"falsifier":"Compare maintenance summaries"}],
           "missing_evidence":["Independent comparator"], "pilot_proposal":"Test checklist", "pilot_safeguard":"Allow immediate stop", "causal_limit":"No causal claims"}
    assert validate_grounding(valid,{'OBS-1041'}) == valid
    valid['hypotheses'][1]['evidence_ids']=['OBS-DOES-NOT-EXIST']
    with pytest.raises(ValueError): validate_grounding(valid,{'OBS-1041'})
    assert RESPONSE_SCHEMA['json_schema']['strict'] is True

def test_input_redaction_and_classification():
    assert '[email-redacted]' in redact('contact sample@example.com')
    assert '[phone-redacted]' in redact('number 555-555-1212')
    assert classify('Missing calibration during handoff')=='handoff'

def test_missing_case(client):
    assert client.post('/api/cases/CASE-DOES-NOT-EXIST/approve',json={'evidence_fingerprint':'a'*64}).status_code==404

def test_meta_is_disabled_by_default(client):
    assert client.post('/api/cases/CASE-HANDOFF/ai').json()['mode']=='demo'


def test_duplicate_approval_rejected(client):
    assert _approve(client).status_code==200
    assert _approve(client).status_code==409
