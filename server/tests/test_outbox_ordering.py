"""FIFO protects newer snapshots from stale retry replay."""
import pytest
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.outbox import append_event, claim_batch, ack, retry


def append(session, event_id):
    return append_event(session, dict(eventID=event_id, type='workspace:updated',
                                     workspaceID='ws', payload={'name': event_id}))


@pytest.mark.parametrize('limit', [1, 100])
def test_fifo_retry_reclaim_and_reopen(settings, limit):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        append(s, 'z-old')
        append(s, 'a-new')
    with db.transaction() as s:
        first, = claim_batch(s, now=10, limit=limit, lease_seconds=5)
        assert first['event_id'] == 'z-old'
    with db.transaction() as s:
        assert claim_batch(s, now=11, limit=limit) == []
        assert retry(s, 'z-old', first['claim_token'], 'outage', now=11, delay_seconds=20)
    db.close()
    db = Database(settings)
    with db.transaction() as s:
        assert claim_batch(s, now=30, limit=limit) == []
        second, = claim_batch(s, now=31, limit=limit, lease_seconds=5)
        assert second['event_id'] == 'z-old'
    with db.transaction() as s:
        reclaimed, = claim_batch(s, now=36, limit=limit)
        assert reclaimed['event_id'] == 'z-old'
        assert not ack(s, 'z-old', second['claim_token'], now=36)
        assert ack(s, 'z-old', reclaimed['claim_token'], now=36)
    with db.transaction() as s:
        newer, = claim_batch(s, now=37, limit=limit)
        assert newer['event_id'] == 'a-new'
    db.close()


def test_rollback_leaves_no_fifo_barrier(settings):
    migrate(settings)
    db = Database(settings)
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            append(s, 'z-rolled-back')
            raise RuntimeError('rollback')
    with db.transaction() as s:
        append(s, 'a-committed')
    with db.transaction() as s:
        claimed, = claim_batch(s, now=1)
        assert claimed['event_id'] == 'a-committed'
    db.close()
