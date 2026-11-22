import asyncio
from workpal_backend.projects.access import Hidden
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';T='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
class Queries:
    def __init__(self):self.calls=[]
    def get_task(self,identity):self.calls.append(('source',identity));return dict(id=T)

def service(q,workspace='workspace',user='user'):
    from workpal_backend.files.mutations import AttachmentMutations
    def forbidden(*args):raise AssertionError('unexpected transaction or event')
    return AttachmentMutations(q,forbidden,forbidden,None,None,forbidden,
        user_id=user,workspace_id=workspace,hidden_projects=lambda ws:Hidden(),
        actor_source='task_token',agent_id=A,task_id=T)


def test_upload_captures_request_actor_before_storage_configuration_rejection():
    q=Queries();response=asyncio.run(service(q).upload(b'invalid','invalid'))
    assert response.status_code==403 and b'file_upload_not_configured' in response.body
    assert q.calls==[('source',T)]


def test_delete_captures_request_actor_before_workspace_validation():
    q=Queries();response=asyncio.run(service(q,workspace='',user='').delete('invalid'))
    assert response.status_code==400 and b'workspace_id is required' in response.body
    assert q.calls==[('source',T)]
