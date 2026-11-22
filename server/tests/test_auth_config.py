from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_disabled_creation(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    settings.disable_workspace_creation = True
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        config = client.get('/api/config').json()
        assert config['workspace_creation_disabled'] is True
        assert config['allow_signup'] is False
        assert config['local_worktree_supported'] is False
        token = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        assert client.post('/api/workspaces', headers={'Authorization':'Bearer '+token}, json={'name':'Test','slug':'test','issue_prefix':'TEST'}).status_code == 403


def test_failed_credentials_exhaust_limit(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        for _ in range(20):
            assert client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'bad'}).status_code == 400
        result = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        assert result.status_code == 429
        assert int(result.headers['Retry-After']) > 0
