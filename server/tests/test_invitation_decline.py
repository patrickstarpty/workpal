from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.workspaces import invitations
from workpal_backend.workspaces.service import create_workspace
from workpal_backend.auth.models import users
from test_workspace_invitations import context
import pytest
import json
from workpal_backend.infrastructure.database import Database
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces.models import members
from workpal_backend.workspaces.invitation_decline import decline_invitation


def test_decline_http(settings, monkeypatch):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/invitations/bad/decline').status_code == 401
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        headers = {'Authorization':'Bearer '+login['token']}
        with client.app.state.database.transaction() as s:
            uid = s.scalar(select(users.c.id))
            ws = create_workspace(s, uid, 'Decline', 'decline')
            row = invitations.create_invitation(s, {'user_id':uid,'identity_kind':'session'}, ws['id'], 'other@example.com')
            s.execute(update(invitations.invitations).where(invitations.invitations.c.id == row['id']).values(expires_at='2000-01-01T00:00:00Z', invitee_user_id=uid))
        path = '/api/invitations/'+row['id']+'/decline'
        assert client.post(path).status_code == 403
        assert client.post('/api/invitations/bad/decline', headers=headers).status_code == 400
        assert client.post('/api/invitations/'+str(uuid4())+'/decline', headers=headers).status_code == 404
        from workpal_backend.workspaces import invitation_decline
        original = invitation_decline.append_event
        def fail(s, event):
            original(s, event)
            raise SQLAlchemyError('after append')
        monkeypatch.setattr(invitation_decline, 'append_event', fail)
        assert client.post(path, headers=headers).status_code == 500
        with client.app.state.database.transaction() as s:
            assert invitations.lookup(s, row['id'])['status'] == 'pending'
        monkeypatch.setattr(invitation_decline, 'append_event', original)
        for _ in range(2):
            response = client.post(path, headers=headers, content='ignored')
            assert response.status_code == 204
            assert response.content == b''
        with client.app.state.database.transaction() as s:
            assert invitations.lookup(s, row['id'])['status'] == 'declined'
            assert s.scalar(text("SELECT count(*) FROM outbox WHERE json_extract(envelope, '$.type')='invitation:declined'")) == 1


def test_recipient_rollback_and_accepted_noop(context, settings):
    from workpal_backend.auth.tokens import issue_session
    db, owner, target, stranger, wid = context
    settings.auth_secret = 's' * 32
    settings.dev_auth = True
    recipient = dict(owner, user_id=target)
    with db.transaction() as s:
        row = invitations.create_invitation(s, owner, wid, 'target@example.com')
    def headers(uid, email):
        return {'Authorization': 'Bearer ' + issue_session(uid, email, email, settings.auth_secret, 3600)}
    with TestClient(create_app(settings)) as client:
        path = '/api/invitations/' + row['id'] + '/decline'
        assert client.post(path, headers=headers(stranger, 'stranger@example.com')).status_code == 403
        with pytest.raises(RuntimeError, match='caller rollback'):
            with db.transaction() as s:
                decline_invitation(s, recipient, row['id'])
                raise RuntimeError('caller rollback')
        with db.transaction() as s:
            assert invitations.lookup(s, row['id'])['status'] == 'pending'
            assert len(list(s.scalars(select(outbox.c.event_id)))) == 1
            invitations.accept_invitation(s, recipient, row['id'])
        with db.transaction() as s:
            before = (list(s.execute(select(members)).all()), list(s.execute(select(users)).all()), list(s.execute(select(outbox)).all()))
        assert client.post(path, headers=headers(target, 'target@example.com')).status_code == 204
        with db.transaction() as s:
            assert invitations.lookup(s, row['id'])['status'] == 'accepted'
            assert before == (list(s.execute(select(members)).all()), list(s.execute(select(users)).all()), list(s.execute(select(outbox)).all()))


@pytest.mark.parametrize('op', ['decline', 'accept', 'revoke'])
def test_independent_connection_races(context, settings, op):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    db, owner, target, stranger, wid = context
    recipient = dict(owner, user_id=target)
    with db.transaction() as s:
        row = invitations.create_invitation(s, owner, wid, 'target@example.com')
    barrier = Barrier(2)
    def run(operation):
        connection = Database(settings)
        try:
            barrier.wait(timeout=10)
            try:
                with connection.transaction() as s:
                    if operation == 'decline': decline_invitation(s, recipient, row['id'])
                    elif operation == 'accept': invitations.accept_invitation(s, recipient, row['id'])
                    else: invitations.revoke_invitation(s, owner, wid, row['id'])
                return 'ok'
            except invitations.InvitationValidationError as error:
                assert operation == 'accept' and str(error) == 'invitation is not pending'
                return 'not-pending'
            except invitations.InvitationNotFoundError as error:
                assert op == 'revoke' and operation in ('decline', 'revoke') and str(error) == 'invitation not found'
                return 'not-found'
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ['decline', op]))
    with db.transaction() as s:
        stored = s.execute(select(invitations.invitations).where(invitations.invitations.c.id == row['id'])).mappings().first()
        status = stored['status'] if stored else None
        kinds = [json.loads(e)['type'] for e in s.scalars(select(outbox.c.envelope))]
        membership = list(s.execute(select(members).where(members.c.user_id == target)))
        if status is None:
            # Go RevokeInvitation deletes pending rows. If revoke won, decline
            # and every subsequent retry must report missing, not a 204 no-op.
            assert op == 'revoke' and results == ['not-found', 'ok']
            assert not membership
            assert kinds == ['invitation:created', 'invitation:revoked']
            before = list(s.execute(select(outbox)).all())
            for _ in range(2):
                with pytest.raises(invitations.InvitationNotFoundError, match='invitation not found'):
                    decline_invitation(s, recipient, row['id'])
            assert list(s.execute(select(outbox)).all()) == before
            return
        if status == 'accepted':
            assert op == 'accept' and results == ['ok', 'ok']
            assert len(membership) == 1
            assert kinds == ['invitation:created', 'member:added', 'invitation:accepted']
        else:
            assert not membership
            assert status == 'declined'
            assert kinds == ['invitation:created', 'invitation:' + status]
            assert results == (['ok', 'not-pending'] if op == 'accept' else ['ok', 'not-found'] if op == 'revoke' and status == 'declined' else ['ok', 'ok'])
        before = list(s.execute(select(outbox)).all())
        decline_invitation(s, recipient, row['id'])
        decline_invitation(s, recipient, row['id'])
        assert list(s.execute(select(outbox)).all()) == before


def test_reopen_outage_fifo(context, settings):
    from workpal_backend.infrastructure.delivery import OutboxDelivery
    db, owner, target, stranger, wid = context
    settings.redis_key_prefix = 'test:decline:' + uuid4().hex + ':'
    with db.transaction() as s:
        row = invitations.create_invitation(s, owner, wid, 'target@example.com')
        decline_invitation(s, dict(owner, user_id=target), row['id'])
        expected = list(s.scalars(select(outbox.c.envelope)))
    failed = OutboxDelivery(settings)
    try:
        assert failed.dispatch(db, retry_delay=0) == 0
    finally:
        failed.close()
        db.close()
    reopened = Database(settings)
    settings.redis_url = 'redis://127.0.0.1:26379'
    delivery = OutboxDelivery(settings)
    try:
        with reopened.transaction() as s:
            assert invitations.lookup(s, row['id'])['status'] == 'declined'
            assert list(s.scalars(select(outbox.c.envelope))) == expected
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 1
        assert delivery.dispatch(reopened) == 0
        received = [fields[b'envelope'].decode() for _, fields in delivery.client.xrange(delivery.channel)]
        assert received == expected
        assert [json.loads(e)['type'] for e in received] == ['invitation:created', 'invitation:declined']
        assert len({json.loads(e)['eventID'] for e in received}) == 2
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
        reopened.close()


@pytest.mark.parametrize('first', ['decline', 'revoke'])
def test_decline_revoke_committed_order(context, first):
    db, owner, target, _, wid = context
    recipient = dict(owner, user_id=target)
    with db.transaction() as s:
        row = invitations.create_invitation(s, owner, wid, 'target@example.com')
    with db.transaction() as s:
        if first == 'decline':
            decline_invitation(s, recipient, row['id'])
        else:
            invitations.revoke_invitation(s, owner, wid, row['id'])
    with pytest.raises(invitations.InvitationNotFoundError, match='invitation not found'):
        with db.transaction() as s:
            if first == 'decline':
                invitations.revoke_invitation(s, owner, wid, row['id'])
            else:
                decline_invitation(s, recipient, row['id'])
    with db.transaction() as s:
        stored = s.execute(select(invitations.invitations).where(invitations.invitations.c.id == row['id'])).mappings().first()
        assert (stored['status'] if stored else None) == ('declined' if first == 'decline' else None)
        assert [json.loads(raw)['type'] for raw in s.scalars(select(outbox.c.envelope))] == [
            'invitation:created', 'invitation:' + ('declined' if first == 'decline' else 'revoked')]
        assert not list(s.execute(select(members).where(members.c.user_id == target)))
