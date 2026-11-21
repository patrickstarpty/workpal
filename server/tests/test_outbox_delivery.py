import json
import time
from uuid import uuid4
import pytest
from redis import Redis
from sqlalchemy import select
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.outbox import append_event, outbox, claim_batch, ack
from workpal_backend.infrastructure.delivery import OutboxDelivery


def test_outage_recovery_rollback_restart(settings):
    settings.redis_key_prefix = 'test:delivery:' + uuid4().hex + ':'
    migrate(settings)
    db = Database(settings)
    event = dict(type='issue:created', workspaceID='ws', payload={'id': 'one'})
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            append_event(s, event)
            raise RuntimeError('rollback')
    failed = OutboxDelivery(settings)
    try:
        assert failed.dispatch(db) == 0
        with db.transaction() as s: event_id = append_event(s, event)
        start = time.monotonic()
        assert failed.dispatch(db, retry_delay=0) == 0
        assert time.monotonic() - start < 2
        with db.transaction() as s:
            row = s.execute(select(outbox)).mappings().one()
            assert row['state'] == 'pending'
            old = claim_batch(s, now=time.time(), lease_seconds=1)[0]
    finally:
        failed.close()
        db.close()
    time.sleep(1.05)  # Simulate restart after the durable lease expires.
    settings.redis_url = 'redis://127.0.0.1:26379'
    subscriber = Redis.from_url(settings.redis_url, socket_timeout=2)
    delivery = OutboxDelivery(settings)
    db = Database(settings)
    try:
        # Dispatch with no consumer, then recover using a newly opened client.
        assert delivery.dispatch(db) == 1
        subscriber.close()
        subscriber = Redis.from_url(settings.redis_url, socket_timeout=2)
        messages = subscriber.xread({delivery.channel: '0-0'})
        assert messages, 'offline publication must remain readable'
        stream_id, fields = messages[0][1][0]
        assert json.loads(fields[b'envelope']) == dict(event, eventID=event_id)
        subscriber.xgroup_create(delivery.channel, 'recovery', id='0-0')
        first = subscriber.xreadgroup('recovery', 'before', {delivery.channel: '>'})
        assert first[0][1][0][0] == stream_id
        subscriber.close()
        subscriber = Redis.from_url(settings.redis_url, socket_timeout=2)
        recovered = subscriber.xclaim(delivery.channel, 'recovery', 'after', 0, [stream_id])
        assert json.loads(recovered[0][1][b'envelope'])['eventID'] == event_id
        assert subscriber.xreadgroup('recovery', 'after', {delivery.channel: '0-0'})[0][1]
        assert subscriber.ttl(delivery.channel) == -1
        assert delivery.dispatch(db) == 0
        with db.transaction() as s:
            assert not ack(s, event_id, old['claim_token'])
            assert s.execute(select(outbox.c.state)).scalar_one() == 'delivered'
    finally:
        delivery.close()
        subscriber.delete(delivery.channel)
        subscriber.close()
        db.close()


def test_network_outside_transaction_and_stale_fencing(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        append_event(s, dict(type='issue:created', workspaceID='ws', payload={}))
    delivery = OutboxDelivery(settings)
    class ReplacingPublisher:
        def xadd(self, channel, fields):
            # Independent writer succeeds only after dispatch's claim committed.
            with db.transaction() as s:
                replacement = claim_batch(s, now=time.time()+60)[0]
                assert replacement['claim_token']
            return 1
        def close(self): pass
    delivery.client.close()
    delivery.client = ReplacingPublisher()
    try:
        assert delivery.dispatch(db) == 0
        with db.transaction() as s:
            assert s.execute(select(outbox.c.state)).scalar_one() == 'claimed'
    finally:
        delivery.close()
        db.close()


def test_worker_wiring_and_client_shutdown(settings, tmp_path, monkeypatch):
    import signal
    from workpal_backend import worker
    settings.upload_dir = tmp_path / 'uploads'
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        event_id = append_event(s, dict(type='issue:created', workspaceID='ws', payload={}))
        claim_batch(s, now=1, lease_seconds=1)
    db.close()
    clients = []
    original = worker.OutboxDelivery
    class Publisher:
        closed = False
        def xadd(self, channel, fields):
            assert json.loads(fields['envelope'])['eventID'] == event_id
            signal.raise_signal(signal.SIGTERM)
            return 0
        def close(self): self.closed = True
    def create(config):
        delivery = original(config)
        delivery.close()
        delivery.client = Publisher()
        clients.append(delivery.client)
        return delivery
    monkeypatch.setattr(worker, 'OutboxDelivery', create)
    worker.run(settings)
    assert clients[0].closed
    db = Database(settings)
    try:
        with db.transaction() as s:
            assert s.execute(select(outbox.c.state)).scalar_one() == 'delivered'
    finally: db.close()


def test_duplicate_attempt_after_ack_failure_keeps_event_id(settings, monkeypatch):
    import workpal_backend.infrastructure.delivery as module
    from sqlalchemy import update
    settings.redis_key_prefix = 'test:delivery:' + uuid4().hex + ':'
    settings.redis_url = 'redis://127.0.0.1:26379'
    migrate(settings)
    db = Database(settings)
    delivery = OutboxDelivery(settings)
    try:
        with db.transaction() as s:
            event_id = append_event(s, dict(type='issue:created', workspaceID='ws', payload={}))
        def broken_ack(*args):
            raise RuntimeError('crash after Redis acceptance')
        with monkeypatch.context() as patch:
            patch.setattr(module, 'ack', broken_ack)
            with pytest.raises(RuntimeError, match='crash'):
                delivery.dispatch(db)
        with db.transaction() as s:
            s.execute(update(outbox).values(claim_until=0))
        assert delivery.dispatch(db) == 1
        entries = delivery.client.xread({delivery.channel: '0-0'})[0][1]
        assert len(entries) == 2
        assert entries[0][0] != entries[1][0]
        assert [json.loads(fields[b'envelope'])['eventID'] for _, fields in entries] == [event_id]*2
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
        db.close()
