from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_workspace_http(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get('/api/workspaces').status_code == 401
        login = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        assert c.get('/api/workspaces').json() == []
        assert c.post('/api/workspaces', json={'name':'A','slug':'alpha'}).status_code == 403
        headers = {'Authorization':'Bearer '+login['token']}
        for body in ('null', '{', '{"name":null}', '{"name":123,"slug":"alpha"}'):
            r = c.post('/api/workspaces', content=body, headers=headers)
            assert r.status_code == 400 and 'error' in r.json()
        r = c.post('/api/workspaces', json={'name':' A ','slug':' ALPHA ','user_id':'forged'}, headers=headers)
        assert r.status_code == 201
        workspace = r.json()
        assert workspace['slug'] == 'alpha' and workspace['name'] == 'A'
        assert workspace['settings'] == {} and workspace['repos'] == []
        assert 'pinned_at' not in workspace
        assert c.get('/api/workspaces').json() == [workspace]
        assert c.get('/api/workspaces/'+workspace['id']).json() == workspace
        assert c.post('/api/workspaces', json={'name':'A','slug':'alpha'},headers=headers).status_code == 409
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get('/api/workspaces',headers=headers).json() == [workspace]


def test_denial_rollback_busy_and_policy(settings, monkeypatch):
    import pytest
    from uuid import uuid4
    from sqlalchemy import select, func
    from workpal_backend.workspaces import service
    from workpal_backend.workspaces.models import workspaces
    from workpal_backend.infrastructure.database import DatabaseBusy
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        login = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()
        headers = {'X-CSRF-Token':c.cookies['workpal_csrf_session']}
        with app.state.database.transaction() as session:
            # Existing authenticated user has no membership in this fixture workspace.
            from workpal_backend.auth.models import users
            other = str(uuid4())
            session.execute(users.insert().values(id=other,email='other@example.com',name='Other',created_at='2026-01-01T00:00:00Z',updated_at='2026-01-01T00:00:00Z'))
            foreign = service.create_workspace(session,other,'Foreign','foreign')
        assert c.get('/api/workspaces/'+foreign['id']).status_code == 404
        assert c.get('/api/workspaces/'+str(uuid4())).json() == {'error':'workspace not found'}
        assert c.get('/api/workspaces/not-uuid').status_code == 400
        app.state.workspace_creation_enabled = False
        assert c.post('/api/workspaces',json={'name':'A','slug':'alpha'},headers=headers).status_code == 403
        app.state.workspace_creation_enabled = True
        app.state.workspace_creation_allowlist = set()
        assert c.post('/api/workspaces',json={'name':'A','slug':'alpha'},headers=headers).status_code == 403
        app.state.workspace_creation_allowlist = None
        original = service.create_workspace
        def fail(session, *args):
            original(session,*args)
            raise RuntimeError('injected after service writes')
        monkeypatch.setattr(service,'create_workspace',fail)
        with pytest.raises(RuntimeError):
            c.post('/api/workspaces',json={'name':'A','slug':'alpha'},headers=headers)
        with app.state.database.transaction() as session:
            assert session.scalar(select(func.count()).select_from(workspaces)) == 1
        def busy(*args):
            raise DatabaseBusy('busy')
        monkeypatch.setattr(service,'list_workspaces',busy)
        response = c.get('/api/workspaces')
        assert response.status_code == 503 and response.json()['retryable'] is True


def test_go_jwt_authentication_does_not_read_legacy_session_table(settings, monkeypatch):
    from workpal_backend.auth import dependencies
    from workpal_backend.infrastructure.database import DatabaseBusy
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        def busy(*args):
            raise DatabaseBusy('locked')
        monkeypatch.setattr(dependencies, 'validate_session', busy)
        response = client.get('/api/workspaces')
        assert response.status_code == 200
        assert response.json() == []
        assert 'retry-after' not in response.headers
