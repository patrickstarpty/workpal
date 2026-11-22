"""Persistence only. Caller commits; HTTP admission/capacity/delivery gates required."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
from sqlalchemy import Table, Column, String, MetaData, CheckConstraint, Index, text, select, update, delete, or_, func
from .models import workspaces, members
from workpal_backend.auth.models import users
from workpal_backend.infrastructure.outbox import append_event

invitations = Table('workspace_invitation', MetaData(),
    Column('id', String, primary_key=True),
    *[Column(k, String, nullable=False) for k in ('workspace_id','inviter_id','invitee_email')],
    Column('invitee_user_id', String),
    *[Column(k, String, nullable=False) for k in ('role','status','created_at','updated_at','expires_at')],
    CheckConstraint("role IN ('admin','member')"),
    CheckConstraint("status IN ('pending','accepted','declined','expired')"),
    # Standalone metadata: explicit SQL references are installed by migration.
)
Index('idx_invitation_unique_pending', invitations.c.workspace_id, invitations.c.invitee_email, unique=True, sqlite_where=text("status='pending'"))
for key in ('invitee_email','invitee_user_id'):
    Index('idx_invitation_'+key, invitations.c[key], sqlite_where=text("status='pending'"))

class InvitationValidationError(ValueError): pass
class InvitationConflictError(ValueError): pass
class InvitationAccessError(PermissionError): pass
class InvitationIdentityError(InvitationAccessError): pass
class InvitationRoleError(InvitationAccessError): pass
class InvitationNotFoundError(LookupError): pass

class InvitationStorageError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)

def stage(session, status, message):
    session.info['invitation_error'] = InvitationStorageError(status, message)

def stamp(now=None):
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None: raise InvitationValidationError('timezone required')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def identity(principal):
    def field(k): return principal.get(k) if isinstance(principal, dict) else getattr(principal,k,None)
    if field('identity_kind') not in ('session', 'cloud_pat') or not field('user_id'):
        raise InvitationIdentityError('unsupported identity')
    return field('user_id')

def authorize(session, principal, wid, admin=False):
    uid = identity(principal)
    row = session.execute(select(members).where(members.c.workspace_id==wid, members.c.user_id==uid)).mappings().first()
    if row is None: raise InvitationNotFoundError('workspace not found')
    if admin and row['role'] not in ('owner','admin'): raise InvitationRoleError('insufficient permissions')
    return uid

def lock(session, wid):
    session.execute(update(workspaces).where(workspaces.c.id==wid).values(issue_counter=workspaces.c.issue_counter))

def enriched(session, row, workspace=False):
    result = dict(row)
    inviter = session.execute(select(users).where(users.c.id==row['inviter_id'])).mappings().first()
    for key in ('name','email'):
        if inviter and inviter[key]: result['inviter_'+key] = inviter[key]
    if workspace:
        name = session.scalar(select(workspaces.c.name).where(workspaces.c.id==row['workspace_id']))
        if name: result['workspace_name'] = name
    return result

def create_invitation(session, principal, workspace_id, email, role='', *, now=None):
    if not isinstance(email,str) or not email.strip(): raise InvitationValidationError('email is required')
    if not isinstance(role,str): raise InvitationValidationError('invalid member role')
    role = 'member' if role == '' else role.strip()
    if role == 'owner': raise InvitationValidationError('cannot invite as owner')
    if role not in ('admin','member'): raise InvitationValidationError('invalid member role')
    email = email.strip().lower()
    lock(session, workspace_id)
    uid = authorize(session, principal, workspace_id, True)
    now = now or datetime.now(timezone.utc)
    current = stamp(now)
    invitee = session.scalar(select(users.c.id).where(func.lower(users.c.email)==email))
    if invitee and session.scalar(select(members.c.id).where(members.c.workspace_id==workspace_id,members.c.user_id==invitee)):
        raise InvitationConflictError('user is already a member')
    session.execute(update(invitations).where(invitations.c.workspace_id==workspace_id,invitations.c.invitee_email==email,invitations.c.status=='pending',invitations.c.expires_at<=current).values(status='expired',updated_at=current))
    if session.scalar(select(invitations.c.id).where(invitations.c.workspace_id==workspace_id,invitations.c.invitee_email==email,invitations.c.status=='pending')):
        raise InvitationConflictError('invitation already pending for this email')
    row = dict(id=str(uuid4()),workspace_id=workspace_id,inviter_id=uid,invitee_email=email,invitee_user_id=invitee,role=role,status='pending',created_at=current,updated_at=current,expires_at=stamp(now+timedelta(days=7)))
    session.execute(invitations.insert().values(**row))
    payload = {'invitation':row}
    name = session.scalar(select(workspaces.c.name).where(workspaces.c.id==workspace_id))
    if name: payload['workspace_name']=name
    append_event(session,dict(type='invitation:created',workspaceID=workspace_id,actorType='member',actorID=uid,payload=payload))
    return row

def list_workspace_invitations(session, principal, workspace_id, *, now=None):
    stage(session, 500, 'failed to list invitations')
    authorize(session,principal,workspace_id)
    return [enriched(session,r) for r in session.execute(select(invitations).where(invitations.c.workspace_id==workspace_id,invitations.c.status=='pending',invitations.c.expires_at>stamp(now)).order_by(invitations.c.created_at.desc())).mappings()]

def recipient(session, principal):
    uid=identity(principal)
    row=session.execute(select(users).where(users.c.id==uid)).mappings().first()
    if row is None: raise InvitationIdentityError('user not found')
    return row

def list_my_invitations(session, principal, *, now=None):
    stage(session, 500, 'failed to load user')
    user=recipient(session,principal)
    stage(session, 500, 'failed to list invitations')
    return [enriched(session,r,True) for r in session.execute(select(invitations).where(or_(invitations.c.invitee_user_id==user['id'],invitations.c.invitee_email==user['email']),invitations.c.status=='pending',invitations.c.expires_at>stamp(now)).order_by(invitations.c.created_at.desc())).mappings()]

def lookup(session, invitation_id):
    try: invitation_id=str(UUID(invitation_id))
    except (ValueError, TypeError, AttributeError): raise InvitationValidationError('invalid invitation id')
    row=session.execute(select(invitations).where(invitations.c.id==invitation_id)).mappings().first()
    if row is None: raise InvitationNotFoundError('invitation not found')
    return row

def get_my_invitation(session, principal, invitation_id):
    identity(principal)
    stage(session, 404, 'invitation not found')
    row=lookup(session,invitation_id)
    stage(session, 500, 'failed to load user')
    user=recipient(session,principal)
    if row['invitee_user_id']!=user['id'] and row['invitee_email']!=user['email'].lower():
        raise InvitationAccessError('invitation does not belong to you')
    from sqlalchemy.exc import SQLAlchemyError, OperationalError
    result = dict(row)
    for table, prefix, key, columns in [(workspaces, 'workspace_', 'workspace_id', ('name',)), (users, 'inviter_', 'inviter_id', ('name', 'email'))]:
        try:
            with session.begin_nested():
                extra = session.execute(select(table).where(table.c.id == row[key])).mappings().first()
            if extra:
                for column in columns:
                    if extra[column]: result[prefix + column] = extra[column]
        except SQLAlchemyError as exc:
            # Contention remains the transaction boundary's responsibility.
            if isinstance(exc, OperationalError) and any(word in str(exc).lower() for word in ('busy', 'locked')):
                raise
    return result

def revoke_invitation(session, principal, workspace_id, invitation_id):
    stage(session, 500, 'failed to revoke invitation')
    lock(session,workspace_id)
    uid=authorize(session,principal,workspace_id,True)
    stage(session, 404, 'invitation not found')
    row=lookup(session,invitation_id)
    stage(session, 500, 'failed to revoke invitation')
    if row['workspace_id']!=workspace_id or row['status']!='pending': raise InvitationNotFoundError('invitation not found')
    count=session.execute(delete(invitations).where(invitations.c.id==row['id'],invitations.c.status=='pending')).rowcount
    if count!=1: raise InvitationNotFoundError('invitation not found')
    append_event(session,dict(type='invitation:revoked',workspaceID=workspace_id,actorType='member',actorID=uid,payload={k:row[k] for k in ('invitee_email','invitee_user_id')} | {'invitation_id':row['id']}))

class InvitationExpiredError(InvitationValidationError):
    """HTTP adapter should map this to 410."""


def accept_invitation(session, principal, invitation_id, *, now=None):
    """Local persistence only; caller owns commit/rollback and admission guards.

    A savepoint keeps a caught failure from committing a partial acceptance.
    SQLite's workspace write lock serializes acceptance with revocation.
    """
    # sqlite3 legacy mode does not BEGIN for SAVEPOINT or SELECT. Establish
    # the caller's outer write transaction before releasing any savepoint.
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    with session.begin_nested():
        user = recipient(session, principal)
        row = lookup(session, invitation_id)
        lock(session, row['workspace_id'])
        row = lookup(session, invitation_id)
        if row['invitee_user_id'] != user['id'] and row['invitee_email'] != user['email'].lower():
            raise InvitationAccessError('invitation does not belong to you')

        def membership():
            columns = [members.c[k] for k in ('id','workspace_id','user_id','role','created_at')]
            columns += [users.c[k] for k in ('name','email','avatar_url')]
            result = session.execute(select(*columns).join(users, users.c.id == members.c.user_id).where(
                members.c.workspace_id == row['workspace_id'], members.c.user_id == user['id'])).mappings().first()
            return dict(result) if result else None

        if row['status'] != 'pending':
            existing = membership() if row['status'] == 'accepted' else None
            if existing is not None:
                return existing
            raise InvitationValidationError('invitation is not pending')
        current = stamp(now)
        if datetime.fromisoformat(row['expires_at']) < datetime.fromisoformat(current):
            raise InvitationExpiredError('invitation has expired')
        count = session.execute(update(invitations).where(
            invitations.c.id == row['id'], invitations.c.status == 'pending'
        ).values(status='accepted', updated_at=current)).rowcount
        if count != 1:
            raise InvitationConflictError('invitation is no longer pending')
        from sqlalchemy.exc import IntegrityError
        try:
            with session.begin_nested():
                session.execute(members.insert().values(id=str(uuid4()), workspace_id=row['workspace_id'],
                    user_id=user['id'], role=row['role'], created_at=current))
        except IntegrityError:
            if membership() is not None:
                raise InvitationConflictError('you are already a member of this workspace')
            raise
        session.execute(update(users).where(users.c.id == user['id']).values(
            onboarded_at=func.coalesce(users.c.onboarded_at, current)))
        member = membership()
        payload = {'member': member}
        name = session.scalar(select(workspaces.c.name).where(workspaces.c.id == row['workspace_id']))
        if name:
            payload['workspace_name'] = name
        for kind, body in [('member:added', payload), ('invitation:accepted', {'invitation_id': row['id'], 'member': member})]:
            append_event(session, dict(type=kind, workspaceID=row['workspace_id'], actorType='member',
                actorID=user['id'], payload=body))
        return member
