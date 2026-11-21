"""Operation-specific revoke persistence and real Redis restart recovery evidence."""
import json
from uuid import uuid4

from sqlalchemy import select, literal_column

from test_workspace_invitations import context
from workpal_backend.infrastructure.database import Database
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces import invitations


def test_revoke_reopen_outage_fifo(context, settings):
    db, owner, target, _, wid = context
    settings.redis_key_prefix = 'test:revoke-recovery:' + uuid4().hex + ':'
    # Port 1 is the fixture's real unavailable endpoint; never stop shared Redis.
    settings.redis_url = 'redis://127.0.0.1:1'
    with db.transaction() as session:
        row = invitations.create_invitation(session, owner, wid, 'target@example.com')
        assert row['invitee_user_id'] == target
    with db.transaction() as session:
        invitations.revoke_invitation(session, owner, wid, row['id'])
    def records(database):
        with database.transaction() as session:
            return list(session.execute(select(outbox).order_by(literal_column('outbox.rowid'))).mappings())
    expected = [record['envelope'] for record in records(db)]
    events = [json.loads(raw) for raw in expected]
    assert [event['type'] for event in events] == ['invitation:created', 'invitation:revoked']
    assert events[1]['payload'] == dict(invitation_id=row['id'], invitee_email='target@example.com', invitee_user_id=target)
    assert events[1]['workspaceID'] == wid
    assert events[1]['actorID'] == owner['user_id']
    assert events[1]['actorType'] == 'member'
    assert len({event['eventID'] for event in events}) == 2
    failed = OutboxDelivery(settings)
    try:
        assert failed.dispatch(db, retry_delay=0) == 0
        persisted = records(db)
        assert [record['state'] for record in persisted] == ['pending', 'pending']
        assert persisted[0]['last_error'] == 'Redis publication failed'
        assert [record['envelope'] for record in persisted] == expected
    finally:
        failed.close()
        db.close()
    reopened = Database(settings)
    settings.redis_url = 'redis://127.0.0.1:26379'
    delivery = OutboxDelivery(settings)
    try:
        assert delivery.client.exists(delivery.channel) == 0
        with reopened.transaction() as session:
            assert session.execute(select(invitations.invitations).where(invitations.invitations.c.id == row['id'])).first() is None
        assert [record['envelope'] for record in records(reopened)] == expected
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 0
        assert delivery.dispatch(reopened) == 0
        received = [fields[b'envelope'].decode() for _, fields in delivery.client.xrange(delivery.channel)]
        assert received == expected
        assert [json.loads(raw)['eventID'] for raw in received] == [event['eventID'] for event in events]
        assert [record['state'] for record in records(reopened)] == ['delivered', 'delivered']
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
        reopened.close()
