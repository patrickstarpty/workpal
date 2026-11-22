"""Role-only mutation. Caller owns the transaction, including the durable event."""
import json
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from workpal_backend.auth.models import users
from workpal_backend.infrastructure.outbox import append_event
from .models import members, workspaces
from .service import require_workspace_access


class ObjectPairs(list):
    """Keep object keys ordered and distinguish objects from JSON arrays."""


def update_member_role(session, principal, workspace_id, member_id, raw_body):
    # A real outer transaction prevents SQLite legacy SAVEPOINT release from
    # committing independently. The savepoint also undoes this unit if a caller
    # catches its failure and later commits unrelated work.
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    with session.begin_nested():
        return _update_member_role(session, principal, workspace_id, member_id, raw_body)


def _update_member_role(session, principal, workspace_id, member_id, raw_body):
    # Acquire the shared SQLite writer boundary before any authorization reads.
    session.execute(update(workspaces).where(workspaces.c.id == workspace_id).values(issue_counter=workspaces.c.issue_counter))
    actor = require_workspace_access(session, principal, workspace_id)
    if actor['role'] not in ('owner', 'admin'):
        raise HTTPException(403, 'insufficient permissions')
    try:
        member_id = str(UUID(member_id))
    except ValueError:
        raise HTTPException(400, 'invalid member id')
    target = stage_sql(session, 404, 'member not found', lambda: session.execute(select(members).where(members.c.id == member_id, members.c.workspace_id == workspace_id)).mappings().one_or_none())
    if target is None:
        raise HTTPException(404, 'member not found')
    try:
        body = json.JSONDecoder(object_pairs_hook=ObjectPairs).raw_decode(raw_body.decode().lstrip())[0]
        body = ObjectPairs() if body is None else body
        if not isinstance(body, ObjectPairs):
            raise ValueError()
        role = ''
        for key, value in body:
            if key.lower() == 'role' and value is not None:
                if not isinstance(value, str):
                    raise ValueError()
                role = value
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'invalid request body')
    role = (role or '').strip()
    if not role:
        raise HTTPException(400, 'role is required')
    if role not in ('owner', 'admin', 'member'):
        raise HTTPException(400, 'invalid member role')
    if (target['role'] == 'owner' or role == 'owner') and actor['role'] != 'owner':
        raise HTTPException(403, 'insufficient permissions')
    if target['role'] == 'owner' and role != 'owner':
        count = stage_sql(session, 500, 'failed to update member', lambda: session.scalar(select(func.count()).select_from(members).where(members.c.workspace_id == workspace_id, members.c.role == 'owner')))
        if count <= 1:
            raise HTTPException(400, 'workspace must have at least one owner')
    stage_sql(session, 500, 'failed to update member', lambda: session.execute(update(members).where(members.c.id == member_id).values(role=role)))
    result = stage_sql(session, 500, 'failed to load member', lambda: load_member_response(session, member_id))
    append_event(session, dict(type='member:updated', workspaceID=workspace_id, actorType='member', actorID=actor['user_id'], payload={'member':result}))
    return result


def load_member_response(session, member_id):
    columns = [members.c[k] for k in ('id','workspace_id','user_id','role','created_at')]
    columns += [users.c[k] for k in ('name','email','avatar_url')]
    row = session.execute(select(*columns).join(users, users.c.id == members.c.user_id).where(members.c.id == member_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(500, 'failed to load member')
    return dict(row)


def stage_sql(session, status, message, operation):
    # Leave the original SQL exception intact until Database.transaction has
    # classified contention and rolled back the entire mutation.
    try:
        return operation()
    except SQLAlchemyError as exc:
        exc.membership_http_error = (status, message)
        raise
