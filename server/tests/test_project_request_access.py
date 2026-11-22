import pytest
from workpal_backend.infrastructure.query_errors import NoRows

W='00000000-0000-0000-0000-000000000001'
P='00000000-0000-0000-0000-000000000002'
U='00000000-0000-0000-0000-000000000003'
A='00000000-0000-0000-0000-000000000004'
T='00000000-0000-0000-0000-000000000005'
O='00000000-0000-0000-0000-000000000006'


class Queries:
    def __init__(self, failure='', empty=False):self.calls=[];self.failure=failure;self.empty=empty
    def record(self,kind,*args):
        self.calls.append((kind,*args))
        if self.failure==kind:raise RuntimeError('query failed')
        if self.failure==kind+'-missing':raise NoRows()
    def list_private_project_ids(self,w):self.record('private',w);return [] if self.empty else [P]
    def get_task(self,t):self.record('task',t);return {'originator_user_id':U,'accountable_user_id':A}
    def get_agent(self,a):self.record('agent',a);return {'owner_id':O}
    def get_member(self,w,u):self.record('member',w,u);return {}
    def list_hidden_project_ids(self,w,u):self.record('hidden',w,u);return [P] if u==O else []


def test_agent_run_is_bounded_by_originator_and_agent_owner():
    from workpal_backend.projects.request_access import hidden_for_agent_run
    q=Queries()
    assert hidden_for_agent_run(q,W,A,T).ids()==[P]
    assert q.calls==[('private',W),('task',T),('agent',A),('private',W),('member',W,U),('hidden',W,U),('member',W,O),('hidden',W,O)]


@pytest.mark.parametrize('failure',['task-missing','agent-missing'])
def test_missing_run_identity_hides_every_private_project(failure):
    from workpal_backend.projects.request_access import hidden_for_agent_run
    q=Queries(failure)
    assert hidden_for_agent_run(q,W,A,T).ids()==[P]
    assert not any(call[0] in ('member','hidden') for call in q.calls)


@pytest.mark.parametrize('failure',['private','task','agent','member','hidden'])
def test_lookup_failures_propagate(failure):
    from workpal_backend.projects.request_access import hidden_for_agent_run
    with pytest.raises(RuntimeError):hidden_for_agent_run(Queries(failure),W,A,T)


def test_no_private_projects_skips_run_lookups():
    from workpal_backend.projects.request_access import hidden_for_agent_run
    q=Queries(empty=True)
    assert hidden_for_agent_run(q,W,'invalid','invalid').empty()
    assert q.calls==[('private',W)]


def test_invalid_task_hides_projects_without_fetching_task():
    from workpal_backend.projects.request_access import hidden_for_agent_run
    q=Queries()
    assert hidden_for_agent_run(q,W,A,'invalid').ids()==[P]
    assert q.calls==[('private',W),('private',W)]


def test_matching_request_member_uses_fast_path_only():
    from workpal_backend.projects.request_access import hidden_for_request
    q=Queries()
    assert hidden_for_request(q,W,U,'user',U,context_member={'workspace_id':W,'user_id':U}).empty()
    assert q.calls==[('hidden',W,U)]


def test_context_member_for_other_user_does_not_bypass_membership():
    from workpal_backend.projects.request_access import hidden_for_request
    q=Queries()
    hidden_for_request(q,W,U,'user',U,context_member={'workspace_id':W,'user_id':O})
    assert q.calls==[('private',W),('member',W,U),('hidden',W,U)]
