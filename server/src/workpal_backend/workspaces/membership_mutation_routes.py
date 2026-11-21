"""HTTP role update; the complete SQL unit runs outside the event loop."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from workpal_backend.auth.dependencies import Principal, require_principal
from .routes import execute, workspace_uuid
from .membership_mutations import update_member_role

router = APIRouter()


@router.patch('/api/workspaces/{id}/members/{memberId}')
async def patch_member(id: str, memberId: str, request: Request, principal: Principal = Depends(require_principal)):
    wid = workspace_uuid(id)
    body = await request.body()
    try:
        return await run_in_threadpool(execute, request, lambda session: update_member_role(session, principal, wid, memberId, body))
    except SQLAlchemyError as exc:
        mapped = getattr(exc, 'membership_http_error', None)
        if mapped is None:
            raise
        raise HTTPException(*mapped) from exc
