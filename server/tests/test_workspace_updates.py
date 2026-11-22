"""Contracts from workspace.go, pr_auto_complete.go and member.sql."""
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_updates(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        token = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        h = {'Authorization':'Bearer '+token}
        ws = c.post('/api/workspaces', json={'name':'A','slug':'alpha'}, headers=h).json()
        url = '/api/workspaces/'+ws['id']
        for method in (c.put, c.patch):
            r = method(url, json={'name':' B ', 'description':'', 'issue_prefix':' ab ', 'repos':[{'url':' https://example.com/a ', 'description':' x '},{'url':'https://example.com/a'}]}, headers=h)
            assert r.status_code == 200
            assert r.json()['repos'] == [{'url':'https://example.com/a','description':'x'}]
            assert r.json()['issue_prefix'] == 'AB'
            assert method(url,json={'name':None,'repos':None,'settings':None},headers=h).json()['name'] == 'B'
            for body in ({'name':' '},{'name':2},{'repos':{}},{'repos':[{}]},{'issue_prefix':'!'}):
                assert method(url,json=body,headers=h).status_code == 400
        assert c.put(url,json={'settings':{'pr_auto_complete_enabled':False}},headers=h).json()['settings'] == {'pr_auto_complete_enabled':False,'pr_merge_status':'none'}
        assert c.patch(url,json={'settings':{}},headers=h).json()['settings'] == {}
        for body in ({},{'pinned':None},{'pinned':1}):
            assert c.put(url+'/pin',json=body,headers=h).status_code == 400
        assert c.put(url+'/pin',json={'pinned':True},headers=h).json()['pinned_at']
        assert c.put(url+'/pin',json={'pinned':False},headers=h).json() == {'pinned_at':None}
        row = c.get(url+'/members',headers=h).json()[0]
        assert list(row) == ['id','workspace_id','user_id','role','created_at','name','email','avatar_url']
        assert row['avatar_url'] is None


def test_guards_rollback_reopen(settings, monkeypatch):
    import pytest
    from uuid import uuid4
    from sqlalchemy import update
    from workpal_backend.auth.models import users
    from workpal_backend.workspaces.models import members
    from workpal_backend.workspaces import service
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as c:
        token = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        h = {'Authorization':'Bearer '+token}
        ws = c.post('/api/workspaces',json={'name':'A','slug':'alpha'},headers=h).json()
        url = '/api/workspaces/'+ws['id']
        with app.state.database.transaction() as session:
            other = str(uuid4())
            session.execute(users.insert().values(id=other,email='private@example.com',name='Private',created_at='2026-01-01',updated_at='2026-01-01'))
            foreign = service.create_workspace(session,other,'Foreign','foreign')
        assert c.get('/api/workspaces/'+foreign['id']+'/members',headers=h).status_code == 404
        assert c.put('/api/workspaces/'+foreign['id'],json={},headers=h).status_code == 404
        assert c.put(url,json={},headers={'Authorization':'Bearer invalid'}).status_code == 401
        original = service.update_workspace
        def fail(*args):
            original(*args)
            raise RuntimeError('rollback')
        monkeypatch.setattr(service,'update_workspace',fail)
        with pytest.raises(RuntimeError):
            c.put(url,json={'name':'Rollback'},headers=h)
        monkeypatch.setattr(service,'update_workspace',original)
        assert c.get(url,headers=h).json() == ws
        with app.state.database.transaction() as session:
            session.execute(update(members).where(members.c.workspace_id == ws['id']).values(role='member'))
        assert c.patch(url,json={'name':'Denied'},headers=h).status_code == 403
        assert c.put(url+'/pin',json={'pinned':True},headers=h).status_code == 200
    with TestClient(create_app(settings)) as c:
        assert c.get(url,headers=h).json() == ws
        assert c.get('/api/workspaces',headers=h).json()[0]['pinned_at']


def test_pin_is_member_scoped_and_orders_before_unpinned(settings):
    from uuid import uuid4
    from sqlalchemy import update
    from workpal_backend.infrastructure.database import Database
    from workpal_backend.auth.models import users
    from workpal_backend.auth.service import get_or_create_development_user
    from workpal_backend.workspaces.models import members, workspaces
    from workpal_backend.workspaces import service
    migrate(settings)
    db = Database(settings)
    try:
        with db.transaction() as session:
            owner = get_or_create_development_user(session, 'dev@workpal.local')['id']
            peer = str(uuid4())
            session.execute(users.insert().values(id=peer,email='peer@example.com',name='Peer',created_at='2026-01-01',updated_at='2026-01-01'))
            first = service.create_workspace(session, owner, 'First', 'first-pin')
            second = service.create_workspace(session, owner, 'Second', 'second-pin')
            for i, workspace in enumerate((first,second)):
                session.execute(update(workspaces).where(workspaces.c.id==workspace['id']).values(created_at=f'2026-01-0{i+1}'))
                session.execute(members.insert().values(id=str(uuid4()),workspace_id=workspace['id'],user_id=peer,role='member',created_at='2026-01-01'))
            principal = {'user_id':owner,'identity_kind':'session'}
            service.set_pinned(session, principal, second['id'], True)
            assert [w['id'] for w in service.list_workspaces(session,owner)] == [second['id'],first['id']]
            peer_rows = service.list_workspaces(session,peer)
            assert [w['id'] for w in peer_rows] == [first['id'],second['id']]
            assert all('pinned_at' not in w for w in peer_rows)
            service.set_pinned(session, principal, second['id'], False)
            assert [w['id'] for w in service.list_workspaces(session,owner)] == [first['id'],second['id']]
    finally:
        db.close()
