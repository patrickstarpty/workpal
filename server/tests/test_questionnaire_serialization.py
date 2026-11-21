import json
from decimal import Decimal
import pytest
from test_onboarding_json_edges import authenticated


@pytest.mark.parametrize('literal', ['0.12345678901234567890123456789', '1e400'])
def test_all_user_responses_preserve_numbers(authenticated, literal):
    client, headers = authenticated
    response = client.patch('/api/me/onboarding', content='{"questionnaire":{"n":'+literal+'}}', headers=headers)
    responses = [response, client.get('/api/me', headers=headers),
                 client.patch('/api/me', content='{}', headers=headers)]
    login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
    assert len(login.headers.get_list('set-cookie')) == 3
    for response in responses:
        assert response.status_code == 200
        assert json.loads(response.text, parse_float=Decimal)['onboarding_questionnaire']['n'] == Decimal(literal)
    assert json.loads(login.text, parse_float=Decimal)['user']['onboarding_questionnaire']['n'] == Decimal(literal)
    with client.app.state.database.transaction() as session:
        from sqlalchemy import text
        raw = session.execute(text('SELECT onboarding_questionnaire FROM users')).scalar_one()
    assert json.loads(raw, parse_float=Decimal)['n'] == Decimal(literal)


@pytest.mark.parametrize('value', ['"\\u0000"', '"\\ud800"', '{"\\udfff":0}', '1e131072', '1e-16384'])
def test_rejected_input_preserves_row(authenticated, value):
    client, headers = authenticated
    before = client.get('/api/me', headers=headers)
    result = client.patch('/api/me/onboarding', content='{"questionnaire":'+value+'}', headers=headers)
    assert result.status_code == 400
    after = client.get('/api/me', headers=headers)
    assert after.status_code == 200
    assert after.json() == before.json()


def test_exact_scalar_storage_and_reopen(authenticated):
    client, headers = authenticated
    literal = '0.12345678901234567890123456789'
    response = client.patch('/api/me/onboarding', content='{"questionnaire":'+literal+'}', headers=headers)
    assert response.status_code == 200
    with client.app.state.database.transaction() as session:
        from sqlalchemy import text
        raw = session.execute(text('SELECT onboarding_questionnaire FROM users')).scalar_one()
    assert json.loads(raw, parse_float=Decimal) == Decimal(literal)
    client.app.state.database.engine.dispose()
    response = client.get('/api/me', headers=headers)
    assert response.status_code == 200
    assert json.loads(response.text, parse_float=Decimal)['onboarding_questionnaire'] == Decimal(literal)
