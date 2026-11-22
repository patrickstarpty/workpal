import json
import asyncio
import pytest
from workpal_backend.realtime.protocol import project_event, ProjectionError
from workpal_backend.realtime.hub import Hub, Connection

@pytest.mark.parametrize('kind', ['invitation:accepted', 'invitation:declined', 'member:added'])
def test_conclusion_union_and_strict_projection(kind):
    member = dict(id='membership', workspace_id='source', user_id='invitee', role='member', created_at='now', name='', email='invitee@example.com', avatar_url=None)
    payload = {'member': member} if kind == 'member:added' else ({'invitation_id': 'invitation', 'member': member} if kind == 'invitation:accepted' else {'invitation_id': 'invitation', 'invitee_email': 'invitee@example.com'})
    event = dict(eventID='stable', type=kind, workspaceID='source', actorID='invitee', actorType='member', payload=payload)
    async def exercise():
        class Socket:
            def __init__(self): self.frames = []
            async def send_text(self, raw): self.frames.append(json.loads(raw))
            async def close(self, code): pass
        sockets = [Socket() for _ in range(5)]
        def denied(): raise PermissionError()
        hub = Hub()
        hub.connections = {Connection(sockets[0], lambda: None, 'source', 'owner'), Connection(sockets[1], lambda: None, 'other', 'invitee'), Connection(sockets[2], lambda: None, 'source', 'invitee'), Connection(sockets[3], lambda: None, 'other', 'stranger'), Connection(sockets[4], denied, 'other', 'invitee')}
        await hub.publish(event)
        assert [len(s.frames) for s in sockets] == [1, 1, 1, 0, 0]
    asyncio.run(exercise())
    assert project_event(event, 'source')['payload'] == payload
    payload['unknown'] = None
    with pytest.raises(ProjectionError): project_event(event, 'source')

@pytest.mark.parametrize('kind', ['invitation:accepted', 'invitation:declined', 'member:added'])
def test_conclusion_personal_fallback_excludes_bound_source_workspace(kind):
    member = dict(id='membership', workspace_id='source', user_id='invitee', role='member', created_at='now', name='', email='invitee@example.com', avatar_url=None)
    payload = {'member': member} if kind == 'member:added' else ({'invitation_id': 'invitation', 'member': member} if kind == 'invitation:accepted' else {'invitation_id': 'invitation', 'invitee_email': 'invitee@example.com'})
    event = dict(type=kind, workspaceID='source', actorID='invitee', actorType='member', payload=payload)

    async def exercise():
        class Socket:
            def __init__(self): self.frames = []
            async def send_text(self, raw): self.frames.append(json.loads(raw))
            async def close(self, code): pass
        sockets = [Socket() for _ in range(4)]
        connections = [Connection(socket, lambda: None, workspace, 'invitee')
                       for socket, workspace in zip(sockets, ['source', 'other', 'source', 'other'])]
        connections[0].rooms.remove(('workspace', 'source'))
        connections[2].rooms.remove(('user', 'invitee'))
        connections[3].rooms.remove(('user', 'invitee'))
        hub = Hub()
        hub.connections = set(connections)
        await hub.publish(event)
        assert [len(socket.frames) for socket in sockets] == [0, 1, 1, 0]
    asyncio.run(exercise())
