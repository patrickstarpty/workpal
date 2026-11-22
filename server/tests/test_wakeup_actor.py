import asyncio
import pytest
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';T='cccccccc-cccc-cccc-cccc-cccccccccccc'
class Queries:
    def __init__(self):self.calls=[];self.fail_at=0;self.status='completed'
    def record(self,kind,identity):
        self.calls.append((kind,identity))
        if len(self.calls)==self.fail_at:raise asyncio.CancelledError()
    def get_agent(self,identity):self.record('agent',identity);return dict(id=A,workspace_id=W)
    def get_task(self,identity):self.record('task',identity);return dict(id=T,agent_id=A,status=self.status)

def capture(q,**kwargs):
    from workpal_backend.auth.wakeup_actor import capture_wakeup_actor
    return capture_wakeup_actor(q,'user',W,**kwargs)


def test_cached_actor_preserved_without_resolving_changed_headers():
    q=Queries();cached=('member','original','')
    assert capture(q,cached=cached,actor_source='task_token',agent_id=A,task_id=T) is cached
    assert q.calls==[]


def test_member_has_no_source_task_even_with_task_header():
    q=Queries();assert capture(q,task_id=T)==('member','user','');assert q.calls==[]


def test_trusted_task_token_uses_task_row_identity_without_terminal_status_filter():
    q=Queries();assert capture(q,actor_source='task_token',agent_id=A,task_id=T.upper())==('agent',A,T)
    assert q.calls==[('task',T)]


def test_legacy_actor_resolves_twice_before_loading_source_task():
    q=Queries();assert capture(q,agent_id=A,task_id=T)==('agent',A,T)
    assert q.calls==[('agent',A),('task',T),('agent',A),('task',T),('task',T)]

@pytest.mark.parametrize('fail_at',[3,4,5])
def test_second_resolution_or_source_failure_keeps_first_actor_without_source(fail_at):
    q=Queries();q.fail_at=fail_at
    assert capture(q,agent_id=A,task_id=T)==('agent',A,'')

@pytest.mark.parametrize('task',['','invalid',' '+T])
def test_invalid_source_header_does_not_query_but_trusted_actor_is_retained(task):
    q=Queries();assert capture(q,actor_source='task_token',agent_id=A,task_id=task)==('agent',A,'');assert q.calls==[]
