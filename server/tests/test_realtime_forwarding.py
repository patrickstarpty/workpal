"""Non-personal Go listener forwarding before transport/database integration."""
import json
import pytest
from workpal_backend.realtime.forwarding import forward_workspace_event, project_outbound

class Broadcaster:
    def __init__(self): self.calls=[]
    def broadcast_to_scope(self,scope,identity,data): self.calls.append((scope,identity,json.loads(data)))
    def broadcast_to_workspace(self,identity,data): self.broadcast_to_scope('workspace',identity,data)
    def broadcast(self,data): self.broadcast_to_scope('global','',data)

@pytest.mark.parametrize('kind,chat,owner,member,expected',[
    ('chat:new','','owner','other',('workspace_member','w:owner')),
    ('chat:future','','','',None),
    ('task:message','chat','owner','',('workspace_member','w:owner')),
    ('task:message','','owner','',('workspace','w')),
    ('task:failed','chat','owner','',('workspace','w')),
    ('pin:created','','','',None),
    ('pin:created','','','member',('workspace_member','w:member')),
    ('arbitrary','','','member',('workspace_member','w:member')),
    ('inbox:new','','','member',None),
])
def test_private_routing(kind,chat,owner,member,expected):
    b=Broadcaster()
    forward_workspace_event(dict(type=kind,workspaceID='w',chatSessionID=chat,
        chatSessionOwnerID=owner,memberPrivateUserID=member,payload={}),b)
    assert [(scope,identity) for scope,identity,_ in b.calls]==([] if expected is None else [expected])


def test_projection_preserves_producer_payload_and_nested_identity():
    payload={'prev_description':'secret','prev_title':'old','issue':{'title':'new'}}
    result=project_outbound('issue:updated',payload)
    assert result=={'issue':{'title':'new'}} and result['issue'] is payload['issue']
    assert payload['prev_description']=='secret'
    assert project_outbound('unknown',payload) is payload
    assert project_outbound('task:failed',{'error':'secret','task_id':'t'})=={'task_id':'t'}
    assert project_outbound('task:failed',['error'])==['error']


def test_audience_failure_drops_and_private_empty_never_falls_back():
    b=Broadcaster();event=dict(type='issue:updated',workspaceID='w',payload={})
    def failed(event): raise RuntimeError('unavailable')
    forward_workspace_event(event,b,audience=failed)
    forward_workspace_event(event,b,audience=lambda event:([],True))
    assert b.calls==[]
    forward_workspace_event(event,b,audience=lambda event:(['u','u','v'],True))
    assert [(s,i) for s,i,_ in b.calls]==[('workspace_member','w:u'),('workspace_member','w:u'),('workspace_member','w:v')]


def test_bad_json_not_sent_or_resolved_and_daemon_only_global():
    b=Broadcaster()
    def forbidden(event): pytest.fail('audience must not be resolved')
    forward_workspace_event(dict(type='issue:updated',workspaceID='w',payload=float('nan')),b,audience=forbidden)
    forward_workspace_event(dict(type='unknown'),b)
    forward_workspace_event(dict(type='chat:new',chatSessionOwnerID='u'),b)
    assert b.calls==[]
    forward_workspace_event(dict(type='daemon:future',payload={'html':'<>&'}),b)
    assert b.calls==[('global','',dict(type='daemon:future',payload={'html':'<>&'},actor_id='',actor_type=''))]


def test_nil_private_audience_drops_without_iteration_error():
    b=Broadcaster()
    forward_workspace_event(dict(type='unknown',workspaceID='w'),b,audience=lambda event:(None,True))
    assert b.calls==[]
