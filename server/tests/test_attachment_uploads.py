import asyncio
import json
import pytest
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.files.loader import AttachmentLoadError
from workpal_backend.files.upload_bindings import UploadBinding
A='aaaaaaaa-aaaa-7aaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
U='cccccccc-cccc-cccc-cccc-cccccccccccc'
C='dddddddd-dddd-dddd-dddd-dddddddddddd'
def body():return b'--b\r\nContent-Disposition: form-data; name="file"; filename="example.SVG"\r\nContent-Type: application/evil\r\n\r\n<svg/>\r\n--b--\r\n'
class Storage:
    def __init__(self,error=None):self.calls=[];self.error=error
    def upload(self,*args):
        self.calls.append(('upload',*args))
        if self.error:raise self.error
        return 'https://storage/object'
    def key_from_url(self,url):return 'object'
    def delete_keys(self,keys):self.calls.append(('delete',keys))
class Bindings:
    def __init__(self,error=None,comment=False):self.error=error;self.comment=comment;self.calls=[]
    def resolve(self,user,workspace,values,**actor):
        self.calls.append((user,workspace,values,actor))
        if self.error:raise self.error
        params=dict(workspace_id=W,uploader_type='member',uploader_id=U)
        if self.comment:params['comment_id']=C
        return UploadBinding(params, ('member', U))
class Writer:
    def __init__(self,error=None):self.error=error;self.calls=[]
    def write(self,kind,params):
        self.calls.append((kind,params.copy()))
        if self.error:raise self.error
        return dict(params,created_at=None,issue_revision=0,comment_revision=0)
    def create(self,params):return self.write('create',params)
    def create_for_live_comment(self,params):return self.write('comment',params)
class Metadata:
    def response(self,row,*,stable=False):return dict(id=row['id'],filename=row['filename'],stable=stable)

def run(storage=True,bindings=None,writer=None,user=U,workspace=W,request_error=lambda:None,**kwargs):
    from workpal_backend.files.uploads import AttachmentUploads
    storage=Storage() if storage is True else storage;bindings=bindings or Bindings();writer=writer or Writer();events=[]
    service=AttachmentUploads(storage,bindings,writer,Metadata(),on_created=lambda row,actor:events.append(row),new_id=lambda:A)
    response=asyncio.run(service.upload(body(),'multipart/form-data; boundary=b',user,workspace,request_error=request_error,**kwargs))
    return response,storage,bindings,writer,events


def test_storage_configuration_and_auth_precede_parsing():
    response,_,_,_,_=run(storage=None,user='')
    assert response.status_code==403 and b'file_upload_not_configured' in response.body
    response,storage,bindings,_,_=run(user='')
    assert response.status_code==401 and not storage.calls and not bindings.calls


def test_workspace_upload_uses_sniff_extension_key_then_persists_and_projects():
    response,storage,bindings,writer,events=run(stable=True)
    assert response.status_code==200 and json.loads(response.body)==dict(id=A,filename='example.SVG',stable=True)
    assert storage.calls==[('upload',f'workspaces/{W}/{A}.SVG',b'<svg/>','image/svg+xml','example.SVG')]
    assert writer.calls[0][1]['size_bytes']==6 and writer.calls[0][1]['url']=='https://storage/object'
    assert len(events)==1 and bindings.calls[0][:2]==(U,W)


def test_avatar_upload_ignores_associations_and_does_not_create_record():
    response,storage,bindings,writer,events=run(workspace='')
    assert json.loads(response.body)==dict(id=A,url='https://storage/object',filename='example.SVG')
    assert storage.calls[0][1]==f'users/{U}/{A}.SVG'
    assert not bindings.calls and not writer.calls and not events


def test_binding_denial_never_uploads_object():
    response,storage,_,writer,_=run(bindings=Bindings(AttachmentLoadError(403,'invalid issue_id')))
    assert response.status_code==403 and not storage.calls and not writer.calls


def test_database_failure_preserves_uploaded_object_and_returns_usable_link():
    response,storage,_,_,events=run(writer=Writer(RuntimeError('database failed')))
    assert response.status_code==200 and json.loads(response.body)['id']==''
    assert [call[0] for call in storage.calls]==['upload'] and not events


def test_comment_lock_refusal_deletes_uploaded_object():
    response,storage,_,writer,_=run(bindings=Bindings(comment=True),writer=Writer(NoRows()))
    assert response.status_code==403 and b'invalid comment_id' in response.body
    assert writer.calls[0][0]=='comment' and storage.calls[-1]==('delete',['object'])


def test_cancelled_record_write_does_not_delete_possibly_committed_object():
    response,storage,_,_,_=run(writer=Writer(asyncio.CancelledError()),request_error=lambda:asyncio.CancelledError())
    assert response.status_code==499 and response.body==b''
    assert [call[0] for call in storage.calls]==['upload']


def test_cancelled_upload_and_non_cancelled_failure_are_distinct():
    response,_,_,writer,_=run(storage=Storage(asyncio.CancelledError()),request_error=lambda:asyncio.CancelledError())
    assert response.status_code==499 and not writer.calls
    response,_,_,_,_=run(storage=Storage(OSError('storage failed')))
    assert response.status_code==500 and b'upload failed' in response.body


def test_upload_event_receives_raw_resolved_actor_without_an_extra_lookup():
    from workpal_backend.files.upload_bindings import UploadBinding
    from workpal_backend.files.uploads import AttachmentUploads
    class ActorBindings:
        def resolve(self,*args,**kwargs):
            return UploadBinding(dict(workspace_id=W,uploader_type='agent',uploader_id=U),('agent',U.upper()))
    events=[]
    service=AttachmentUploads(Storage(),ActorBindings(),Writer(),Metadata(),on_created=lambda row,actor:events.append((row['uploader_id'],actor)),new_id=lambda:A)
    response=asyncio.run(service.upload(body(),'multipart/form-data; boundary=b',U,W))
    assert response.status_code==200
    assert events==[(U,('agent',U.upper()))]
