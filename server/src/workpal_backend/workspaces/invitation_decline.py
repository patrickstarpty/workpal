"""Recipient decline with caller-owned SQLite transaction and durable event."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import update, select
from workpal_backend.auth.dependencies import Principal, require_principal
from workpal_backend.auth.models import users
from workpal_backend.infrastructure.outbox import append_event
from . import invitations as service
from .invitation_routes import execute, identifier

router = APIRouter()


def decline_invitation(session, principal, invitation_id):
    uid = service.identity(principal)
    service.stage(session, 500, 'failed to decline invitation')
    # Start the outer transaction before any reads; serialize competing writers.
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    service.stage(session, 404, 'invitation not found')
    row = service.lookup(session, invitation_id)
    service.stage(session, 500, 'failed to load user')
    user = session.execute(select(users).where(users.c.id == uid)).mappings().first()
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(500, 'failed to load user')
    if row['invitee_user_id'] != uid and row['invitee_email'] != user['email'].lower():
        raise service.InvitationAccessError('invitation does not belong to you')
    if row['status'] != 'pending':
        return
    service.stage(session, 500, 'failed to decline invitation')
    count = session.execute(update(service.invitations).where(
        service.invitations.c.id == row['id'], service.invitations.c.status == 'pending'
    ).values(status='declined', updated_at=service.stamp())).rowcount
    if count != 1:
        from sqlalchemy.exc import SQLAlchemyError
        raise SQLAlchemyError('conditional decline lost')
    append_event(session, dict(type='invitation:declined', workspaceID=row['workspace_id'],
        actorType='member', actorID=uid, payload={
            'invitation_id':row['id'], 'invitee_email':row['invitee_email']}))


@router.post('/api/invitations/{id}/decline', status_code=204)
def decline(id: str, request: Request, principal: Principal = Depends(require_principal)):
    iid = identifier(id, 'invitation id')
    execute(request, lambda session: decline_invitation(session, principal, iid),
            'failed to decline invitation')
    return Response(status_code=204)
