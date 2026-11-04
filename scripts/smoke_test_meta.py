"""Run one explicitly authorized Meta smoke test against a temporary demo DB.

Only the built-in fictional CASE-HANDOFF evidence is used. No prompts, model
responses, or credentials are printed. This script does not configure secrets.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def run_check(client):
    """Exercise the real application path and return only non-sensitive metadata."""
    case_response = client.get('/api/cases/CASE-HANDOFF')
    if case_response.status_code != 200:
        return {'result': 'case_unavailable', 'application_http_status': case_response.status_code}, False
    case = case_response.json()
    allowed = set(case.get('evidence_ids', []))
    result = client.post('/api/cases/CASE-HANDOFF/ai')
    data = result.json()
    out = {'result': 'inference_failed', 'application_http_status': result.status_code}
    if result.status_code != 200:
        # The detail body may contain arbitrary content; never print it.
        return out, False

    mode = data.get('mode')
    provider = data.get('provider')
    analysis = data.get('analysis') or {}
    hypotheses = analysis.get('hypotheses') or []
    grounding = (isinstance(hypotheses, list) and len(hypotheses) >= 2
                 and bool(allowed) and all(
                     isinstance(h, dict) and isinstance(h.get('evidence_ids'), list)
                     and bool(h['evidence_ids'])
                     and all(isinstance(i, str) and i in allowed for i in h['evidence_ids'])
                     for h in hypotheses))
    fingerprint_ok = data.get('evidence_fingerprint') == case.get('evidence_fingerprint')
    out.update({'provider_is_meta': provider == 'meta', 'live_result': mode == 'meta',
                'evidence_ids_valid': grounding, 'fingerprint_matches': fingerprint_ok,
                'hypothesis_count': len(hypotheses) if isinstance(hypotheses, list) else 0})
    categories = {'BILLING_OR_CREDITS', 'AUTHENTICATION_OR_ACCESS', 'RATE_LIMIT',
                  'PROVIDER_UNAVAILABLE', 'REQUEST_REJECTED', 'HTTP_ERROR', 'OUTPUT_LIMIT'}
    out['error_category'] = data.get('error_category') if data.get('error_category') in categories else None
    model = data.get('model')
    from app.meta_adapter import ALLOWED_MODELS
    out['model'] = model if model in ALLOWED_MODELS else None
    upstream_status = _count(data.get('http_status'))
    if upstream_status and 400 <= upstream_status <= 599:
        out['provider_http_status'] = upstream_status

    workflows = client.get('/api/cases/CASE-HANDOFF/workflows')
    events = workflows.json().get('inference_events', []) if workflows.status_code == 200 else []
    matching = [e for e in events if e.get('workflow_run_id') == data.get('workflow_run_id')]
    event = matching[0] if len(matching) == 1 else {}
    out['ledger_recorded'] = bool(event)
    out['usage_source'] = event.get('usage_source') if event.get('usage_source') in ('reported', 'estimated', 'not_reported') else 'not_reported'
    for field in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'provider_total_tokens', 'estimated_cost_usd_micros'):
        out[field] = _count(event.get(field))
    out['pricebook_version'] = event.get('pricebook_version') if event.get('pricebook_version') == '2026-10-29' else None
    success = (result.status_code == 200 and provider == 'meta' and mode == 'meta'
               and grounding and fingerprint_ok and bool(event)
               and event.get('status') == 'succeeded' and out['usage_source'] == 'reported'
               and out['input_tokens'] is not None and out['output_tokens'] is not None)
    out['result'] = 'passed' if success else 'incomplete_or_failed'
    return out, success


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run one synthetic Meta inference through FloorTruth.')
    parser.add_argument('--confirm-standard', action='store_true',
                        help='Confirm Standard mode and authorize one potentially billable call.')
    args = parser.parse_args(argv)
    if not args.confirm_standard:
        print(json.dumps({'result': 'not_run', 'reason': 'standard_mode_confirmation_required'}))
        return 2
    if (os.getenv('FLOORTRUTH_ENABLE_MODEL_API', '').lower() != 'true'
            or not os.getenv('MODEL_API_KEY')):
        print(json.dumps({'result': 'not_run', 'reason': 'server_environment_not_configured'}))
        return 2

    # These changes are restricted to this process and restored afterward. The
    # test uses a new database rather than altering existing demo records.
    old_db = os.environ.get('FLOORTRUTH_DB_PATH')
    old_gate = os.environ.get('FLOORTRUTH_DEMO_ACCESS')
    try:
        with tempfile.TemporaryDirectory(prefix='floortruth-meta-smoke-') as directory:
            path = str(Path(directory) / 'smoke.sqlite3')
            os.environ['FLOORTRUTH_DB_PATH'] = path
            os.environ['FLOORTRUTH_DEMO_ACCESS'] = 'false'
            from fastapi.testclient import TestClient
            import app.main as application
            from app.store import DemoStore
            from app.finops.ledger import FinOpsStore
            old_store, old_finops = application.store, application.finops
            try:
                application.store = DemoStore(path)
                application.finops = FinOpsStore(path)
                with TestClient(application.app) as client:
                    summary, success = run_check(client)
            finally:
                application.store, application.finops = old_store, old_finops
                # SQLite context managers commit but do not close connections;
                # collect them before removing the temporary DB on Windows.
                gc.collect()
        print(json.dumps(summary, sort_keys=True))
        return 0 if success else 1
    except Exception:
        # Exception messages and upstream bodies may contain credentials or data.
        print(json.dumps({'result': 'error', 'reason': 'local_or_provider_error'}))
        return 1
    finally:
        for name, value in (('FLOORTRUTH_DB_PATH', old_db), ('FLOORTRUTH_DEMO_ACCESS', old_gate)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == '__main__':
    raise SystemExit(main())
