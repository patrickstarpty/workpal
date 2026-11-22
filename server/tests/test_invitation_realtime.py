import json
import pytest
from workpal_backend.realtime.protocol import project_event, ProjectionError


def event(kind='invitation:revoked', recipient='recipient'):
    return dict(eventID='stable', type=kind, workspaceID='source', actorID='owner', actorType='member',
                payload=dict(invitation_id='invitation', invitee_email='target@example.com', invitee_user_id=recipient))


def test_revocation_projection():
    e = event()
    assert project_event(e, 'source') == dict(type=e['type'], payload=e['payload'], actor_id='owner', actor_type='member')


@pytest.mark.parametrize('kind', ['chat:updated', 'task:updated'])
def test_unimplemented_public_types_and_ownerless_chat_closed(kind):
    if kind.startswith('chat:'):
        from workpal_backend.realtime.protocol import resolve_audience
        assert resolve_audience(event(kind)) is None
    else:
        with pytest.raises(ProjectionError): project_event(event(kind), 'source')


def test_created_audience_and_strict_payload():
    from workpal_backend.realtime.protocol import resolve_audience
    e = event('invitation:created')
    row = dict(id='invitation', workspace_id='source', inviter_id='owner', invitee_email='target@example.com', invitee_user_id='recipient', role='member', status='pending', created_at='now', updated_at='now', expires_at='later')
    e['payload'] = {'invitation': row}
    assert resolve_audience(e) == ('user', 'recipient')
    e['payload']['workspace_name'] = 'Source workspace'
    assert project_event(e, 'source')['payload'] == e['payload']
    e['payload']['workspace_name'] = {'private': 'unexpected'}
    with pytest.raises(ProjectionError): resolve_audience(e)
    e['payload']['workspace_name'] = 'Source workspace'
    e['payload']['private'] = 'unexpected'
    with pytest.raises(ProjectionError): resolve_audience(e)
    del e['payload']['private']
    row['invitee_user_id'] = None
    assert resolve_audience(e) is None
    row['workspace_id'] = 'foreign'
    with pytest.raises(ProjectionError): resolve_audience(e)
    row['workspace_id'] = 'source'
    row['private'] = 'secret'
    with pytest.raises(ProjectionError): resolve_audience(e)


def test_personal_fanout_cross_workspace_and_revalidation():
    import asyncio
    from workpal_backend.realtime.hub import Hub, Connection
    async def exercise():
        class Socket:
            def __init__(self): self.frames = []
            async def send_text(self, raw): self.frames.append(json.loads(raw))
            async def close(self, code): pass
        good, other, denied = Socket(), Socket(), Socket()
        def reject(): raise PermissionError()
        hub = Hub()
        hub.connections = {Connection(good, lambda: None, 'different', 'recipient'), Connection(other, lambda: None, 'source', 'owner'), Connection(denied, reject, 'different', 'recipient')}
        await hub.publish(event())
        assert len(good.frames) == 1
        assert not other.frames and not denied.frames
        assert any(c.closed for c in hub.connections)
        await hub.publish(event(recipient=None))
        assert len(good.frames) == 1
    asyncio.run(exercise())
