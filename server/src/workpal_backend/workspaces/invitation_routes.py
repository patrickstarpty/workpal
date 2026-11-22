"""Session-authenticated invitation reads and transactional revocation."""
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from workpal_backend.auth.dependencies import Principal, require_principal
from . import invitations as service

router = APIRouter()


def identifier(value, label):
    try:
        return str(UUID(value))
    except ValueError:
        raise HTTPException(400, 'invalid ' + label)


def execute(request, operation, failure='failed to list invitations'):
    session = None
    try:
        with request.app.state.database.transaction() as session:
            return operation(session)
    except SQLAlchemyError as exc:
        error = (session.info if session is not None else {}).get('invitation_error', service.InvitationStorageError(500, failure))
        raise HTTPException(error.status, str(error)) from exc
    except service.InvitationIdentityError:
        raise HTTPException(401, 'user not found')
    except service.InvitationRoleError:
        raise HTTPException(403, 'insufficient permissions')
    except service.InvitationAccessError as exc:
        raise HTTPException(403, str(exc))
    except service.InvitationNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except service.InvitationValidationError as exc:
        raise HTTPException(400, str(exc))


@router.get('/api/workspaces/{id}/invitations')
def workspace_invitations(id: str, request: Request, principal: Principal = Depends(require_principal)):
    wid = identifier(id, 'workspace id')
    return execute(request, lambda session: service.list_workspace_invitations(session, principal, wid))


@router.get('/api/invitations')
def my_invitations(request: Request, principal: Principal = Depends(require_principal)):
    return execute(request, lambda session: service.list_my_invitations(session, principal))


@router.get('/api/invitations/{id}')
def my_invitation(id: str, request: Request, principal: Principal = Depends(require_principal)):
    iid = identifier(id, 'invitation id')
    return execute(request, lambda session: service.get_my_invitation(session, principal, iid), 'failed to load user')


@router.delete('/api/workspaces/{id}/invitations/{invitationId}', status_code=204)
def revoke(id: str, invitationId: str, request: Request, principal: Principal = Depends(require_principal)):
    wid = identifier(id, 'workspace id')
    iid = identifier(invitationId, 'invitation id')
    execute(request, lambda session: service.revoke_invitation(session, principal, wid, iid), 'failed to revoke invitation')
    return Response(status_code=204)
