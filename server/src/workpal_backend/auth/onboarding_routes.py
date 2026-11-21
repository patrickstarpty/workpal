"""Bounded first-value onboarding HTTP transport."""
from .json_codec import user_response
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from .dependencies import Principal, require_principal
from .profile_decode import ProfileDecodeError
from .onboarding import decode_onboarding, update_onboarding

router = APIRouter()


def persist(database, user_id, patch):
    try:
        with database.transaction() as session:
            result = update_onboarding(session, user_id, patch)
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(500, 'failed to update onboarding') from exc


@router.patch('/api/me/onboarding')
async def patch_onboarding(request: Request, principal: Principal = Depends(require_principal)):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk[:16384-len(raw)])
        if len(raw) == 16384:
            break
    try:
        patch = decode_onboarding(bytes(raw))
    except ProfileDecodeError:
        raise HTTPException(400, 'invalid request body')
    return user_response(await run_in_threadpool(persist, request.app.state.database, principal.user_id, patch))
