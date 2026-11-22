import asyncio
import pytest
U='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
A='cccccccc-cccc-cccc-cccc-cccccccccccc'
class Queries:
    def __init__(self,role='member',targets=(),failure=''):self.role=role;self.targets=targets;self.failure=failure;self.calls=[]
    def get_member(self,workspace,user):
        self.calls.append(('member',workspace,user))
        if self.failure=='member':raise RuntimeError('unavailable')
        return {'role':self.role}
    def list_agent_invocation_targets(self,agent):
        self.calls.append(('targets',agent))
        if self.failure=='targets':raise asyncio.CancelledError()
        return self.targets

def agent(owner=None,mode='private'):return dict(id=A,owner_id=owner,permission_mode=mode)

@pytest.mark.parametrize(('actor_type','actor_id','owner'),[('agent','anything',None),('member',U,U),('member','',None)])
def test_agent_actor_and_exact_owner_skip_queries(actor_type,actor_id,owner):
    from workpal_backend.agents.access import can_access_private_agent
    q=Queries(failure='member')
    assert can_access_private_agent(q,agent(owner),actor_type,actor_id,W)
    assert not q.calls

@pytest.mark.parametrize(('role','allowed'),[('owner',True),('admin',True),('Admin',False),('member',False)])
def test_workspace_manager_access_is_exact_role_match(role,allowed):
    from workpal_backend.agents.access import can_access_private_agent
    q=Queries(role)
    assert can_access_private_agent(q,agent(),'member',U,W)==allowed
    assert q.calls==[('member',W,U)]

@pytest.mark.parametrize(('targets','allowed'),[([],False),([{'target_type':'workspace','target_id':None}],True),([{'target_type':'member','target_id':U}],True),([{'target_type':'member','target_id':W}],False),([{'target_type':'team','target_id':U}],False)])
def test_public_to_targets_and_batch_filter_agree(targets,allowed):
    from workpal_backend.agents.access import can_access_private_agent,member_allowed_to_view_agent
    q=Queries(targets=targets);row=agent(mode='public_to')
    assert can_access_private_agent(q,row,'member',U,W)==allowed
    assert member_allowed_to_view_agent(row,targets,U,'member')==allowed
    assert q.calls==[('member',W,U),('targets',A)]

@pytest.mark.parametrize('failure',['member','targets'])
def test_query_failure_denies_access(failure):
    from workpal_backend.agents.access import can_access_private_agent
    assert not can_access_private_agent(Queries(failure=failure),agent(mode='public_to'),'member',U,W)


def test_raw_actor_id_is_not_canonicalized_for_owner_or_target_comparison():
    from workpal_backend.agents.access import can_access_private_agent
    q=Queries(targets=[{'target_type':'member','target_id':U}])
    assert not can_access_private_agent(q,agent(owner=U,mode='public_to'),'member',U.upper(),W)
    assert q.calls[0]==('member',W,U)
