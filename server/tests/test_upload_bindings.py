import pytest
from workpal_backend.projects.access import Hidden
from workpal_backend.files.loader import AttachmentLoadError
from workpal_backend.infrastructure.query_errors import NoRows
W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
U='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
I='cccccccc-cccc-cccc-cccc-cccccccccccc'
C='dddddddd-dddd-dddd-dddd-dddddddddddd'
P='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'
class Queries:
    def __init__(self,failure='',deleted=False,comment_workspace=W):self.failure=failure;self.deleted=deleted;self.comment_workspace=comment_workspace;self.calls=[]
    def call(self,kind,*args):
        self.calls.append((kind,*args))
        if self.failure==kind:raise RuntimeError('unavailable')
        if self.failure==kind+'-missing':raise NoRows()
    def get_member(self,workspace,user):self.call('member',workspace,user);return {}
    def get_issue_in_workspace(self,identity,workspace):self.call('issue',identity,workspace);return dict(id=I,project_id=P)
    def get_comment(self,identity):self.call('comment',identity);return dict(id=C,workspace_id=self.comment_workspace,issue_id=I,deleted_at='now' if self.deleted else None)
    def issue_project(self,identity):self.call('project',identity);return P

def service(q,hidden=None):
    from workpal_backend.files.upload_bindings import UploadBindings
    return UploadBindings(q,hidden_projects=hidden or (lambda workspace:Hidden()))

def error(status,message,fn):
    with pytest.raises(AttachmentLoadError) as caught:fn()
    assert (caught.value.status,caught.value.message)==(status,message)


def test_membership_precedes_upload_association_validation():
    q=Queries(failure='member')
    error(403,'not a member of this workspace',lambda:service(q).resolve(U,W,{'issue_id':'invalid'}))
    assert q.calls==[('member',W,U)]


def test_valid_issue_then_comment_are_bound_in_form_order():
    q=Queries()
    result=service(q).resolve(U,W,{'issue_id':I,'comment_id':C})
    assert result==dict(workspace_id=W,uploader_type='member',uploader_id=U,issue_id=I,comment_id=C)
    assert q.calls==[('member',W,U),('issue',I,W),('comment',C)]

@pytest.mark.parametrize(('field','status','message'),[('issue_id',400,'invalid issue_id'),('comment_id',400,'invalid comment_id')])
def test_invalid_association_uuid(field,status,message):
    error(status,message,lambda:service(Queries()).resolve(U,W,{field:'invalid'}))

@pytest.mark.parametrize('failure',['issue','issue-missing'])
def test_issue_lookup_errors_deny(failure):
    error(403,'invalid issue_id',lambda:service(Queries(failure=failure)).resolve(U,W,{'issue_id':I}))

@pytest.mark.parametrize(('deleted','workspace'),[(True,W),(False,U)])
def test_deleted_or_cross_workspace_comment_cannot_receive_upload(deleted,workspace):
    error(403,'invalid comment_id',lambda:service(Queries(deleted=deleted,comment_workspace=workspace)).resolve(U,W,{'comment_id':C}))

@pytest.mark.parametrize('field',['issue_id','comment_id'])
def test_private_project_is_indistinguishable_from_invalid_association(field):
    hidden=Hidden();hidden.add([P])
    error(403,'invalid '+field,lambda:service(Queries(),lambda workspace:hidden).resolve(U,W,{field:I if field=='issue_id' else C}))


def test_missing_comment_parent_is_not_hidden():
    hidden=Hidden();hidden.add([P]);q=Queries(failure='project-missing')
    assert service(q,lambda workspace:hidden).resolve(U,W,{'comment_id':C})['comment_id']==C


def test_resolved_actor_is_preserved_outside_sql_values():
    q=Queries();result=service(q).resolve(U,W,{},actor_source='task_token',agent_id=P.upper())
    assert result.uploader==('agent',P.upper())
    assert result==dict(workspace_id=W,uploader_type='agent',uploader_id=P)
    assert q.calls==[('member',W,U)]
