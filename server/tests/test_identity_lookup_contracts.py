"""Source-derived GetMe contracts; these do not execute Go."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from workpal_backend.app import create_app
from workpal_backend.auth import routes
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def identity(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'}).json()
        yield app, client, login


@pytest.mark.parametrize('failure,status,body', [
    (None, 401, {'error': 'user not found'}),
    ('query', 500, {'error': 'failed to load user'}),
    ('locked', 503, None),
])
def test_handler_read_failure(identity, monkeypatch, failure, status, body):
    app, client, _ = identity
    def read(session, user_id):
        if failure:
            raise OperationalError('SELECT', {}, Exception('database is locked' if failure == 'locked' else 'broken query'))
        # Simulates deletion after the real dependency validated the persisted user.
        return None
    monkeypatch.setattr(routes, 'get_user', read)
    response = client.get('/api/me')
    assert response.status_code == status
    assert response.headers['content-type'] == 'application/json'
    if body is not None:
        assert response.json() == body
    else:
        assert 'error' in response.json()


def test_persisted_identity_contract(identity, settings):
    app, client, login = identity
    assert len([r for r in routes.router.routes if r.path == '/api/me' and 'GET' in r.methods]) == 1
    fixture = json.loads((Path(__file__).parents[1] / 'contracts/batches/identity-lookup.json').read_text())['fixtures'][0]['body']
    default = client.get('/api/me').json()
    assert set(default) == set(fixture)
    for key, value in fixture.items():
        if key not in ('id', 'created_at', 'updated_at'):
            assert default[key] == value
    with app.state.database.transaction() as session:
        session.execute(text("UPDATE users SET timezone='Asia/Shanghai', profile_description='Persisted profile', onboarding_questionnaire=:q WHERE id=:id"), {'q': '{"role":"engineer"}', 'id': default['id']})
    def snapshot():
        with app.state.database.transaction() as session:
            names = session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).scalars().all()
            return {name: session.execute(text('SELECT * FROM "' + name + '"')).all() for name in names}
    before = snapshot()
    result = client.get('/api/me?id=unknown&email=other@example.com', headers={'X-User-ID': 'unknown', 'X-Actor-Source': 'agent'} )
    assert result.status_code == 200
    assert result.json() == default | {'timezone': 'Asia/Shanghai', 'profile_description': 'Persisted profile', 'onboarding_questionnaire': {'role': 'engineer'}}
    assert snapshot() == before
    for token in ('bad', 'mul_fake', 'mat_fake', 'mcn_fake', login['token'] + 'tampered'):
        response = client.get('/api/me', headers={'Authorization': 'Bearer ' + token})
        assert response.status_code == 401
        assert response.json() == {'error': 'invalid token'}
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get('/api/me', headers={'Authorization': 'Bearer ' + login['token']}).json() == result.json()
