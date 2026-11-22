from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_role_contract(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        token = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        headers = {'Authorization':'Bearer '+token}
        workspace = client.post('/api/workspaces', json={'name':'A','slug':'alpha'}, headers=headers).json()
        base = '/api/workspaces/'+workspace['id']+'/members'
        member = client.get(base, headers=headers).json()[0]
        url = base+'/'+member['id']
        result = client.patch(url, json={'role':' owner '}, headers=headers)
        assert result.status_code == 200
        assert result.json() == member
        assert member['avatar_url'] is None
        assert 'pinned_at' not in member
        for body, error in [({},'role is required'),({'role':None},'role is required'),({'role':1},'invalid request body'),({'role':'Owner'},'invalid member role'),({'role':'member'},'workspace must have at least one owner')]:
            response = client.patch(url, json=body, headers=headers)
            assert response.status_code == 400
            assert response.json()['error'] == error
        assert client.patch(base+'/bad', json={'role':'owner'}, headers=headers).status_code == 400


def test_caller_rollback_and_lookup_failure(settings, monkeypatch):
    import pytest
    from sqlalchemy import select
    from workpal_backend.workspaces import membership_mutations as mutation
    from workpal_backend.workspaces.models import members
    from workpal_backend.infrastructure.outbox import outbox
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        h = {'Authorization':'Bearer '+token}
        ws = client.post('/api/workspaces',json={'name':'A','slug':'alpha'},headers=h).json()
        member = client.get('/api/workspaces/'+ws['id']+'/members',headers=h).json()[0]
        principal = {'identity_kind':'session','user_id':member['user_id']}
        with pytest.raises(RuntimeError):
            with app.state.database.transaction() as session:
                mutation.update_member_role(session,principal,ws['id'],member['id'],b'{"role":"owner"}')
                raise RuntimeError('caller rollback')
        with app.state.database.transaction() as session:
            assert session.scalar(select(outbox.c.event_id)) is None
        def fail(*args):
            raise RuntimeError('lookup failed')
        monkeypatch.setattr(mutation,'load_member_response',fail)
        with pytest.raises(RuntimeError):
            with app.state.database.transaction() as session:
                mutation.update_member_role(session,principal,ws['id'],member['id'],b'{"role":"owner"}')
        with app.state.database.transaction() as session:
            assert session.scalar(select(outbox.c.event_id)) is None
            assert session.scalar(select(members.c.role)) == 'owner'
