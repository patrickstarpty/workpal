import asyncio
import pytest
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.files.loader import AttachmentLoadError

class Dependencies:
    def __init__(self,**values):
        self.row=dict(id='attachment',workspace_id='workspace',uploader_type='member',uploader_id='user',url='https://storage/object',**values)
        self.calls=[];self.failure='';self.changed=True
    def for_request(self,*args):
        self.calls.append(('load',*args))
        if self.failure=='load':raise AttachmentLoadError(404,'attachment not found')
        return self.row
    def with_owner_lock(self,attachment,write):
        self.calls.append(('lock',attachment))
        if self.failure=='missing':raise NoRows()
        if self.failure=='cancel':raise asyncio.CancelledError()
        if self.failure=='write':raise RuntimeError('failed')
        result=write(self);self.calls.append(('commit',));return result
    def delete_attachment(self,identity,workspace):
        self.calls.append(('delete',identity,workspace));return dict(changed=self.changed,issue_revision=0)
    def deleted(self,attachment,result):self.calls.append(('event',attachment,result))
    def key_from_url(self,url):self.calls.append(('key',url));return 'object'
    def delete(self,key):
        self.calls.append(('storage',key))
        if self.failure=='storage':raise RuntimeError('storage failed')

def remove(d,**kwargs):
    from workpal_backend.files.deletion import AttachmentDeletion
    return asyncio.run(AttachmentDeletion(d,d,d,d).delete('attachment',kwargs.pop('user','user'),kwargs.pop('workspace','workspace'),**kwargs))

def test_delete_commits_then_events_then_storage_and_returns_empty_204():
    d=Dependencies();response=remove(d)
    assert response.status_code==204 and response.body==b''
    assert [entry[0] for entry in d.calls]==['load','lock','delete','commit','event','key','storage']

@pytest.mark.parametrize('user,workspace,status',[('','','400'),('','workspace','401')])
def test_workspace_then_auth_validation_precedes_loading(user,workspace,status):
    d=Dependencies();response=remove(d,user=user,workspace=workspace)
    assert response.status_code==int(status) and d.calls==[]

def test_historical_source_attachment_hidden_even_from_admin():
    d=Dependencies(source_context_id='source');response=remove(d,member=dict(role='admin'))
    assert response.status_code==404 and [entry[0] for entry in d.calls]==['load']

@pytest.mark.parametrize('kind,user,member,allowed',[
    ('agent','user',None,False),('member','USER',None,False),('member','other',dict(role='owner'),True),
    ('member','other',dict(role='admin'),True),('member','other',dict(role='Admin'),False),
    ('member','user',None,True)])
def test_only_exact_member_uploader_or_context_admin_can_delete(kind,user,member,allowed):
    d=Dependencies();d.row['uploader_type']=kind
    response=remove(d,user=user,member=member)
    assert response.status_code==(204 if allowed else 403)
    if not allowed:assert len(d.calls)==1

@pytest.mark.parametrize('failure,status',[('load',404),('missing',404),('cancel',500),('write',500),('storage',204)])
def test_write_failures_never_publish_or_delete_storage_but_storage_failure_is_best_effort(failure,status):
    d=Dependencies();d.failure=failure;response=remove(d)
    assert response.status_code==status
    if status!=204:assert not any(entry[0] in ('event','storage') for entry in d.calls)
