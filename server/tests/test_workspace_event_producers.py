"""Source: handler/workspace.go:529; caller-owned atomic producer."""
import json
from uuid import uuid4
import pytest
from sqlalchemy import select, update
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.auth.service import get_or_create_development_user
from workpal_backend.workspaces import service
from workpal_backend.workspaces.models import members

@pytest.fixture
def workspace(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        uid = get_or_create_development_user(s, 'dev@workpal.local')['id']
        ws = service.create_workspace(s, uid, 'Original', 'producer-test')
    yield db, {'identity_kind':'session', 'user_id':uid}, ws
    db.close()

def rows(db):
    with db.transaction() as s:
        return [dict(r) for r in s.execute(select(outbox)).mappings()]

def test_commit_repeated_and_audit(workspace):
    db, actor, ws = workspace
    with db.transaction() as s:
        service.set_pinned(s, actor, ws['id'], True)
        service.get_workspace(s, actor, ws['id'])
        service.list_members(s, actor, ws['id'])
        service.list_workspaces(s, actor['user_id'])
    assert rows(db) == []
    for body in ({'name':'Changed'}, {'name':'Changed'}, {}):
        with db.transaction() as s:
            result = service.update_workspace(s, actor, ws['id'], body)
        event = json.loads(rows(db)[-1]['envelope'])
        assert event == dict(eventID=event['eventID'], type='workspace:updated', workspaceID=ws['id'], actorType='member', actorID=actor['user_id'], payload={'workspace':result})
    assert len({r['event_id'] for r in rows(db)}) == 3

@pytest.mark.parametrize('injected', [False, True])
def test_atomic_rollback(workspace, monkeypatch, injected):
    db, actor, ws = workspace
    if injected:
        def fail(*args): raise RuntimeError('append failed')
        monkeypatch.setattr(service, 'append_event', fail)
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            service.update_workspace(s, actor, ws['id'], {'name':'Lost'})
            raise RuntimeError('caller rollback')
    with db.transaction() as s:
        assert service.get_workspace(s, actor, ws['id']) == ws
    assert rows(db) == []

def test_unauthorized(workspace):
    db, actor, ws = workspace
    with db.transaction() as s:
        s.execute(update(members).values(role='member'))
    for principal in (actor, dict(actor, user_id=str(uuid4()))):
        with pytest.raises(service.WorkspaceAccessError):
            with db.transaction() as s:
                service.update_workspace(s, principal, ws['id'], {'name':'Denied'})
    assert rows(db) == []

def test_outage_recovery(workspace, settings):
    db, actor, ws = workspace
    settings.redis_key_prefix = 'test:workspace-producer:' + uuid4().hex + ':'
    with db.transaction() as s:
        result = service.update_workspace(s, actor, ws['id'], {'description':'Durable'})
    delivery = OutboxDelivery(settings)
    try:
        assert delivery.dispatch(db, retry_delay=0) == 0
    finally: delivery.close()
    row = rows(db)[0]
    assert row['state'] == 'pending'
    with db.transaction() as s:
        assert service.get_workspace(s, actor, ws['id']) == result
    settings.redis_url = 'redis://127.0.0.1:26379'
    delivery = OutboxDelivery(settings)
    try:
        assert delivery.dispatch(db) == 1
        entries = delivery.client.xread({delivery.channel:'0-0'})[0][1]
        assert len(entries) == 1
        assert json.loads(entries[0][1][b'envelope']) == json.loads(row['envelope'])
        assert rows(db)[0]['state'] == 'delivered'
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
