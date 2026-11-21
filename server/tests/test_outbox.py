import pytest
from sqlalchemy import select
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.outbox import append_event, outbox, claim_batch, ack, retry


def test_atomic_and_fenced(settings):
    migrate(settings)
    db = Database(settings)
    event = {'type': 'issue:created', 'workspaceID': 'ws', 'payload': {'id': 'one'}}
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            append_event(s, event)
            raise RuntimeError()
    with db.transaction() as s:
        assert not s.execute(select(outbox)).all()
        event_id = append_event(s, event)
    with db.transaction() as s:
        first = claim_batch(s, now=10, lease_seconds=5)[0]
    with db.transaction() as s:
        assert claim_batch(s, now=11) == []
        second = claim_batch(s, now=16)[0]
        assert not ack(s, event_id, first['claim_token'], now=16)
        assert not retry(s, event_id, first['claim_token'], 'old', now=16)
        assert retry(s, event_id, second['claim_token'], 'offline', now=16, delay_seconds=2)
    db.close()
    db = Database(settings)
    with db.transaction() as s:
        assert claim_batch(s, now=17) == []
        third = claim_batch(s, now=18)[0]
        assert third['event_id'] == event_id
        assert ack(s, event_id, third['claim_token'], now=18)
    db.close()


def test_validation_and_no_commit(settings):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        s.execute(text('CREATE TABLE mutation (id INTEGER)'))
    for payload in ({'bad': object()}, {'bad': float('nan')}):
        with pytest.raises((TypeError, ValueError)):
            with db.transaction() as s:
                s.execute(text('INSERT INTO mutation VALUES (1)'))
                append_event(s, dict(type='issue:created', workspaceID='ws', payload=payload))
    with db.transaction() as s:
        assert s.scalar(text('SELECT count(*) FROM mutation')) == 0
        event_id = append_event(s, dict(type='issue:created', workspaceID='ws', payload={}))
        assert s.in_transaction()
        s.execute(text('INSERT INTO mutation VALUES (1)'))
    with pytest.raises(IntegrityError):
        with db.transaction() as s:
            append_event(s, dict(eventID=event_id, type='issue:created', workspaceID='ws', payload={'different': True}))
    db.close()


def test_competing_connections(settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        append_event(s, dict(type='issue:created', workspaceID='ws', payload={}))
    barrier = Barrier(2)
    def claim():
        barrier.wait()
        with db.transaction() as s:
            return claim_batch(s, now=1)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(map(len, results)) == [0, 1]
    db.close()
