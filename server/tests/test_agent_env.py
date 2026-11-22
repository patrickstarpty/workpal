"""Env reveals must be authorized and durably audited before returning secrets."""
import json
from uuid import uuid4
import pytest
from sqlalchemy import text,event
from sqlalchemy.exc import OperationalError
from test_runtime_list import runtimes

@pytest.fixture
def env(runtimes):
    client,app,workspace,ids,rows,headers=runtimes
    agent=str(uuid4())
    with app.state.database.transaction() as session:
        session.execute(text("INSERT INTO agent(id,workspace_id,name,runtime_mode,owner_id,custom_env) VALUES (:id,:wid,'Env fixture','local',:owner,:env)"),
                        dict(id=agent,wid=workspace['id'],owner=ids[1],env=json.dumps({'Z_KEY':'private-z','A_KEY':'private-a'})))
    return client,app,workspace,ids,headers,agent

def test_reveal_persists_keys_only(env):
    client,app,workspace,ids,headers,agent=env
    response=client.get(f'/api/agents/{agent}/env',headers=headers())
    assert response.status_code==200
    assert response.content==('{"agent_id":"'+agent+'","custom_env":{"A_KEY":"private-a","Z_KEY":"private-z"}}\n').encode()
    with app.state.database.transaction() as session:
        row=session.execute(text('SELECT * FROM activity_log')).mappings().one()
    assert row['actor_id']==ids[1] and row['actor_type']=='member'
    assert row['issue_id'] is None and row['action']=='agent_env_revealed'
    assert json.loads(row['details'])==dict(agent_id=agent,agent_name='Env fixture',revealed_keys=['A_KEY','Z_KEY'],key_count=2)
    assert 'private-' not in row['details']

def test_reveal_permission_and_kind(env):
    client,app,workspace,ids,headers,agent=env
    assert client.get(f'/api/agents/{agent}/env',headers=headers(ids[0])).status_code==200
    assert client.get(f'/api/agents/{agent}/env',headers=headers(ids[2])).status_code==404
    with app.state.database.transaction() as session:
        session.execute(text('UPDATE agent SET owner_id=NULL'))
    assert client.get(f'/api/agents/{agent}/env',headers=headers()).status_code==403
    with app.state.database.transaction() as session:
        session.execute(text("UPDATE agent SET kind='system'"))
    assert client.get(f'/api/agents/{agent}/env',headers=headers(ids[0])).status_code==404
    assert client.get('/api/agents/invalid/env',headers=headers()).status_code==400

def test_audit_failure_never_reveals(env):
    client,app,workspace,ids,headers,agent=env
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO activity_log'):
            raise OperationalError(statement,parameters,Exception('fixture audit outage'))
    event.listen(app.state.database.engine,'before_cursor_execute',fail)
    try:
        response=client.get(f'/api/agents/{agent}/env',headers=headers())
        assert response.status_code==500
        assert response.json()=={'error':'audit log write failed; refusing to serve env without a recorded reveal'}
        assert 'private-' not in response.text
    finally:event.remove(app.state.database.engine,'before_cursor_execute',fail)

@pytest.mark.parametrize('raw,expected',[(None,{}),('null',{}),('[1]',{}),('{"a":12}',{}),('{"a":null}',{'a':''}),('{"z":"yes","a":"ok"}',{'a':'ok','z':'yes'})])
def test_env_go_map_decoding(env,raw,expected):
    client,app,workspace,ids,headers,agent=env
    # custom_env is NOT NULL in the Go schema, so None uses its empty default.
    with app.state.database.transaction() as session:
        session.execute(text('UPDATE agent SET custom_env=:value'),dict(value=raw or '{}'))
    response=client.get(f'/api/agents/{agent}/env',headers=headers())
    assert response.status_code==200
    assert response.json()['custom_env']==expected


def test_commit_failure_never_reveals_and_rolls_back_audit(env):
    client,app,workspace,ids,headers,agent=env
    def fail_commit(conn):
        if conn.exec_driver_sql('SELECT count(*) FROM activity_log').scalar():
            raise OperationalError('COMMIT',{},Exception('fixture commit outage'))
    event.listen(app.state.database.engine,'commit',fail_commit)
    try:
        response=client.get(f'/api/agents/{agent}/env',headers=headers())
        assert response.status_code==500
        assert 'private-' not in response.text
    finally:event.remove(app.state.database.engine,'commit',fail_commit)
    with app.state.database.transaction() as session:
        assert session.scalar(text('SELECT count(*) FROM activity_log'))==0


def test_middleware_errors_do_not_have_handler_newline(env):
    client,app,workspace,ids,headers,agent=env
    h=headers()
    h.pop('X-Workspace-Slug')
    response=client.get(f'/api/agents/{agent}/env',headers=h)
    assert response.content==b'{"error":"workspace_id or workspace_slug is required"}'
    response=client.get('/api/agents/bad/env',headers=headers())
    assert response.content==b'{"error":"invalid agent id"}\n'
