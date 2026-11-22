import json
import pytest
from workpal_backend.realtime.task_projects import tasks_projects,task_projects
P='00000000-0000-0000-0000-000000000001'
P2='00000000-0000-0000-0000-000000000002'
I='00000000-0000-0000-0000-000000000003'
R='00000000-0000-0000-0000-000000000004'
class Queries:
    def __init__(self):self.calls=[];self.fail=''
    def list_issue_project_ids(self,ids):
        self.calls.append(('issue',set(ids)))
        if self.fail=='issue':raise RuntimeError('db down')
        return [(I,P2)]
    def list_autopilot_run_project_ids(self,ids):
        self.calls.append(('run',set(ids)))
        if self.fail=='run':raise RuntimeError('db down')
        return [(identity,P) for identity in ids]


def test_batch_precedence_dedup_and_cross_project_parent():
    q=Queries();tasks=[{'autopilot_run_id':R} for _ in range(200)]
    tasks += [dict(issue_id=I,chat_session_id=R,autopilot_run_id=R),
        dict(chat_session_id=R,autopilot_run_id=R),
        dict(context=json.dumps(dict(type='quick_create',project_id=P,parent_issue_id=I))),{}]
    assert tasks_projects(q,tasks)==[[P]]*200+[[P2],None,[P,P2],None]
    assert q.calls==[('issue',{I}),('run',{R})]


@pytest.mark.parametrize('raw,expected',[
 ('{"type":"quick_create","project_id":"'+P+'"}',[P]),
 ('{"TYPE":"quick_create","PROJECT_ID":"'+P+'"}',[P]),
 ('{"type":"quick_create","project_id":"'+P+'","project_id":null}',[P]),
 ('{"type":"quick_create","project_id":7,"project_id":"'+P+'"}',None),
 ('{"type":"quick_create","project_id":"'+P+'"} {}',None),
 ('{"type":"quick_create","project_id":"'+P+'","unknown":1e999}',[P]),
 ('{"type":"other","project_id":"'+P+'"}',None),
 ('null',None),('[]',None),('not json',None),('',None),
])
def test_context_decoder(raw,expected):
    q=Queries()
    assert task_projects(q,{'context':raw})==expected
    assert q.calls==[]


def test_failure_propagates_before_next_query_and_null_rows_ignored():
    for failure,count in [('issue',1),('run',2)]:
        q=Queries();q.fail=failure
        with pytest.raises(RuntimeError):tasks_projects(q,[dict(issue_id=I),dict(autopilot_run_id=R)])
        assert len(q.calls)==count
    q=Queries();q.list_issue_project_ids=lambda ids:[(I,P),(I,None)]
    assert task_projects(q,dict(issue_id=I)) is None
    assert tasks_projects(q,[])==[]
