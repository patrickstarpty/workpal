"""Real HTTP reads of canonical runtime rows, including private machine visibility."""
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from workpal_backend.app import create_app
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.workspaces.service import create_workspace


@pytest.fixture
def runtimes(settings):
    settings.auth_secret='s'*64
    migrate(settings)
    app=create_app(settings)
    uid,other,outsider=[str(uuid4()) for _ in range(3)]
    with TestClient(app) as client:
        with app.state.database.transaction() as session:
            for user in [uid,other,outsider]:
                session.execute(text("INSERT INTO users(id,email,name,created_at,updated_at) VALUES (:id,:email,'Fixture','2026-01-01','2026-01-01')"),dict(id=user,email=user+'@example.com'))
            workspace=create_workspace(session,uid,'Runtime list','runtime-list')
            session.execute(text("INSERT INTO members(id,workspace_id,user_id,role,created_at) VALUES (:id,:wid,:uid,'member','2026-01-01')"),dict(id=str(uuid4()),wid=workspace['id'],uid=other))
            rows=[]
            for name,owner,visibility,shared in [
                ('mine',other,'private',[]),('private',uid,'private',[]),
                ('shared',uid,'private',[other]),('public',None,'public',[])]:
                row=session.execute(text("""INSERT INTO agent_runtime(workspace_id,name,runtime_mode,provider,owner_id,visibility,shared_with,created_at,updated_at)
                    VALUES (:wid,:name,'local','omp',:owner,:visibility,:shared,:stamp,:stamp) RETURNING *"""),
                    dict(wid=workspace['id'],name=name,owner=owner,visibility=visibility,shared=json.dumps(shared),
                         stamp=f'2026-01-0{len(rows)+1}T01:02:03.456789Z')).mappings().one()
                rows.append(dict(row))
        def headers(user=other):
            return {'Authorization':'Bearer '+issue_session(user,user+'@example.com','Fixture',settings.auth_secret,3600),
                    'X-Workspace-Slug':'runtime-list'}
        yield client,app,workspace,(uid,other,outsider),rows,headers


def test_member_visibility_and_exact_projection(runtimes):
    client,app,workspace,ids,rows,headers=runtimes
    response=client.get('/api/runtimes',headers=headers())
    assert response.status_code==200
    result=response.json()
    assert [r['name'] for r in result]==['mine','shared','public']
    first=result[0]
    assert first['launch_header']=='omp (json mode)'
    assert first['created_at']=='2026-01-01T01:02:03Z'
    assert first['metadata']=={} and first['shared_with']==[]
    assert first['custom_name'] is None and first['profile_id'] is None
    assert first['last_seen_at'] is None and first['max_concurrent_tasks'] is None
    assert 'legacy_daemon_id' not in first
    assert response.content.endswith(b'\n')
    assert [r['name'] for r in client.get('/api/runtimes?owner=me',headers=headers()).json()]==['mine']
    assert [r['name'] for r in client.get('/api/runtimes?owner=me&owner=other',headers=headers()).json()]==['mine']


def test_admin_governance_and_tenant_isolation(runtimes):
    client,app,workspace,(owner,member,outsider),rows,headers=runtimes
    assert len(client.get('/api/runtimes',headers=headers(owner)).json())==4
    assert [r['name'] for r in client.get('/api/runtimes?owner=me',headers=headers(owner)).json()]==['private','shared']
    assert client.get('/api/runtimes',headers=headers(outsider)).status_code==404
    with app.state.database.transaction() as session:
        session.execute(text('DELETE FROM members WHERE user_id=:uid'),dict(uid=member))
    assert client.get('/api/runtimes',headers=headers(member)).status_code==404


def test_workspace_selector_order(runtimes):
    client,app,workspace,ids,rows,headers=runtimes
    h=headers()
    assert client.get('/api/runtimes?workspace_slug=unknown',headers=h).status_code==404
    h.pop('X-Workspace-Slug')
    response=client.get('/api/runtimes',headers=h)
    assert response.status_code==400
    assert response.json()=={'error':'workspace_id or workspace_slug is required'}
    assert client.get('/api/runtimes?workspace_id='+workspace['id'],headers=h).status_code==200
    assert client.get('/api/runtimes?workspace_id=nope',headers=h).status_code==400
    h['X-Workspace-ID']=workspace['id']
    assert client.get('/api/runtimes?workspace_id=nope&workspace_id='+workspace['id'],headers=h).status_code==400
    assert client.get('/api/runtimes?workspace_id=%zz',headers=h).status_code==200


def test_runtime_query_error_is_explicit_and_reads_do_not_write(runtimes):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    client,app,workspace,ids,rows,headers=runtimes
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('SELECT * FROM agent_runtime'):
            raise OperationalError(statement,parameters,Exception('fixture database failure'))
    event.listen(app.state.database.engine,'before_cursor_execute',fail)
    try:
        response=client.get('/api/runtimes',headers=headers())
        assert response.status_code==500
        assert response.content==b'{"error":"failed to list runtimes"}\n'
    finally:
        event.remove(app.state.database.engine,'before_cursor_execute',fail)
    with app.state.database.transaction() as session:
        after=[dict(r) for r in session.execute(text('SELECT * FROM agent_runtime ORDER BY created_at')).mappings()]
        assert after==rows
        assert session.scalar(text('SELECT count(*) FROM outbox'))==0


def test_uuid_array_projection_and_membership_are_canonical(runtimes):
    client,app,workspace,(owner,member,outsider),rows,headers=runtimes
    with app.state.database.transaction() as session:
        session.execute(text('UPDATE agent_runtime SET shared_with=:shared WHERE name=\'shared\''),
                        dict(shared=json.dumps([None,member.upper()])))
    result=client.get('/api/runtimes',headers=headers()).json()
    shared=next(row for row in result if row['name']=='shared')
    assert shared['shared_with']==['',member]


@pytest.mark.parametrize('raw,expected',[('{"a":2,"a":1}',{'a':1}),('{"a":1,"a":{}}',{'a':{}})])
def test_jsonb_duplicate_keys_last_value_wins(runtimes,raw,expected):
    client,app,workspace,ids,rows,headers=runtimes
    with app.state.database.transaction() as session:
        session.execute(text("UPDATE agent_runtime SET metadata=:value WHERE name='mine'"),dict(value=raw))
    response=client.get('/api/runtimes',headers=headers())
    assert response.status_code==200
    assert response.json()[0]['metadata']==expected


def test_order_uses_timestamp_instant_not_text(runtimes):
    client,app,workspace,ids,rows,headers=runtimes
    with app.state.database.transaction() as session:
        for name,stamp in [('mine','2026-01-01T00:00:00Z'),
                           ('shared','2026-01-01T00:00:00.1Z'),
                           ('public','2026-01-01T01:00:00.2+01:00')]:
            session.execute(text('UPDATE agent_runtime SET created_at=:stamp WHERE name=:name'),dict(name=name,stamp=stamp))
    result=client.get('/api/runtimes',headers=headers()).json()
    assert [row['name'] for row in result]==['mine','shared','public']
    assert result[-1]['created_at']=='2026-01-01T00:00:00Z'
