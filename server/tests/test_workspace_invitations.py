import pytest
from workpal_backend.workspaces import invitations

def test_role_validation():
    with pytest.raises(invitations.InvitationValidationError):
        invitations.create_invitation(None, None, 'x', 'x', 'owner')

from sqlalchemy import select
from workpal_backend.infrastructure.database import Database, migrate
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.auth.service import get_or_create_development_user
from workpal_backend.workspaces.service import create_workspace

def test_lifecycle_and_rollback(settings):
    migrate(settings)
    db=Database(settings)
    with db.transaction() as s:
        uid=get_or_create_development_user(s,'dev@workpal.local')['id']
        other='00000000-0000-0000-0000-000000000001'
        ws=create_workspace(s,uid,'Invitations','inv-tests')
    actor={'identity_kind':'session','user_id':uid}
    wrong=dict(actor,user_id=other)
    with db.transaction() as s:
        row=invitations.create_invitation(s,actor,ws['id'],' Invitee@Example.com ')
        assert row['role']=='member' and row['invitee_email']=='invitee@example.com'
    with pytest.raises(invitations.InvitationConflictError):
        with db.transaction() as s: invitations.create_invitation(s,actor,ws['id'],'invitee@example.com')
    with pytest.raises(invitations.InvitationAccessError):
        with db.transaction() as s: invitations.get_my_invitation(s,wrong,row['id'])
    with pytest.raises(invitations.InvitationNotFoundError):
        with db.transaction() as s: invitations.revoke_invitation(s,wrong,ws['id'],row['id'])
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            invitations.revoke_invitation(s,actor,ws['id'],row['id'])
            raise RuntimeError()
    with db.transaction() as s:
        assert len(invitations.list_workspace_invitations(s,actor,ws['id']))==1
        assert len(s.execute(select(outbox)).all())==1
        invitations.revoke_invitation(s,actor,ws['id'],row['id'])
    db.close()
    db=Database(settings)
    with db.transaction() as s:
        assert invitations.list_workspace_invitations(s,actor,ws['id'])==[]
        assert len(s.execute(select(outbox)).all())==2
    db.close()

from datetime import datetime, timezone, timedelta
from sqlalchemy import update
from workpal_backend.auth.models import users

@pytest.fixture
def context(settings):
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        from uuid import uuid4
        owner, target, stranger = [str(uuid4()) for _ in range(3)]
        for uid, email in [(owner,'owner@example.com'),(target,'target@example.com'),(stranger,'stranger@example.com')]:
            s.execute(users.insert().values(id=uid,email=email,name=email,created_at=invitations.stamp(),updated_at=invitations.stamp()))
        ws = create_workspace(s, owner, 'Review', 'review')
    yield db, {'identity_kind':'session', 'user_id':owner}, target, stranger, ws['id']
    db.close()

def test_exact_expiry_and_persisted_recipients(context):
    db, actor, target, stranger, wid = context
    with db.transaction() as s:
        row = invitations.create_invitation(s, actor, wid, 'target@example.com')
        assert datetime.fromisoformat(row['expires_at']) - datetime.fromisoformat(row['created_at']) == timedelta(days=7)
        s.execute(update(users).where(users.c.id == target).values(email='changed@example.com'))
        recipient = dict(actor, user_id=target)
        assert invitations.get_my_invitation(s, recipient, row['id'])['id'] == row['id']
        assert len(invitations.list_my_invitations(s, recipient)) == 1
        with pytest.raises(invitations.InvitationAccessError, match='does not belong'):
            invitations.get_my_invitation(s, dict(actor,user_id=stranger), row['id'])
        email_row = invitations.create_invitation(s, actor, wid, 'changed@example.com')
        assert len(invitations.list_my_invitations(s, recipient)) == 2
        assert invitations.get_my_invitation(s, recipient, email_row['id'])['id'] == email_row['id']

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from workpal_backend.workspaces.models import members

@pytest.mark.parametrize('role', ['member','admin','owner'])
def test_permissions_and_cross_workspace(context, role):
    db, actor, target, stranger, wid = context
    person = dict(actor,user_id=target)
    with db.transaction() as s:
        s.execute(members.insert().values(id=str(uuid4()),workspace_id=wid,user_id=target,role=role,created_at=invitations.stamp()))
        row = invitations.create_invitation(s,actor,wid,'new@example.com')
        other = create_workspace(s,actor['user_id'],'Other','other')
    if role == 'member':
        for operation in [lambda s: invitations.create_invitation(s,person,wid,'another@example.com'),lambda s: invitations.revoke_invitation(s,person,wid,row['id'])]:
            with pytest.raises(invitations.InvitationRoleError):
                with db.transaction() as s: operation(s)
    else:
        with db.transaction() as s:
            invitations.create_invitation(s,person,wid,'another@example.com')
            invitations.revoke_invitation(s,person,wid,row['id'])
    with pytest.raises(invitations.InvitationNotFoundError):
        with db.transaction() as s: invitations.revoke_invitation(s,actor,other['id'],row['id'])


def test_boundary_reopen_and_events(context, settings):
    db, actor, target, stranger, wid = context
    now = datetime(2026,1,1,tzinfo=timezone.utc)
    with db.transaction() as s:
        first = invitations.create_invitation(s,actor,wid,'target@example.com',now=now)
    with pytest.raises(invitations.InvitationConflictError):
        with db.transaction() as s: invitations.create_invitation(s,actor,wid,'target@example.com',now=now+timedelta(days=7,microseconds=-1))
    with db.transaction() as s:
        assert invitations.list_workspace_invitations(s,actor,wid,now=now+timedelta(days=7)) == []
        second = invitations.create_invitation(s,actor,wid,'target@example.com',now=now+timedelta(days=7))
        assert invitations.lookup(s,first['id'])['status'] == 'expired'
    with pytest.raises(invitations.InvitationNotFoundError):
        with db.transaction() as s: invitations.revoke_invitation(s,actor,wid,first['id'])
    db.close()
    reopened = Database(settings)
    with reopened.transaction() as s:
        assert invitations.lookup(s,second['id']) == second
        invitations.revoke_invitation(s,actor,wid,second['id'])
        events = [json.loads(e) for e in s.scalars(select(outbox.c.envelope))]
        for event in events:
            assert event['workspaceID'] == wid
            assert event['actorID'] == actor['user_id']
            assert event['actorType'] == 'member'
        assert events[0]['type'] == 'invitation:created'
        assert events[0]['payload'] == {'invitation':first,'workspace_name':'Review'}
        assert events[1]['payload'] == {'invitation':second,'workspace_name':'Review'}
        assert events[2]['type'] == 'invitation:revoked'
        assert events[2]['payload'] == {'invitation_id':second['id'],'invitee_email':'target@example.com','invitee_user_id':target}
    reopened.close()

@pytest.mark.parametrize('operation', ['create','revoke'])
@pytest.mark.parametrize('failure', ['append','caller'])
def test_atomic_rollback(context, monkeypatch, operation, failure):
    db, actor, target, stranger, wid = context
    with db.transaction() as s:
        row = invitations.create_invitation(s,actor,wid,'target@example.com')
        before_rows = [dict(r) for r in s.execute(select(invitations.invitations)).mappings()]
        before_events = list(s.scalars(select(outbox.c.envelope)))
    original = invitations.append_event
    def fail(s,event):
        original(s,event)
        raise RuntimeError('injected append failure')
    if failure == 'append': monkeypatch.setattr(invitations,'append_event',fail)
    with pytest.raises(RuntimeError):
        with db.transaction() as s:
            if operation == 'create': invitations.create_invitation(s,actor,wid,'new@example.com')
            else: invitations.revoke_invitation(s,actor,wid,row['id'])
            raise RuntimeError('caller rollback')
    with db.transaction() as s:
        assert [dict(r) for r in s.execute(select(invitations.invitations)).mappings()] == before_rows
        assert list(s.scalars(select(outbox.c.envelope))) == before_events


def test_concurrent_normalized_duplicate(context):
    db, actor, target, stranger, wid = context
    barrier = Barrier(2)
    def create(email):
        barrier.wait()
        try:
            with db.transaction() as s: invitations.create_invitation(s,actor,wid,email)
            return 'created'
        except invitations.InvitationConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create,[' SAME@example.com ','same@example.com']))
    assert sorted(results) == ['conflict','created']
    with db.transaction() as s:
        assert len(list(s.scalars(select(invitations.invitations.c.id)))) == 1
        assert len(list(s.scalars(select(outbox.c.event_id)))) == 1


def test_reinvite_expires_only_matching_recipient(context):
    from datetime import datetime, timezone, timedelta
    db, actor, target, stranger, wid = context
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with db.transaction() as session:
        first = invitations.create_invitation(session, actor, wid, 'target@example.com', now=start)
        other = invitations.create_invitation(session, actor, wid, 'unrelated@example.com', now=start)
    with db.transaction() as session:
        invitations.create_invitation(session, actor, wid, 'target@example.com', now=start+timedelta(days=8))
    with db.transaction() as session:
        assert invitations.lookup(session, first['id'])['status'] == 'expired'
        assert dict(invitations.lookup(session, other['id'])) == other
