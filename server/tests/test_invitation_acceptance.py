from test_workspace_invitations import context
from workpal_backend.workspaces import invitations as api
from sqlalchemy import select
from workpal_backend.workspaces.models import members
from workpal_backend.auth.models import users


def test_accept_and_retry(context):
    db, actor, target, _, wid = context
    principal = dict(actor, user_id=target)
    with db.transaction() as s:
        invitation = api.create_invitation(s, actor, wid, 'target@example.com', 'admin')
    with db.transaction() as s:
        member = api.accept_invitation(s, principal, invitation['id'])
        assert member['role'] == 'admin'
        assert member['email'] == 'target@example.com'
        onboarded = s.scalar(select(users.c.onboarded_at).where(users.c.id == target))
        assert onboarded
    with db.transaction() as s:
        assert api.accept_invitation(s, principal, invitation['id']) == member
        assert s.scalar(select(users.c.onboarded_at).where(users.c.id == target)) == onboarded
        assert len(s.execute(select(members).where(members.c.user_id == target)).all()) == 1


def test_caller_rollback_undoes_acceptance(context):
    import pytest
    from workpal_backend.infrastructure.outbox import outbox
    db, actor, target, _, wid = context
    with db.transaction() as session:
        invitation = api.create_invitation(session, actor, wid, 'target@example.com')
    with pytest.raises(RuntimeError):
        with db.transaction() as session:
            api.accept_invitation(session, dict(actor, user_id=target), invitation['id'])
            raise RuntimeError('caller rollback')
    with db.transaction() as session:
        assert api.lookup(session, invitation['id'])['status'] == 'pending'
        assert session.scalar(select(users.c.onboarded_at).where(users.c.id == target)) is None
        assert session.execute(select(members).where(members.c.user_id == target)).first() is None
        assert len(session.execute(select(outbox)).all()) == 1

import pytest
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import delete
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.infrastructure.database import Database


def snapshot(db, target):
    with db.transaction() as s:
        return (list(s.execute(select(api.invitations)).mappings()),
                list(s.execute(select(members).where(members.c.user_id == target)).mappings()),
                s.scalar(select(users.c.onboarded_at).where(users.c.id == target)),
                list(s.execute(select(outbox)).mappings()))


def create(context, **kwargs):
    db, actor, target, _, wid = context
    with db.transaction() as s:
        return api.create_invitation(s, actor, wid, 'target@example.com', **kwargs)


@pytest.mark.parametrize('failure_at', [1, 2])
def test_append_failure_caught_then_outer_commit(context, monkeypatch, failure_at):
    db, actor, target, _, _ = context
    row = create(context)
    before = snapshot(db, target)
    real = api.append_event
    calls = []
    def append(s, event):
        real(s, event)
        calls.append(event['type'])
        if len(calls) == failure_at:
            raise RuntimeError('after real append')
    monkeypatch.setattr(api, 'append_event', append)
    with db.transaction() as s:
        with pytest.raises(RuntimeError, match='after real append'):
            api.accept_invitation(s, dict(actor, user_id=target), row['id'])
    assert len(calls) == failure_at
    assert snapshot(db, target) == before


def test_existing_membership_conflict_is_atomic(context):
    db, actor, target, _, wid = context
    row = create(context)
    with db.transaction() as s:
        s.execute(members.insert().values(id=str(uuid4()), workspace_id=wid,
            user_id=target, role='member', created_at=api.stamp()))
    before = snapshot(db, target)
    with db.transaction() as s:
        with pytest.raises(api.InvitationConflictError):
            api.accept_invitation(s, dict(actor, user_id=target), row['id'])
    assert snapshot(db, target) == before


@pytest.mark.parametrize('revoke', [False, True])
def test_competing_connections(context, settings, revoke):
    db, actor, target, _, wid = context
    row = create(context)
    barrier = Barrier(2)
    def operation(index):
        connection = Database(settings)
        try:
            barrier.wait(timeout=5)
            try:
                with connection.transaction() as s:
                    if revoke and index:
                        api.revoke_invitation(s, actor, wid, row['id'])
                        return 'revoked'
                    return api.accept_invitation(s, dict(actor, user_id=target), row['id'])
            except api.InvitationNotFoundError:
                return 'missing'
        finally:
            connection.close()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(operation, range(2)))
    state = snapshot(db, target)
    kinds = [json.loads(r['envelope'])['type'] for r in state[3]]
    assert kinds[0] == 'invitation:created'  # Creation contributes one event.
    if any(isinstance(r, dict) for r in results):
        assert len(state[1]) == 1 and state[2]
        assert kinds == ['invitation:created', 'member:added', 'invitation:accepted']
        with db.transaction() as s:
            api.accept_invitation(s, dict(actor, user_id=target), row['id'])
        assert snapshot(db, target) == state
    else:
        assert sorted(results) == ['missing', 'revoked']
        assert state[0] == [] and state[1] == [] and state[2] is None
        assert kinds == ['invitation:created', 'invitation:revoked']
    if not revoke:
        assert results[0] == results[1]


@pytest.mark.parametrize('offset', [-1, 0, 1])
def test_strict_expiry(context, offset):
    db, actor, target, _, _ = context
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row = create(context, now=now)
    before = snapshot(db, target)
    with db.transaction() as s:
        if offset > 0:
            with pytest.raises(api.InvitationExpiredError):
                api.accept_invitation(s, dict(actor, user_id=target), row['id'], now=now+timedelta(days=7,microseconds=offset))
        else:
            api.accept_invitation(s, dict(actor, user_id=target), row['id'], now=now+timedelta(days=7,microseconds=offset))
    if offset > 0:
        assert snapshot(db, target) == before
    else:
        assert len(snapshot(db, target)[1]) == 1


def test_foreign_and_removed_membership(context, settings):
    db, actor, target, stranger, _ = context
    row = create(context)
    before = snapshot(db, target)
    with db.transaction() as s:
        with pytest.raises(api.InvitationAccessError):
            api.accept_invitation(s, dict(actor, user_id=stranger), row['id'])
    assert snapshot(db, target) == before
    with db.transaction() as s:
        api.accept_invitation(s, dict(actor, user_id=target), row['id'])
    accepted = snapshot(db, target)
    db.close()
    reopened = Database(settings)
    try:
        assert snapshot(reopened, target) == accepted
        with reopened.transaction() as s:
            s.execute(delete(members).where(members.c.user_id == target))
        before = snapshot(reopened, target)
        with reopened.transaction() as s:
            with pytest.raises(api.InvitationValidationError, match='not pending'):
                api.accept_invitation(s, dict(actor, user_id=target), row['id'])
        assert snapshot(reopened, target) == before
    finally:
        reopened.close()


def test_redis_outage_recovery_preserves_order_and_ids(context, settings, isolated_relay_redis_port):
    from workpal_backend.infrastructure.delivery import OutboxDelivery
    from redis import Redis
    db, actor, target, _, _ = context
    row = create(context)
    with db.transaction() as s:
        api.accept_invitation(s, dict(actor, user_id=target), row['id'])
    envelopes = [json.loads(r['envelope']) for r in snapshot(db, target)[3]]
    assert [e['type'] for e in envelopes] == ['invitation:created', 'member:added', 'invitation:accepted']
    prefix = 'test:acceptance:' + str(uuid4()) + ':'
    offline = OutboxDelivery(settings.model_copy(update={'redis_key_prefix': prefix}))
    try:
        assert offline.dispatch(db, retry_delay=0) == 0
    finally:
        offline.close()
    online = OutboxDelivery(settings.model_copy(update={'redis_url': f'redis://127.0.0.1:{isolated_relay_redis_port}/0', 'redis_key_prefix': prefix}))
    try:
        assert online.client.ping()
        for _ in envelopes:
            assert online.dispatch(db, retry_delay=0) == 1
        assert online.dispatch(db) == 0
        actual = [json.loads(fields[b'envelope']) for _, fields in online.client.xrange(online.channel)]
        assert actual == envelopes
        assert len({e['eventID'] for e in actual}) == 3
    finally:
        online.client.delete(online.channel)  # Exact owned stream only.
        online.close()
