import pytest
import json
from workpal_backend.realtime.private_projects import PrivateProjectAudience, NoRows

W='00000000-0000-0000-0000-000000000001'
T='00000000-0000-0000-0000-000000000002'
P='00000000-0000-0000-0000-000000000003'
P2='00000000-0000-0000-0000-000000000004'
I='00000000-0000-0000-0000-000000000005'
U='00000000-0000-0000-0000-000000000006'
V='00000000-0000-0000-0000-000000000007'

class Queries:
    def __init__(self):
        self.rows=[(P,U),(P,V),(P2,V)];self.projects=[P];self.calls=[];self.fail=False
    def list_private_project_audience(self,w):
        self.calls.append(('workspace',w))
        if self.fail:raise RuntimeError('database down')
        return self.rows
    def list_issue_project_ids(self,ids):
        self.calls.append(('projects',ids));return [(I,self.projects[1])]
    def get_task(self,t):
        self.calls.append(('task',t))
        context=dict(type='quick_create',project_id=self.projects[0])
        if len(self.projects)>1:context['parent_issue_id']=I
        return dict(context=json.dumps(context))
    def issue_project(self,i):self.calls.append(('issue',i));return P
    def comment_project(self,i):self.calls.append(('comment',i));return P2
    def autopilot_project(self,i):self.calls.append(('autopilot',i));return P2


def event(kind='task:message',**fields):
    return dict(type=kind,workspaceID=W,taskID=T,payload=fields)


def test_cache_expiry_and_member_revocation():
    q=Queries();clock=[0.0];a=PrivateProjectAudience(q,now=lambda:clock[0])
    for _ in range(200): assert a(event())==([U,V],True)
    assert len(q.calls)==2
    q.rows=[(P,V)]
    a(event('project:members_changed',project_id=P))
    assert a(event())==([V],True)
    q.rows=[(P,None)];clock[0]=1.999
    assert a(event())==([V],True)
    clock[0]=2
    assert a(event())==(None,True)


def test_intersection_preserves_duplicates_and_does_not_mutate_cache():
    q=Queries();q.rows=[(P,U),(P,V),(P,V),(P2,V)];q.projects=[P,P2]
    a=PrivateProjectAudience(q)
    assert a(event())==([V,V],True)
    assert a(event('unknown',issue={'project_id':P}))==([U,V,V],True)


@pytest.mark.parametrize('kind',['issue:updated','autopilot:updated','project:updated','member:updated','task:queued','task:completed','task:failed','task:cancelled'])
def test_invalidation_changes_task_project(kind):
    q=Queries();a=PrivateProjectAudience(q)
    assert a(event())==([U,V],True)
    q.projects=[P2];a(event(kind))
    assert a(event())==([V],True)


def test_errors_retry_and_unknown_ids_do_not_allocate_cache():
    q=Queries();a=PrivateProjectAudience(q);q.fail=True
    with pytest.raises(RuntimeError):a(event())
    q.fail=False
    assert a(event())==([U,V],True)
    q.get_task=lambda task:(_ for _ in ()).throw(NoRows())
    a(event('task:completed'))
    assert a(event())==(None,False)
    assert a(dict(type='unknown',workspaceID='invalid'))==(None,False)
    assert a(dict(type='unknown'))==(None,False)


def test_reference_lookup_precedence_and_lifecycle_bypass():
    q=Queries();a=PrivateProjectAudience(q)
    assert a(event('unknown',issue={'project_id':None,'id':I}))==(None,False)
    assert a(event('unknown',issue_id=I))==([U,V],True)
    assert a(event('unknown',comment_id=I))==([V],True)
    assert a(event('autopilot:updated',autopilot_id=I))==([V],True)
    q.fail=True
    for kind in ['task:queued','task:coalesced','task:dispatch','task:running','task:waiting_local_directory','task:usage','task:completed','task:failed','task:cancelled']:
        assert a(event(kind))==(None,False)


def test_task_cache_bound_and_workspace_scoped_invalidation():
    q=Queries();a=PrivateProjectAudience(q)
    for i in range(4097):
        e=event();e['taskID']=f'00000000-0000-0000-0001-{i:012x}'
        assert a(e)==([U,V],True)
    assert len(a._tasks)==1
    other=event('issue:updated');other['workspaceID']=P2
    a(other)
    assert len(a._tasks)==2
    a(event('issue:updated'))
    # This event has a task hint and immediately repopulates its own entry.
    assert set(a._tasks)=={(P2,T),(W,T)}
