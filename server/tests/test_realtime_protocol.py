import copy
import json
from pathlib import Path
import pytest
from workpal_backend.realtime.protocol import parse_frame, project_event, ProjectionError

FIX = json.loads((Path(__file__).parents[1] / 'contracts/batches/realtime.json').read_text())

def test_frames():
    for name in ('ping', 'subscribe', 'unsubscribe'):
        result = parse_frame(json.dumps(FIX['fixtures'][name]), 'workspace-1', 'user-1')
        assert result.reply == FIX['fixtures'][{'ping':'pong','subscribe':'subscribe_ack','unsubscribe':'unsubscribe_ack'}[name]]

@pytest.mark.parametrize('raw', ['bad', '[]', 'null', '{"type":7}', '{"type":"unknown"}'])
def test_ignored(raw):
    assert parse_frame(raw, 'w', 'u').reply is None

@pytest.mark.parametrize('scope,id,error', [('workspace','foreign','forbidden'),('user','foreign','forbidden'),('task','x','forbidden'),('chat','x','forbidden'),('private','x','unknown_scope')])
def test_denied(scope,id,error):
    result = parse_frame(json.dumps(dict(type='subscribe',payload=dict(scope=scope,id=id))), 'w','u')
    assert result.reply['payload']['error'] == error
    assert result.action is None

def test_malformed_and_limit():
    assert parse_frame('{"type":"unsubscribe"}', 'w','u').reply == FIX['fixtures']['unsubscribe_error']
    assert parse_frame('x'*65537, 'w','u').close_code == 1009
    assert parse_frame('x'*65536, 'w','u').close_code is None

def test_projection():
    assert project_event(FIX['internal_event'], 'workspace-1') == FIX['fixtures']['workspace_updated']

@pytest.mark.parametrize('change', [dict(type='unknown'),dict(workspaceID='foreign'),dict(actorID=3),dict(chatSessionID='secret'),dict(memberPrivateUserID='secret')])
def test_reject_envelope(change):
    event = copy.deepcopy(FIX['internal_event']); event.update(change)
    with pytest.raises(ProjectionError): project_event(event,'workspace-1')

def test_reject_payload():
    event = copy.deepcopy(FIX['internal_event']); event['payload']['secret']='private'
    with pytest.raises(ProjectionError): project_event(event,'workspace-1')
    event = copy.deepcopy(FIX['internal_event']); event['payload']['workspace']['id']='foreign'
    with pytest.raises(ProjectionError): project_event(event,'workspace-1')
