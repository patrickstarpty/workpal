import pytest
from workpal_backend.projects.access import Hidden,for_member,for_principals,run_principals,is_manager_role,valid_visibility,NoRows

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
P,P2,W=uid(101),uid(102),uid(200)
class Queries:
    def __init__(self):self.calls=[];self.private=[P,P2];self.failure=''
    def call(self,name,user=None):
        self.calls.append((name,user))
        if name==self.failure:raise RuntimeError('database down')
    def list_private_project_ids(self,w):self.call('private');return self.private
    def get_member(self,w,u):
        self.call('member',u)
        if u==uid(4):raise NoRows()
        return {'role':{uid(5):'admin',uid(6):'owner'}.get(u,'member')}
    def list_hidden_project_ids(self,w,u):
        self.call('hidden',u)
        return [] if u==uid(1) else [P2] if u==uid(2) else [P,P2]

@pytest.mark.parametrize('principals,hidden',[
 ([uid(1)],[]),([uid(2)],[P2]),([uid(5)],[P,P2]),([uid(6)],[P,P2]),
 ([uid(1),uid(2)],[P2]),([uid(2),uid(3)],[P2,P]),([uid(1),uid(4)],[P,P2]),
 ([],[P,P2]),([None,uid(2)],[P2]),
])
def test_principals_bound_access_without_role_bypass(principals,hidden):
    q=Queries();h=for_principals(q,W,*principals)
    assert h.ids()==hidden and h.param()==(hidden or None)
    assert h.can_see_project(None)
    assert h.can_see_projects([P,P2])==(not hidden)
    assert h.empty()==(not hidden)


def test_dedup_invalid_and_error_order():
    q=Queries();h=for_principals(q,W,uid(2),None,uid(2).upper())
    assert h.ids()==[P2] and q.calls==[('private',None),('member',uid(2)),('hidden',uid(2))]
    q=Queries();q.private=[];q.failure='member'
    assert for_principals(q,W,uid(4)).empty() and len(q.calls)==1
    for stage in ['private','member','hidden']:
        q=Queries();q.failure=stage
        with pytest.raises(RuntimeError):for_principals(q,W,uid(1))


def test_member_has_no_extra_membership_query_and_hidden_set_order():
    q=Queries();assert for_member(q,W,uid(1)).param() is None
    assert q.calls==[('hidden',uid(1))]
    h=Hidden();h.add([None,P2,P,P2])
    assert h.ids()==[P2,P] and not h.can_see_project(P2)
    assert Hidden().ids()==[] and Hidden().param() is None


def test_run_principal_fallback_and_validation_helpers():
    assert run_principals({'originator_user_id':uid(1),'accountable_user_id':uid(2)},uid(3))==[uid(1),uid(3)]
    assert run_principals({'accountable_user_id':uid(2)},uid(2))==[uid(2),uid(2)]
    assert run_principals({},None)==[None,None]
    assert [is_manager_role(r) for r in ['owner','admin','member','Owner','']]==[True,True,False,False,False]
    assert [valid_visibility(v) for v in ['workspace','private','public','PRIVATE','']]==[True,True,False,False,False]
