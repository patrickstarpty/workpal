"""Update primitives preserve masked values and commit audit with state."""
import json
import pytest
from sqlalchemy import event,text
from sqlalchemy.exc import OperationalError
from test_agent_env import env
from test_runtime_list import runtimes


def test_merge_sentinel_and_audit_are_exact_and_do_not_mutate():
    from workpal_backend.agents.env_update import merge_env
    existing={'keep':'secret','same':'same','change':'old','remove':'gone'}
    requested={'keep':'****','new-mask':'****','same':'same','change':'new','z':'last','a':''}
    merged,audit=merge_env(existing,requested)
    assert merged=={'keep':'secret','same':'same','change':'new','z':'last','a':''}
    assert audit=={'added_keys':['a','z'],'removed_keys':['remove'],'changed_keys':['change'],'preserved_keys':['keep']}
    assert existing['change']=='old' and requested['keep']=='****'
    assert merge_env({}, {})==({},dict(added_keys=None,removed_keys=None,changed_keys=None,preserved_keys=None))


def test_update_and_keys_only_audit_commit_together(env):
    from workpal_backend.agents.env_update import persist_env,merge_env
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        row=dict(session.execute(text('SELECT * FROM agent WHERE id=:id'),dict(id=agent)).mappings().one())
    merged,audit=merge_env(json.loads(row['custom_env']),{'Z_KEY':'****','new':'private-new'})
    updated=persist_env(app.state.database,row,ids[1],merged,audit)
    assert json.loads(updated['custom_env'])=={'Z_KEY':'private-z','new':'private-new'}
    with app.state.database.transaction() as session:
        record=session.execute(text('SELECT * FROM activity_log')).mappings().one()
        assert record['action']=='agent_env_updated' and record['issue_id'] is None
        assert 'private-' not in record['details']
        assert json.loads(record['details'])==dict(agent_id=agent,agent_name='Env fixture',**audit)


@pytest.mark.parametrize('stage',['update','audit','commit'])
def test_failure_rolls_back_env_and_audit(env,stage):
    from workpal_backend.agents.env_update import persist_env,EnvWriteError
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        row=dict(session.execute(text('SELECT * FROM agent WHERE id=:id'),dict(id=agent)).mappings().one())
    def statement_failure(conn,cursor,statement,parameters,context,executemany):
        if (stage=='update' and statement.startswith('UPDATE agent')) or (stage=='audit' and statement.startswith('INSERT INTO activity_log')):
            raise OperationalError(statement,parameters,Exception('fixture write outage'))
    def commit_failure(conn):
        if stage=='commit':raise OperationalError('COMMIT',{},Exception('fixture commit outage'))
    event.listen(app.state.database.engine,'before_cursor_execute',statement_failure)
    event.listen(app.state.database.engine,'commit',commit_failure)
    try:
        with pytest.raises(EnvWriteError) as error:
            persist_env(app.state.database,row,ids[1],{'new':'secret'},dict(added_keys=['new'],removed_keys=['A_KEY','Z_KEY'],changed_keys=None,preserved_keys=None))
        assert str(error.value)==('audit log write failed; env update rolled back' if stage=='audit' else 'failed to update env')
    finally:
        event.remove(app.state.database.engine,'before_cursor_execute',statement_failure)
        event.remove(app.state.database.engine,'commit',commit_failure)
    with app.state.database.transaction() as session:
        after=dict(session.execute(text('SELECT * FROM agent WHERE id=:id'),dict(id=agent)).mappings().one())
        assert after==row
        assert session.scalar(text('SELECT count(*) FROM activity_log'))==0


@pytest.mark.parametrize('raw,expected',[
    (b'null',{}),(b'{}',{}),(b'{"custom_env":null}',{}),
    (b'{"custom_env":{"x":null}}',{'x':''}),
    (b'{"custom_env":{"a":"first"},"CUSTOM_ENV":{"b":"next"}}',{'a':'first','b':'next'}),
    (b'{"custom_env":{"a":"first"},"custom_env":null}',{}),
    (b'{"custom_env":{"x":"value","x":null}}',{'x':''}),
    (b'{"custom_env":{"x":"value"}} trailing',{'x':'value'}),
])
def test_decode_env_update_go_struct(raw,expected):
    from workpal_backend.agents.env_update import decode_update
    assert decode_update(raw)==expected


@pytest.mark.parametrize('raw',[b'',b'[]',b'{"custom_env":[]}',b'{"custom_env":{"a":1}}',
    b'{"custom_env":{"a":1},"custom_env":{}}',b'{"custom_env":{"a":false}}'])
def test_decode_env_update_rejects_bad_types(raw):
    from workpal_backend.agents.env_update import decode_update
    with pytest.raises(ValueError,match='invalid request body'):decode_update(raw)


def test_unknown_large_numeric_field_is_skipped():
    from workpal_backend.agents.env_update import decode_update
    assert decode_update(b'{"ignored":'+b'9'*5000+b',"custom_env":{"a":"ok"}}')=={'a':'ok'}


def test_put_updates_and_publishes_redacted_skill_summary(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        session.execute(text('UPDATE agent SET runtime_config=:config,mcp_config=:mcp,composio_toolkit_allowlist=:allow'),dict(config='{"gateway":{"token":"private-gateway"}}',mcp='{"secret":"private-mcp"}',allow='["private-toolkit"]'))
    response=client.put(f'/api/agents/{agent}/env',headers=headers(),json={'custom_env':{'Z_KEY':'****','new':'private-new'}})
    assert response.status_code==200
    assert response.json()['custom_env']=={'Z_KEY':'private-z','new':'private-new'}
    with app.state.database.transaction() as session:
        event=json.loads(session.scalar(text('SELECT envelope FROM outbox')))
    assert event['type']=='agent:status' and event['actorID']==ids[1]
    projected=event['payload']['agent']
    assert projected['runtime_config']['gateway']['token']=='***'
    assert projected['mcp_config'] is None and projected['mcp_config_redacted'] is True
    assert projected['composio_toolkit_allowlist_redacted'] is True
    assert projected['custom_env_key_count']==2
    assert 'private-' not in json.dumps(event)
    assert 'custom_env' not in projected and projected['skills']==[]


def test_put_authorization_before_decode_and_qoder_refusal(env):
    client,app,workspace,ids,headers,agent=env
    assert client.put(f'/api/agents/{agent}/env',headers=headers(ids[2]),content='bad').status_code==404
    with app.state.database.transaction() as session:
        runtime=session.scalar(text("SELECT id FROM agent_runtime LIMIT 1"))
        session.execute(text("UPDATE agent_runtime SET provider='qoder_cloud' WHERE id=:id"),dict(id=runtime))
        session.execute(text('UPDATE agent SET runtime_id=:id'),dict(id=runtime))
    assert client.put(f'/api/agents/{agent}/env',headers=headers(),json={'custom_env':{'key':'value'}}).status_code==400
    assert client.put(f'/api/agents/{agent}/env',headers=headers(),json={'custom_env':{}}).status_code==200


def test_put_skill_failure_is_after_commit_and_emits_nothing(env):
    client,app,workspace,ids,headers,agent=env
    def fail(conn,cursor,statement,parameters,context,executemany):
        if 'JOIN agent_skill' in statement:raise OperationalError(statement,parameters,Exception('fixture skills outage'))
    event.listen(app.state.database.engine,'before_cursor_execute',fail)
    try:
        response=client.put(f'/api/agents/{agent}/env',headers=headers(),json={'custom_env':{'new':'value'}})
        assert response.status_code==500 and response.json()=={'error':'failed to load agent skills'}
    finally:event.remove(app.state.database.engine,'before_cursor_execute',fail)
    with app.state.database.transaction() as session:
        assert json.loads(session.scalar(text('SELECT custom_env FROM agent')))=={'new':'value'}
        assert session.scalar(text('SELECT count(*) FROM activity_log'))==1
        assert session.scalar(text('SELECT count(*) FROM outbox'))==0


def test_event_subscriber_failure_does_not_undo_success(env):
    client,app,workspace,ids,headers,agent=env
    called=[]
    def fail(event):raise RuntimeError('fixture listener failure')
    app.state.events.subscribe('agent:status',fail)
    app.state.events.subscribe('agent:status',lambda event:called.append(event['type']))
    response=client.put(f'/api/agents/{agent}/env',headers=headers(),json={'custom_env':{}})
    assert response.status_code==200 and called==['agent:status']
    with app.state.database.transaction() as session:
        assert session.scalar(text('SELECT count(*) FROM outbox'))==1


def test_broadcast_struct_fields_follow_jsonb_order_and_empty_omitempty():
    from workpal_backend.agents.projection import struct_array
    assert struct_array('[{"NAME":"old","name":""}]',('key',),('name',))==[{'key':''}]
    # PostgreSQL JSONB stores same-length object keys in byte order, so lower
    # case name is decoded last even if the original input had it first.
    assert struct_array('[{"name":"last","NAME":"first"}]',('key',),('name',))==[{'key':'','name':'last'}]
