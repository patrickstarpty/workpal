import json
import asyncio
from copy import deepcopy

import pytest

from workpal_backend.realtime.hub import Connection, Hub
from workpal_backend.realtime.protocol import ProjectionError, project_event, resolve_audience


def event():
    return dict(eventID='stable', type='member:updated', workspaceID='source',
                actorID='owner', actorType='member', payload={'member': dict(
                    id='membership', workspace_id='source', user_id='recipient',
                    role='admin', created_at='now', name='', email='a@example.com', avatar_url=None)})


@pytest.mark.parametrize('avatar', [None, '/avatar.png'])
def test_exact_projection_and_workspace_tuple(avatar):
    source = event()
    source['payload']['member']['avatar_url'] = avatar
    frame = project_event(source, 'source')
    assert frame == dict(type='member:updated', payload=source['payload'], actor_id='owner', actor_type='member')
    assert resolve_audience(source) == ('workspace', 'source')
    source['payload']['member']['name'] = 'changed'
    assert frame['payload']['member']['name'] == ''


@pytest.mark.parametrize('mutation', [
    lambda e: e.update(workspaceID='foreign'),
    lambda e: e.update(actorID=None),
    lambda e: e.update(userID='private'),
    lambda e: e.update(taskID='private'),
    lambda e: e.update(payload=None),
    lambda e: e['payload'].update(extra=True),
    lambda e: e['payload']['member'].update(workspace_id='foreign'),
    lambda e: e['payload']['member'].update(pinned_at=None),
    lambda e: e['payload']['member'].update(role='invalid'),
    lambda e: e['payload']['member'].update(avatar_url=1),
    lambda e: e['payload']['member'].update(name=None),
    lambda e: e['payload']['member'].pop('avatar_url'),
    lambda e: e['payload'].update(member=[]),
])
def test_reject_malformed_foreign_and_private(mutation):
    source = deepcopy(event())
    mutation(source)
    with pytest.raises(ProjectionError):
        project_event(source, 'source')


def test_existing_hub_workspace_only_and_session_boundary():
    async def exercise():
        class Socket:
            def __init__(self): self.frames, self.closed = [], False
            async def send_text(self, raw): self.frames.append(json.loads(raw))
            async def close(self, code): self.closed = True
        sockets = [Socket() for _ in range(5)]
        checks = []
        def check(index):
            checks.append(index)
            if index == 4: raise PermissionError('expired session')
        connections = [Connection(s, lambda i=i: check(i), ws, user)
                       for i, (s, ws, user) in enumerate(zip(sockets,
                           ['source', 'source', 'other', 'other', 'source'],
                           ['owner', 'recipient', 'recipient', 'stranger', 'expired']))]
        hub = Hub()
        hub.connections = set(connections)
        await hub.publish(event())
        assert [len(s.frames) for s in sockets] == [1, 1, 0, 0, 0]
        assert set(checks) == {0, 1, 4}
        assert sockets[4].closed
    asyncio.run(exercise())
