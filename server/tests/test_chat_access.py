import pytest
from workpal_backend.infrastructure.query_errors import NoRows
W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
U='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
S='cccccccc-cccc-cccc-cccc-cccccccccccc'
A='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,failure='',creator=U,owner=U,role='member'):
        self.failure=failure;self.creator=creator;self.owner=owner;self.role=role;self.calls=[]
    def call(self,kind,*args):
        self.calls.append((kind,*args))
        if self.failure==kind:raise NoRows()
    def get_chat_session_in_workspace(self,identity,workspace):
        self.call('session',identity,workspace)
        return dict(id=S,workspace_id=W,agent_id=A,creator_id=self.creator)
    def get_agent(self,identity):
        self.call('agent',identity)
        return dict(id=A,owner_id=self.owner,permission_mode='private')
    def get_member(self,workspace,user):self.call('member',workspace,user);return dict(role=self.role)
    def get_public_chat_session_in_workspace(self,identity,workspace):self.call('public',identity,workspace);return {}

def gate(q,session=S,workspace=W,user=U,**kwargs):
    from workpal_backend.chat.access import public_session_for_user
    return public_session_for_user(q,user,workspace,session,**kwargs)

def error(status,message,fn):
    from workpal_backend.chat.access import ChatAccessError
    with pytest.raises(ChatAccessError) as caught:fn()
    assert (caught.value.status,caught.value.message)==(status,message)

@pytest.mark.parametrize(('session','workspace','message'),[('invalid','invalid','invalid chat session id'),(S,'invalid','invalid workspace id')])
def test_validation_order(session,workspace,message):
    q=Queries();error(400,message,lambda:gate(q,session,workspace));assert not q.calls

@pytest.mark.parametrize(('failure','message'),[('session','chat session not found'),('agent','agent not found'),('public','chat session not found')])
def test_missing_row_at_each_stage_is_not_found(failure,message):
    error(404,message,lambda:gate(Queries(failure=failure)))


def test_creator_mismatch_denies_before_agent_lookup():
    q=Queries(creator=W);error(403,'not your chat session',lambda:gate(q));assert q.calls==[('session',S,W)]


def test_creator_is_rechecked_against_current_agent_permission():
    q=Queries(owner=W)
    error(403,'you do not have access to this agent',lambda:gate(q))
    assert q.calls==[('session',S,W),('agent',A),('member',W,U)]
    q.role='admin'
    assert gate(q)['id']==S
    assert q.calls[-1]==('public',S,W)


def test_task_actor_still_requires_session_creator_then_skips_member_gate():
    q=Queries(owner=W)
    assert gate(q,actor_source='task_token',agent_id=A)['id']==S
    assert q.calls==[('session',S,W),('agent',A),('public',S,W)]


def test_lower_gate_keeps_recovery_access_to_nonpublic_sessions():
    from workpal_backend.chat.access import session_for_user
    q=Queries(failure='public')
    assert session_for_user(q,U,W,S)['id']==S
    assert q.calls==[('session',S,W),('agent',A)]
