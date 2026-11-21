"""Mounted, authenticated JSON roundtrips; no PostgreSQL acceptance guesses."""
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def authenticated(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        token = client.post('/auth/verify-code', json={
            'email': 'dev@workpal.local', 'code': '888888',
        }).json()['token']
        yield client, {'Authorization': 'Bearer ' + token}


@pytest.mark.parametrize('raw,expected', [
    (b'{"questionnaire":{"nested":[null,{"\\ud83d\\ude00":"\\ud83d\\ude00"}]}}',
     {'nested': [None, {'😀': '😀'}]}),
    (b'{"questionnaire":{"nested":{"same":1,"same":2}}}', {'nested': {'same': 2}}),
    (b'{"questionnaire":{"nested":[9007199254740993,1.25,1e2]}}',
     {'nested': [9007199254740993, 1.25, 100]}),
])
def test_supported_nested_json_roundtrip(authenticated, raw, expected):
    client, headers = authenticated
    response = client.patch('/api/me/onboarding', content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json()['onboarding_questionnaire'] == expected
    assert client.get('/api/me', headers=headers).json()['onboarding_questionnaire'] == expected


def test_precise_decimal_roundtrip(authenticated):
    client, headers = authenticated
    literal = '0.12345678901234567890123456789'
    response = client.patch('/api/me/onboarding',
                            content='{"questionnaire":{"number":' + literal + '}}', headers=headers)
    assert response.status_code == 200
    actual = json.loads(response.text, parse_float=Decimal)['onboarding_questionnaire']['number']
    assert actual == Decimal(literal)


@pytest.mark.parametrize('value', [b'{"nested":"\\ud800"}', b'{"\\udc00":null}',
                                   b'{"nested":1e400}', b'{"nested":"\xff"}'])
def test_record_uncertain_jsonb_inputs(authenticated, value, record_property):
    client, headers = authenticated
    before = client.get('/api/me', headers=headers)
    response = client.patch('/api/me/onboarding', content=b'{"questionnaire":' + value + b'}', headers=headers)
    after = client.get('/api/me', headers=headers)
    with client.app.state.database.transaction() as session:
        from sqlalchemy import text
        stored = session.execute(text('SELECT onboarding_questionnaire FROM users')).scalar_one()
    record_property('stored', repr(stored))
    record_property('input', repr(value))
    record_property('before', before.text)
    record_property('patch', (response.status_code, response.text))
    record_property('after', (after.status_code, after.text))
    if value in (b'{"nested":"\\ud800"}', b'{"\\udc00":null}'):
        assert response.status_code == 400
        assert after.status_code == 200
        assert after.json() == before.json()
    else:
        assert response.status_code == 200
        assert after.status_code == 200
