import asyncio
import pytest

W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
A='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
T='cccccccc-cccc-cccc-cccc-cccccccccccc'


class Queries:
    def __init__(self,fail='',workspace=W,agent=A):self.fail=fail;self.workspace=workspace;self.agent=agent;self.calls=[]
    def get_agent(self,identity):
        self.calls.append(('agent',identity))
        if self.fail=='agent':raise RuntimeError('unavailable')
        return {'workspace_id':self.workspace}
    def get_task(self,identity):
        self.calls.append(('task',identity))
        if self.fail=='task':raise RuntimeError('unavailable')
        if self.fail=='cancel':raise asyncio.CancelledError()
        return {'agent_id':self.agent}


@pytest.mark.parametrize(('agent','task'),[('',T),(A,''),('invalid',T)])
def test_missing_or_invalid_agent_claim_falls_back_without_queries(agent,task):
    from workpal_backend.auth.actor import resolve_actor
    q=Queries()
    assert resolve_actor(q,'user',W,agent_id=agent,task_id=task)==('member','user')
    assert q.calls==[]


def test_task_token_server_identity_is_authoritative():
    from workpal_backend.auth.actor import resolve_actor
    q=Queries(fail='agent')
    assert resolve_actor(q,'user',W,actor_source='task_token',agent_id='bound-agent')==('agent','bound-agent')
    assert q.calls==[]


@pytest.mark.parametrize('failure',['agent','task','cancel'])
def test_query_failure_falls_back_to_member(failure):
    from workpal_backend.auth.actor import resolve_actor
    assert resolve_actor(Queries(fail=failure),'user',W,agent_id=A,task_id=T)==('member','user')


def test_fallback_requires_matching_workspace_then_matching_task_agent():
    from workpal_backend.auth.actor import resolve_actor
    assert resolve_actor(Queries(workspace=T),'user',W,agent_id=A,task_id=T)==('member','user')
    assert resolve_actor(Queries(agent=W),'user',W,agent_id=A,task_id=T)==('member','user')
    q=Queries()
    assert resolve_actor(q,'user',W,agent_id=A,task_id=T)==('agent',A)
    assert q.calls==[('agent',A),('task',T)]


def test_invalid_task_is_checked_after_agent_lookup():
    from workpal_backend.auth.actor import resolve_actor
    q=Queries()
    assert resolve_actor(q,'user',W,agent_id=A,task_id='invalid')==('member','user')
    assert q.calls==[('agent',A)]


def test_go_compares_raw_identity_headers_after_parsing():
    from workpal_backend.auth.actor import resolve_actor
    assert resolve_actor(Queries(),'user',W,agent_id=A.upper(),task_id=T)==('member','user')
    assert resolve_actor(Queries(),'user',W.upper(),agent_id=A,task_id=T)==('member','user')


def test_null_stored_workspace_compares_as_go_empty_uuid_string():
    from workpal_backend.auth.actor import resolve_actor
    q=Queries(workspace=None)
    assert resolve_actor(q,'user','',agent_id=A,task_id=T)==('agent',A)
    assert q.calls==[('agent',A),('task',T)]
