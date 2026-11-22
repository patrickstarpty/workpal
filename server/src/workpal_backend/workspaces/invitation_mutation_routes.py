"""Local invitation mutations; no email delivery or production capacity gate."""
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, func
from . import invitations as service
from .invitation_routes import identifier, execute
from .invitation_admission import InvitationAdmission, InvitationAdmissionError
from .models import members
from workpal_backend.auth.models import users
from workpal_backend.auth.dependencies import Principal, require_principal

router = APIRouter()


def mutation(request, operation, failure):
    def mapped(session):
        try:
            return operation(session)
        except service.InvitationExpiredError as exc:
            raise HTTPException(410, str(exc)) from exc
        except service.InvitationConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
    return execute(request, mapped, failure)


@router.post('/api/workspaces/{id}/members', status_code=201)
async def create(id: str, request: Request, principal: Principal = Depends(require_principal)):
    wid = identifier(id, 'workspace id')
    # Authorization precedes decoding, as in the source middleware.
    await run_in_threadpool(mutation, request, lambda s: service.authorize(s, principal, wid, True), 'failed to create invitation')
    try:
        body = json.JSONDecoder().raw_decode((await request.body()).decode().lstrip())[0]
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise ValueError()
        email, role = body.get('email') or '', body.get('role') or ''
        if any(body.get(k) is not None and not isinstance(body[k], str) for k in ('email', 'role')):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'invalid request body')
    email = email.strip().lower()
    role = 'member' if role == '' else role.strip()
    if not email:
        raise HTTPException(400, 'email is required')
    if role == 'owner':
        raise HTTPException(400, 'cannot invite as owner')
    if role not in ('admin', 'member'):
        raise HTTPException(400, 'invalid member role')

    def preflight(session):
        uid = service.authorize(session, principal, wid, True)
        invitee = session.scalar(select(users.c.id).where(func.lower(users.c.email) == email))
        if invitee and session.scalar(select(members.c.id).where(members.c.workspace_id == wid, members.c.user_id == invitee)):
            raise service.InvitationConflictError('user is already a member')
        table = service.invitations
        if session.scalar(select(table.c.id).where(table.c.workspace_id == wid, table.c.invitee_email == email,
                table.c.status == 'pending', table.c.expires_at > service.stamp())):
            raise service.InvitationConflictError('invitation already pending for this email')
        return uid
    uid = await run_in_threadpool(mutation, request, preflight, 'failed to create invitation')
    # execute has closed its read transaction before any Redis await.
    try:
        await InvitationAdmission(request.app.state.redis).admit(uid, wid, email)
    except InvitationAdmissionError as exc:
        return JSONResponse(exc.body, status_code=exc.status_code, headers=exc.headers)
    return await run_in_threadpool(mutation, request, lambda s: service.create_invitation(s, principal, wid, email, role), 'failed to create invitation')


@router.post('/api/invitations/{id}/accept')
def accept(id: str, request: Request, principal: Principal = Depends(require_principal)):
    iid = identifier(id, 'invitation id')
    # Source never decodes an acceptance body.
    return mutation(request, lambda s: service.accept_invitation(s, principal, iid), 'failed to accept invitation')
