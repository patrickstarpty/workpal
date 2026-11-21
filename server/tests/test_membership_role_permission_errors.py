"""Two bounded HTTP groups: authorization and real SQL failure boundaries."""
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces.models import members


@pytest.fixture
def seeded(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        headers = {'Authorization':'Bearer ' + login['token']}
        ws = client.post('/api/workspaces', json={'name':'Roles','slug':'roles'}, headers=headers).json()
        foreign = client.post('/api/workspaces', json={'name':'Foreign','slug':'foreign'}, headers=headers).json()
        owner = client.get(f"/api/workspaces/{ws['id']}/members", headers=headers).json()[0]
        ids = {'owner':owner['id']}
        tokens = {'owner':login['token']}
        with app.state.database.transaction() as session:
            for name, role in [('admin','admin'),('admin2','admin'),('member','member'),('outsider','member'),('owner2','owner')]:
                uid, mid = str(uuid4()), str(uuid4())
                session.execute(users.insert().values(id=uid,email=name+'@example.com',name=name,created_at=ws['created_at'],updated_at=ws['created_at']))
                session.execute(members.insert().values(id=mid,user_id=uid,workspace_id=foreign['id'] if name == 'outsider' else ws['id'],role=role,created_at=ws['created_at']))
                ids[name] = mid
                tokens[name] = issue_session(uid,name+'@example.com',name,settings.auth_secret,3600)
        yield app, client, ws, ids, tokens, login


def snapshot(app):
    with app.state.database.transaction() as session:
        return (list(session.execute(select(members).order_by(members.c.id))), list(session.execute(select(outbox).order_by(outbox.c.event_id))))


def patch(client, ws, mid, token, role):
    return client.patch(f"/api/workspaces/{ws['id']}/members/{mid}",json={'role':role},headers={'Authorization':'Bearer '+token})


@pytest.mark.parametrize('actor,target,role,status', [
    ('owner','member','admin',200), ('owner','member','owner',200),
    ('admin','admin2','member',200), ('admin','admin','member',200),
    ('admin','owner','member',403), ('admin','member','owner',403),
    ('member','member','admin',403), ('member','admin','member',403),
    ('outsider','member','admin',404), ('owner','outsider','admin',404),
    ('owner','missing','admin',404),
])
def test_permission_matrix(seeded, actor, target, role, status):
    app, client, ws, ids, tokens, _ = seeded
    before = snapshot(app)
    response = patch(client,ws,ids.get(target,str(uuid4())),tokens[actor],role)
    assert response.status_code == status, response.text
    if status != 200:
        assert snapshot(app) == before
    else:
        assert response.json()['role'] == role
        with app.state.database.transaction() as session:
            assert session.scalar(select(members.c.role).where(members.c.id == ids[target])) == role


def test_authentication_csrf_and_persistent_revocation(seeded, settings):
    app, client, ws, ids, tokens, login = seeded
    url = f"/api/workspaces/{ws['id']}/members/{ids['member']}"
    before = snapshot(app)
    client.cookies.clear()
    assert client.patch(url,json={'role':'admin'}).status_code == 401
    assert snapshot(app) == before
    client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'})
    assert client.patch(url,json={'role':'admin'}).status_code == 403
    assert snapshot(app) == before
    csrf = client.cookies.get('workpal_csrf')
    assert client.patch(url,json={'role':'admin'},headers={'x-csrf-token':csrf}).status_code == 200
    assert client.post('/auth/logout',headers={'Authorization':'Bearer '+tokens['owner']}).status_code == 200
    before = snapshot(app)
    assert patch(client,ws,ids['member'],tokens['owner'],'member').status_code == 401
    assert snapshot(app) == before
    with TestClient(create_app(settings)) as reopened:
        assert patch(reopened,ws,ids['member'],tokens['owner'],'member').status_code == 401
    assert snapshot(app) == before


@pytest.mark.parametrize('stage,status,message', [
    ('target',404,'member not found'), ('count',500,'failed to update member'),
    ('update',500,'failed to update member'), ('join',500,'failed to load member'),
    ('lock',503,None),
])
def test_sql_stage_failures(seeded, stage, status, message):
    app, client, ws, ids, tokens, _ = seeded
    before = snapshot(app)
    seen = []
    writes = []
    def inject(conn, cursor, statement, parameters, context, executemany):
        sql = ' '.join(statement.lower().split())
        if sql.startswith('update members set role='):
            writes.append(parameters)
        match = {'target':sql.startswith('select members.') and 'where members.id =' in sql and 'join users' not in sql,
                 'count':'count(' in sql and 'from members' in sql,
                 'update':sql.startswith('update members set role='),
                 'join':'join users' in sql,
                 'lock':sql.startswith('select members.') and 'where members.id =' in sql and 'join users' not in sql}[stage]
        if match:
            seen.append(sql)
            raise OperationalError(statement,parameters,sqlite3.OperationalError('database is locked' if stage == 'lock' else 'injected stage failure'))
    event.listen(app.state.database.engine,'before_cursor_execute',inject)
    try:
        response = patch(client,ws,ids['owner2'] if stage == 'count' else ids['member'],tokens['owner'],'admin')
    finally:
        event.remove(app.state.database.engine,'before_cursor_execute',inject)
    assert seen
    assert response.status_code == status, response.text
    if message:
        assert response.json()['error'] == message
    else:
        assert response.json()['retryable'] is True
    if stage == 'join':
        assert writes, 'failure must occur after a real role-changing UPDATE'
    assert snapshot(app) == before
