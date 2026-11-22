"""Authenticated local waitlist transport; intentionally capped at 16 KiB."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from .dependencies import Principal, require_principal
from .json_codec import user_response
from .waitlist import join_waitlist
from .waitlist_decode import decode_waitlist

router = APIRouter()


def persist(database, user_id, email, reason):
    try:
        with database.transaction() as session:
            result = join_waitlist(session, user_id, email, reason)
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(500, 'failed to join waitlist') from exc


@router.post('/api/me/onboarding/cloud-waitlist')
async def join(request: Request, principal: Principal = Depends(require_principal)):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 16384:
            raise HTTPException(413, 'request body too large')
        raw.extend(chunk)
    try:
        email, reason = decode_waitlist(bytes(raw))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return user_response(await run_in_threadpool(persist, request.app.state.database, principal.user_id, email, reason))
