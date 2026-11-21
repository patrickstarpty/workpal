"""Workspace HTTP boundary; production mounting belongs to the application owner."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from workpal_backend.auth.dependencies import Principal, require_principal
from workpal_backend.infrastructure.database import DatabaseBusy
from .schemas import CreateWorkspace, UpdateWorkspace
from . import service

router = APIRouter()

def creation_policy(request: Request, principal: Principal):
    """Explicit integration option until Settings gains creation configuration.

    app.state.workspace_creation_enabled (bool, default True) and
    workspace_creation_allowlist (user IDs, default None) are server-owned.
    """
    settings = request.app.state.settings
    if settings.disable_workspace_creation or not getattr(request.app.state, 'workspace_creation_enabled', True):
        raise HTTPException(403, 'workspace creation is disabled')
    emails = {email.strip().lower() for email in settings.workspace_creation_allowed_emails.split(',') if email.strip()}
    if emails:
        from workpal_backend.auth.service import get_user
        with request.app.state.database.transaction() as session:
            user = get_user(session, principal.user_id)
        if not user or user['email'].strip().lower() not in emails:
            raise HTTPException(403, 'workspace creation is restricted to selected users on this instance')
    allowed = getattr(request.app.state, 'workspace_creation_allowlist', None)
    if allowed is not None and principal.user_id not in allowed:
        raise HTTPException(403, 'workspace creation is not allowed')

def execute(request, operation):
    try:
        with request.app.state.database.transaction() as session:
            return operation(session)
    except DatabaseBusy:
        return JSONResponse({'error':'Database is busy; retry later','retryable':True}, status_code=503, headers={'Retry-After':'1'})
    except service.WorkspaceValidationError as exc:
        raise HTTPException(400, str(exc))
    except service.WorkspaceConflictError as exc:
        raise HTTPException(409, str(exc))
    except service.WorkspaceRoleError:
        raise HTTPException(403, 'insufficient permissions')
    except service.WorkspaceAccessError:
        raise HTTPException(404, 'workspace not found')

@router.get('/api/workspaces')
def list_workspaces(request: Request, principal: Principal = Depends(require_principal)):
    return execute(request, lambda session: service.list_workspaces(session, principal.user_id))

@router.post('/api/workspaces', status_code=201)
def create_workspace(body: CreateWorkspace, request: Request, principal: Principal = Depends(require_principal)):
    creation_policy(request, principal)
    return execute(request, lambda session: service.create_workspace(session, principal.user_id, body.name, body.slug, body.issue_prefix))

@router.get('/api/workspaces/{workspace_id}')
def get_workspace(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
    try:
        workspace_id = str(UUID(workspace_id))
    except ValueError:
        raise HTTPException(400, 'invalid workspace_id')
    return execute(request, lambda session: service.get_workspace(session, principal, workspace_id))


def workspace_uuid(value):
    try:
        return str(UUID(value))
    except ValueError:
        raise HTTPException(400, 'invalid workspace id')


@router.put('/api/workspaces/{workspace_id}')
@router.patch('/api/workspaces/{workspace_id}')
def update_workspace(workspace_id: str, body: UpdateWorkspace, request: Request, principal: Principal = Depends(require_principal)):
    workspace_id = workspace_uuid(workspace_id)
    return execute(request, lambda session: service.update_workspace(session, principal, workspace_id, body.model_dump()))


@router.put('/api/workspaces/{workspace_id}/pin')
async def pin_workspace(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
    workspace_id = workspace_uuid(workspace_id)
    try:
        body = await request.json()
    except ValueError:
        body = None
    pinned = body.get('pinned') if isinstance(body, dict) else None
    return execute(request, lambda session: service.set_pinned(session, principal, workspace_id, pinned))


@router.get('/api/workspaces/{workspace_id}/members')
def list_members(workspace_id: str, request: Request, principal: Principal = Depends(require_principal)):
    workspace_id = workspace_uuid(workspace_id)
    return execute(request, lambda session: service.list_members(session, principal, workspace_id))
