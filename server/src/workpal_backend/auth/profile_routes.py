"""Bounded local PATCH /api/me transport."""
from .json_codec import user_response
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from .dependencies import Principal, require_principal
from .profile_decode import decode_profile_patch, ProfileDecodeError
from .profile import update_profile

router = APIRouter()


def persist(database, user_id, patch):
    stage = ['load']
    try:
        with database.transaction() as session:
            result = update_profile(session, user_id, patch, stage)
        return result
    except SQLAlchemyError as exc:
        # Transaction has already rolled back and classified SQLite contention.
        raise HTTPException(404 if stage[0] == 'load' else 500,
                            'user not found' if stage[0] == 'load' else 'failed to update user') from exc


@router.patch('/api/me')
async def patch_me(request: Request, principal: Principal = Depends(require_principal)):
    raw = await request.body()
    try:
        patch = decode_profile_patch(raw)
    except ProfileDecodeError:
        raise HTTPException(400, 'invalid request body')
    return user_response(await run_in_threadpool(persist, request.app.state.database, principal.user_id, patch))
