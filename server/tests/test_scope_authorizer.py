import pytest
from workpal_backend.realtime.scope_authorizer import ScopeAuthorizer
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.realtime.protocol import parse_frame

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
U,W,S,T,I=map(uid,range(1,6))
class Queries:
    def __init__(self):self.calls=[];self.task={'chat_session_id':S};self.failure=None
    def read(self,name,row):
        self.calls.append(name)
        if self.failure:raise self.failure
        return row
    def get_task(self,id):return self.read('task',self.task)
    def get_issue(self,id):return self.read('issue',{'workspace_id':W})
    def get_chat_session(self,id):return self.read('chat',{'workspace_id':W,'creator_id':U})

@pytest.mark.parametrize('scope,user,workspace,identity,expected',[
 ('chat',U,W,S,True),('chat',uid(9),W,S,False),('chat','',W,S,False),
 ('chat',U,uid(9),S,False),('task',U,W,T,True),('task',uid(9),W,T,False),
 ('task',U,'bad',T,False),('task',U,W,'bad',False),('workspace',U,W,S,False),
])
def test_creator_and_workspace_scope(scope,user,workspace,identity,expected):
    assert ScopeAuthorizer(Queries())(user,workspace,scope,identity)==expected


def test_issue_task_precedence_and_orphan_denial():
    q=Queries();q.task={'issue_id':I,'chat_session_id':S}
    assert ScopeAuthorizer(q)('',W,'task',T)
    assert q.calls==['task','issue']
    q.task={};assert not ScopeAuthorizer(q)(U,W,'task',T)


def test_missing_versus_query_failure_and_protocol_reason():
    q=Queries();a=ScopeAuthorizer(q);q.failure=NoRows()
    assert not a(U,W,'chat',S)
    q.failure=RuntimeError('database down')
    with pytest.raises(RuntimeError):a(U,W,'chat',S)
    raw='{"type":"subscribe","payload":{"scope":"chat","id":"'+S+'"}}'
    assert parse_frame(raw,W,U,authorizer=a).reply['payload']['error']=='lookup_failed'
    q.failure=None
    assert parse_frame(raw,W,U,authorizer=a).action==('subscribe','chat',S)
    assert parse_frame(raw,W,uid(9),authorizer=a).reply['payload']['error']=='forbidden'

from test_agent_env import env
from test_runtime_list import runtimes
from sqlalchemy import text,event as sql_event
from sqlalchemy.exc import OperationalError


def test_real_socket_chat_creator_denial_and_lookup_failure(env):
    client,app,workspace,ids,headers,agent=env
    with app.state.database.transaction() as session:
        chat=session.scalar(text('INSERT INTO chat_session(workspace_id,creator_id,agent_id) VALUES (:w,:u,:a) RETURNING id'),dict(w=workspace['id'],u=ids[1],a=agent))
    def connect(user):return client.websocket_connect('/ws?workspace_id='+workspace['id'],headers={'cookie':'workpal_auth='+headers(user)['Authorization'].split(' ',1)[1]})
    frame=dict(type='subscribe',payload=dict(scope='chat',id=chat))
    with connect(ids[1]) as ws:
        ws.send_json(frame)
        assert ws.receive_json()==dict(type='subscribe_ack',payload=frame['payload'])
        ws.send_json(dict(type='unsubscribe',payload=frame['payload']))
        assert ws.receive_json()==dict(type='unsubscribe_ack',payload=frame['payload'])
    with connect(ids[0]) as ws:
        ws.send_json(frame)
        assert ws.receive_json()['payload']['error']=='forbidden'
    def fail(conn,cursor,statement,parameters,context,executemany):
        if 'FROM chat_session' in statement:raise OperationalError(statement,parameters,Exception('fixture outage'))
    sql_event.listen(app.state.database.engine,'before_cursor_execute',fail)
    try:
        with connect(ids[1]) as ws:
            ws.send_json(frame)
            assert ws.receive_json()['payload']['error']=='lookup_failed'
    finally:sql_event.remove(app.state.database.engine,'before_cursor_execute',fail)
