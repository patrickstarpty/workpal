from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_invitation_http_boundary(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/invitations').status_code == 401
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        headers = {'Authorization': 'Bearer ' + login['token']}
        assert client.get('/api/invitations', headers=headers).json() == []
        assert client.get('/api/invitations/bad', headers=headers).json() == {'error':'invalid invitation id'}


def test_persisted_permissions_revoke_and_rollback(settings, monkeypatch):
    import pytest
    from uuid import uuid4
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta
    from workpal_backend.auth.models import users
    from workpal_backend.auth.tokens import issue_session
    from workpal_backend.workspaces.models import members
    from workpal_backend.workspaces import service, invitations
    from workpal_backend.infrastructure.database import DatabaseBusy
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        owner_headers = {'Authorization':'Bearer '+login['token']}
        with app.state.database.transaction() as session:
            owner = session.scalar(select(users.c.id))
            workspace = service.create_workspace(session, owner, 'Invitations', 'invite-test')
            ids = {}
            for role in ('member', 'admin', 'recipient', 'foreign'):
                uid = ids[role] = str(uuid4())
                session.execute(users.insert().values(id=uid,email=role+'@example.com',name=role,created_at=invitations.stamp(),updated_at=invitations.stamp()))
                if role in ('member','admin'):
                    session.execute(members.insert().values(id=str(uuid4()),workspace_id=workspace['id'],user_id=uid,role=role,created_at=invitations.stamp()))
            invitation = invitations.create_invitation(session, {'user_id':owner,'identity_kind':'session'}, workspace['id'], 'recipient@example.com')
            expired = invitations.create_invitation(session, {'user_id':owner,'identity_kind':'session'}, workspace['id'], 'unknown@example.com', now=datetime.now(timezone.utc)-timedelta(days=8))
        def headers(role):
            return {'Authorization':'Bearer '+issue_session(ids[role],role+'@example.com',role,settings.auth_secret,3600)}
        path = '/api/workspaces/'+workspace['id']+'/invitations'
        detail = '/api/invitations/'+invitation['id']
        revoke = path+'/'+invitation['id']
        assert client.get(path,headers=headers('foreign')).status_code == 404
        rows = client.get(path,headers=headers('member')).json()
        assert [r['id'] for r in rows] == [invitation['id']]
        assert rows[0]['inviter_email'] == 'dev@workpal.local'
        assert 'workspace_name' not in rows[0]
        assert client.get('/api/invitations',headers=headers('recipient')).json()[0]['workspace_name'] == 'Invitations'
        assert client.get(detail,headers=headers('foreign')).status_code == 403
        assert client.get(detail,headers=headers('recipient')).status_code == 200
        with app.state.database.transaction() as session:
            foreign_workspace = service.create_workspace(session, owner, 'Other', 'other-invite-test')
        assert client.delete('/api/workspaces/'+foreign_workspace['id']+'/invitations/'+invitation['id'], headers=owner_headers).status_code == 404
        expired_path = path+'/'+expired['id']
        assert client.delete(expired_path, headers={'X-CSRF-Token':client.cookies['workpal_csrf_session']}).status_code == 204
        assert client.delete(revoke).status_code == 403
        assert client.delete(revoke,headers=headers('member')).status_code == 403
        original = invitations.append_event
        def fail(*args, **kwargs):
            raise RuntimeError('outbox failure')
        monkeypatch.setattr(invitations,'append_event',fail)
        with pytest.raises(RuntimeError):
            client.delete(revoke,headers=owner_headers)
        with app.state.database.transaction() as session:
            assert session.scalar(select(invitations.invitations.c.id).where(invitations.invitations.c.id==invitation['id'])) == invitation['id']
        monkeypatch.setattr(invitations,'append_event',original)
        response = client.delete(revoke,headers=headers('admin'))
        assert response.status_code == 204 and response.content == b''
        assert client.delete(revoke,headers=owner_headers).status_code == 404
        with app.state.database.transaction() as session:
            from sqlalchemy import text
            assert session.scalar(text("SELECT count(*) FROM outbox WHERE json_extract(envelope, '$.type')='invitation:revoked'")) == 2
        def busy(*args, **kwargs):
            raise DatabaseBusy('unavailable')
        monkeypatch.setattr(invitations,'list_my_invitations',busy)
        assert client.get('/api/invitations',headers=owner_headers).status_code == 503

        from workpal_backend.auth.sessions import revoke_session
        with app.state.database.transaction() as session:
            revoke_session(session, settings, login['token'])
        assert client.get('/api/invitations', headers=owner_headers).status_code == 401
