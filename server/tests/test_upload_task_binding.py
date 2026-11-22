import pytest
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
T='cccccccc-cccc-cccc-cccc-cccccccccccc'
S='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,agent=A,session=S,failure=False):self.agent=agent;self.session=session;self.failure=failure;self.calls=[]
    def get_task_in_workspace(self,identity,workspace):
        self.calls.append((identity,workspace))
        if self.failure:raise RuntimeError('unavailable')
        return dict(id=T,agent_id=self.agent,chat_session_id=self.session)

def resolve(q,task=T,source='task_token',bound=T,actor='agent',actor_id=A):
    from workpal_backend.files.upload_task_binding import task_upload_binding
    return task_upload_binding(q,W,task,actor_source=source,bound_task_id=bound,uploader_type=actor,uploader_id=actor_id)

def error(status,message,fn):
    from workpal_backend.files.loader import AttachmentLoadError
    with pytest.raises(AttachmentLoadError) as caught:fn()
    assert (caught.value.status,caught.value.message)==(status,message)


def test_task_token_requirement_precedes_uuid_validation():
    q=Queries()
    error(403,'task_id upload is only available from within an agent task',lambda:resolve(q,task='invalid',source=''))
    assert not q.calls


def test_form_task_uuid_must_be_valid_before_binding_match():
    q=Queries()
    error(400,'invalid task_id',lambda:resolve(q,task=' '+T+' ',bound=' '+T+' '))
    assert not q.calls

@pytest.mark.parametrize('bound',['',A,T.replace('-','')])
def test_bound_run_comparison_cannot_cross_tasks(bound):
    q=Queries()
    error(403,"task_id must match the request's task token",lambda:resolve(q,bound=bound))
    assert not q.calls


def test_bound_header_trim_and_case_fold_preserve_original_behavior():
    q=Queries()
    assert resolve(q,task=T.upper(),bound='\u00a0'+T+'\t')==dict(task_id=T,chat_session_id=S)
    assert q.calls==[(T,W)]


def test_task_query_error_denies_attachment_binding():
    error(403,'invalid task_id',lambda:resolve(Queries(failure=True)))

@pytest.mark.parametrize(('actor','actor_id','stored'),[('member',A,A),('agent',A,W),('agent',A.upper(),A)])
def test_only_producing_agent_can_bind_task(actor,actor_id,stored):
    error(403,"task_id upload requires the task's own agent",lambda:resolve(Queries(agent=stored),actor=actor,actor_id=actor_id))


def test_issue_task_cannot_be_bound_as_chat_attachment():
    error(400,'task_id upload requires a chat task',lambda:resolve(Queries(session=None)))
