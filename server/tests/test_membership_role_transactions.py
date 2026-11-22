"""Real role changes at the SQLite/outbox transaction boundary."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import insert, select, func, update

from workpal_backend.auth.models import users
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces.models import members, workspaces
from workpal_backend.workspaces import membership_mutations as mutation


@pytest.fixture
def seeded(settings):
    migrate(settings)
    db = Database(settings)
    ws, first, second = [str(uuid4()) for _ in range(3)]
    with db.transaction() as s:
        s.execute(insert(workspaces).values(id=ws, name='Roles', slug='roles', issue_prefix='R', created_at='now', updated_at='now'))
        for uid in (first, second):
            s.execute(insert(users).values(id=uid, email=uid+'@example.com', name=uid, created_at='now', updated_at='now'))
            s.execute(insert(members).values(id=uid, workspace_id=ws, user_id=uid, role='owner', created_at='now'))
    yield db, ws, first, second
    db.close()


def change(s, ws, actor, target, role='admin'):
    return mutation.update_member_role(s, {'identity_kind':'session', 'user_id':actor}, ws, target, json.dumps({'role':role}).encode())


def snapshot(db, target):
    with db.transaction() as s:
        return (s.scalar(select(members.c.role).where(members.c.id == target)), s.scalar(select(func.count()).select_from(outbox)))


def test_independent_connections_serialize_owner_self_demotions(settings, seeded):
    db, ws, first, second = seeded
    barrier = Barrier(2)
    def demote(uid):
        connection = Database(settings)
        try:
            barrier.wait(timeout=5)
            try:
                with connection.transaction() as s:
                    change(s, ws, uid, uid)
                return 'success'
            except HTTPException as exc:
                return exc.status_code, exc.detail
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(demote, (first, second)))
    assert results.count('success') == 1
    assert results.count((400, 'workspace must have at least one owner')) == 1
    with db.transaction() as s:
        assert s.scalar(select(func.count()).select_from(members).where(members.c.role == 'owner')) == 1
        assert s.scalar(select(func.count()).select_from(outbox)) == 1


@pytest.mark.parametrize('failure', ['caller', 'lookup', 'append'])
def test_actual_change_rolls_back_on_failure(seeded, monkeypatch, failure):
    db, ws, first, second = seeded
    def fail(*args):
        if failure == 'append':
            original(*args)
        raise RuntimeError('injected '+failure)
    original = mutation.append_event
    if failure != 'caller':
        monkeypatch.setattr(mutation, 'load_member_response' if failure == 'lookup' else 'append_event', fail)
    with pytest.raises(RuntimeError, match='injected'):
        with db.transaction() as s:
            change(s, ws, first, second)
            raise RuntimeError('injected caller')
    assert snapshot(db, second) == ('owner', 0)


@pytest.mark.parametrize('failure', ['lookup', 'append'])
def test_caught_failure_must_not_commit_partial_change(seeded, monkeypatch, failure):
    db, ws, first, second = seeded
    original = mutation.append_event
    def fail(*args):
        if failure == 'append':
            original(*args)
        raise RuntimeError('injected')
    monkeypatch.setattr(mutation, 'load_member_response' if failure == 'lookup' else 'append_event', fail)
    with db.transaction() as s:
        s.execute(update(users).where(users.c.id == first).values(name='Unrelated caller change'))
        with pytest.raises(RuntimeError):
            change(s, ws, first, second)
    assert snapshot(db, second) == ('owner', 0)
    with db.transaction() as s:
        assert s.scalar(select(users.c.name).where(users.c.id == first)) == 'Unrelated caller change'


def test_reopen_and_real_redis_outage_recovery_fifo(settings, seeded, isolated_relay_redis_port):
    db, ws, first, second = seeded
    settings.redis_key_prefix = 'test:member-role:'+uuid4().hex+':'
    with db.transaction() as s:
        assert change(s, ws, first, second)['role'] == 'admin'
    with db.transaction() as s:
        change(s, ws, first, second, 'member')
        expected = [json.loads(row) for row in s.scalars(select(outbox.c.envelope).order_by(outbox.c.event_id))]
    failed = OutboxDelivery(settings)  # fixture uses a real unavailable TCP endpoint
    try:
        assert failed.dispatch(db, retry_delay=0) == 0
    finally:
        failed.close()
        db.close()
    reopened = Database(settings)
    settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
    delivery = OutboxDelivery(settings)
    client = Redis.from_url(settings.redis_url, socket_timeout=2)
    try:
        assert snapshot(reopened, second) == ('member', 2)
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 0
        client.close()
        client = Redis.from_url(settings.redis_url, socket_timeout=2)
        recovered = [json.loads(fields[b'envelope']) for _, fields in client.xrange(delivery.channel)]
        assert [e['payload']['member']['role'] for e in recovered] == ['admin', 'member']
        assert sorted(recovered, key=lambda e:e['eventID']) == expected
        assert len({e['eventID'] for e in recovered}) == 2
    finally:
        client.delete(delivery.channel)
        client.close()
        delivery.close()
        reopened.close()
