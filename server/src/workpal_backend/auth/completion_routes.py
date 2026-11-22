"""Bounded optional completion transport."""
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from .dependencies import Principal, require_principal
from .completion import decode_completion, complete_onboarding
from .json_codec import user_response

router = APIRouter()


def persist(database, user_id):
    try:
        with database.transaction() as session:
            result = complete_onboarding(session, user_id)
        return result
    except SQLAlchemyError as exc:
        raise HTTPException(500, 'failed to complete onboarding') from exc


@router.post('/api/me/onboarding/complete')
async def complete(request: Request, principal: Principal = Depends(require_principal)):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 16384:
            raise HTTPException(413, 'request body too large')
        raw.extend(chunk)
    length = request.headers.get('content-length', '0')
    patch = decode_completion(bytes(raw)) if length.isdigit() and int(length) > 0 else {}
    workspace = patch.get('workspace_id', '')
    if workspace and not re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}', workspace):
        raise HTTPException(400, 'invalid workspace_id')
    return user_response(await run_in_threadpool(persist, request.app.state.database, principal.user_id))
