"""Workspace-scoped access to preserved local content; caller owns transactions."""
from sqlalchemy import delete, func, select, update

from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspaces.service import WorkspaceAccessError, require_workspace_access
from .models import records


def resolve_workspace(session, principal, slug):
    workspace = session.execute(select(workspaces).where(workspaces.c.slug == slug)).mappings().one_or_none()
    if workspace is None:
        raise WorkspaceAccessError('workspace not found')
    require_workspace_access(session, principal, workspace['id'])
    return dict(workspace)


def list_records(session, workspace_id, kind):
    return list(session.scalars(select(records.c.body).where(
        records.c.workspace_id == workspace_id, records.c.kind == kind,
    ).order_by(records.c.position, records.c.id)))


def get_record(session, workspace_id, kind, record_id):
    return session.scalar(select(records.c.body).where(
        records.c.workspace_id == workspace_id, records.c.kind == kind, records.c.id == record_id,
    ))


def put_record(session, workspace_id, kind, body):
    predicate = (records.c.workspace_id == workspace_id, records.c.kind == kind, records.c.id == body['id'])
    existing = session.execute(select(records.c.id).where(*predicate)).first()
    if existing:
        # Keep source_body intact as the original import snapshot, and preserve order.
        session.execute(update(records).where(*predicate).values(body=body))
    else:
        position = session.scalar(select(func.max(records.c.position)).where(
            records.c.workspace_id == workspace_id, records.c.kind == kind,
        ))
        session.execute(records.insert().values(workspace_id=workspace_id, kind=kind, id=body['id'],
                                               body=body, position=0 if position is None else position + 1))
    return body


def delete_record(session, workspace_id, kind, record_id):
    return session.execute(delete(records).where(
        records.c.workspace_id == workspace_id, records.c.kind == kind, records.c.id == record_id,
    )).rowcount != 0
