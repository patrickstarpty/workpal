"""Go RequireWorkspaceMember admission for canonical workspace-scoped routes."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.auth.task_workspace import query_values
from workpal_backend.infrastructure.database import DatabaseBusy
from workpal_backend.infrastructure.go_uuid import parse_uuid
from .models import workspaces,members


def query_first(request,key):
    # URL.Query ignores bad pairs while preserving the first valid value.
    for pair in request.scope.get('query_string',b'').split(b'&'):
        try:values=query_values(pair)
        except HTTPException:continue
        if key in values:return values[key][0]
    return ''


def admit(request,principal):
    database=request.app.state.database
    slug=query_first(request,'workspace_slug') or request.headers.get('x-workspace-slug','')
    workspace=query_first(request,'workspace_id') or request.headers.get('x-workspace-id','')
    if slug:
        try:
            with database.transaction() as session:
                workspace=session.scalar(select(workspaces.c.id).where(workspaces.c.slug==slug))
        except (SQLAlchemyError,DatabaseBusy) as exc:
            raise HTTPException(404,'workspace not found') from exc
        if not workspace:raise HTTPException(404,'workspace not found')
    if not workspace:raise HTTPException(400,'workspace_id or workspace_slug is required')
    try:user=parse_uuid(principal.user_id)
    except ValueError as exc:raise HTTPException(401,'user not authenticated') from exc
    try:workspace=parse_uuid(workspace)
    except ValueError as exc:raise HTTPException(400,'invalid workspace_id') from exc
    member=read_member(database,user,workspace)
    return workspace,user,member


def read_member(database,user,workspace):
    try:
        with database.transaction() as session:
            member=session.execute(select(members).where(members.c.workspace_id==workspace,
                members.c.user_id==user)).mappings().one_or_none()
    except (SQLAlchemyError,DatabaseBusy) as exc:
        raise HTTPException(404,'workspace not found') from exc
    if member is None:raise HTTPException(404,'workspace not found')
    return dict(member)
