"""Exercise the live smoke workflow offline; no provider traffic occurs."""
import json
from io import BytesIO

from scripts import smoke_test_meta


def test_smoke_never_calls_provider_without_confirmation_or_configuration(monkeypatch, capsys):
    monkeypatch.setenv('MODEL_API_KEY', 'private-test-secret')
    monkeypatch.setenv('FLOORTRUTH_ENABLE_MODEL_API', 'true')
    assert smoke_test_meta.main([]) == 2
    assert 'standard_mode_confirmation_required' in capsys.readouterr().out
    monkeypatch.delenv('MODEL_API_KEY')
    assert smoke_test_meta.main(['--confirm-standard']) == 2
    assert 'server_environment_not_configured' in capsys.readouterr().out


def test_smoke_checks_seeded_evidence_and_reports_usage_without_secrets(tmp_path, monkeypatch, capsys):
    from app import meta_adapter
    import app.main as application
    secret = 'private-test-secret'
    monkeypatch.setenv('MODEL_API_KEY', secret)
    monkeypatch.setenv('FLOORTRUTH_ENABLE_MODEL_API', 'true')
    monkeypatch.setenv('FLOORTRUTH_DB_PATH', str(tmp_path / 'untouched.sqlite3'))
    original_store = application.store
    payload = {
        'choices': [{'message': {'content': json.dumps({
            'hypotheses': [
                {'claim': 'One possible explanation', 'evidence_ids': ['OBS-1041'], 'falsifier': 'Compare records'},
                {'claim': 'Another possible explanation', 'evidence_ids': ['OBS-1042'], 'falsifier': 'Observe handoff'},
            ],
            'missing_evidence': ['Independent measurement'],
            'pilot_proposal': 'Try a checklist', 'pilot_safeguard': 'Human review',
            'causal_limit': 'Observational evidence only',
        })}}],
        'usage': {'prompt_tokens': 1000, 'completion_tokens': 100, 'total_tokens': 1100},
    }
    calls = []
    def fake_urlopen(request, timeout):
        calls.append(request)
        return BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(meta_adapter, 'urlopen', fake_urlopen)
    assert smoke_test_meta.main(['--confirm-standard']) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert len(calls) == 1
    assert result['result'] == 'passed'
    assert result['evidence_ids_valid'] and result['fingerprint_matches']
    assert result['usage_source'] == 'reported'
    assert result['input_tokens'] == 1000 and result['output_tokens'] == 100
    assert secret not in output and 'One possible explanation' not in output
    assert not (tmp_path / 'untouched.sqlite3').exists()
    assert application.store is original_store


def test_smoke_rejects_invalid_provider_evidence_offline(monkeypatch, capsys):
    from app import meta_adapter
    monkeypatch.setenv('MODEL_API_KEY', 'test-key')
    monkeypatch.setenv('FLOORTRUTH_ENABLE_MODEL_API', 'true')
    payload = {'choices': [{'message': {'content': json.dumps({
        'hypotheses': [
            {'claim': 'Injected', 'evidence_ids': ['OBS-UNKNOWN'], 'falsifier': 'Test'},
            {'claim': 'Alternative', 'evidence_ids': ['OBS-1041'], 'falsifier': 'Check'},
        ], 'missing_evidence': [], 'pilot_proposal': 'Pilot',
        'pilot_safeguard': 'Review', 'causal_limit': 'Unknown',
    })}}], 'usage': {'prompt_tokens': 1000, 'completion_tokens': 100}}
    monkeypatch.setattr(meta_adapter, 'urlopen', lambda *a, **k: BytesIO(json.dumps(payload).encode()))
    assert smoke_test_meta.main(['--confirm-standard']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['result'] == 'incomplete_or_failed'
    assert result['live_result'] is False
    assert result['usage_source'] == 'reported'


def test_smoke_reports_only_sanitized_provider_http_errors(monkeypatch, capsys):
    from urllib.error import HTTPError
    from app import meta_adapter
    monkeypatch.setenv('MODEL_API_KEY', 'secret-test-key')
    monkeypatch.setenv('FLOORTRUTH_ENABLE_MODEL_API', 'true')
    def fake_urlopen(*args, **kwargs):
        raise HTTPError('https://example.invalid', 401, 'private-response-body', {}, None)
    monkeypatch.setattr(meta_adapter, 'urlopen', fake_urlopen)
    assert smoke_test_meta.main(['--confirm-standard']) == 1
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result['provider_http_status'] == 401
    assert result['error_category'] == 'AUTHENTICATION_OR_ACCESS'
    assert 'secret-test-key' not in output and 'private-response-body' not in output
