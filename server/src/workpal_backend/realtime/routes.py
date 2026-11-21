"""Session-only WebSocket endpoint with authoritative idle/write checks."""
import asyncio
import anyio
import json
from urllib.parse import urlsplit
from fastapi import APIRouter, WebSocket, HTTPException
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from jwt import InvalidTokenError
from sqlalchemy import select
from ..auth.sessions import validate_session
from ..workspaces.models import members, workspaces
from .hub import Connection, authorize
from .protocol import parse_frame, MAX_FRAME_BYTES

router = APIRouter()

def origin_allowed(ws):
    origin = ws.headers.get('origin')
    if origin is None:
        return True
    parsed = urlsplit(origin)
    expected = 'https' if ws.scope['scheme'] == 'wss' else 'http'
    return origin == ws.app.state.settings.frontend_origin or (
        parsed.scheme == expected and parsed.netloc == ws.headers.get('host')
        and origin == f'{expected}://{parsed.netloc}')

async def deny(ws, status, message):
    if 'websocket.http.response' in ws.scope.get('extensions', {}):
        await ws.send_denial_response(JSONResponse({'error': message}, status_code=status))
    else:
        await ws.close(code=1008)

@router.websocket('/ws')
async def websocket(ws: WebSocket):
    if not origin_allowed(ws):
        return await deny(ws, 403, 'Forbidden origin')
    workspace = ws.query_params.get('workspace_id')
    slug = ws.query_params.get('workspace_slug')
    if not workspace and not slug:
        return await deny(ws, 400, 'Workspace required')
    def resolve():
        if workspace:
            return workspace
        with ws.app.state.database.transaction() as session:
            value = session.execute(select(workspaces.c.id).where(workspaces.c.slug == slug)).scalar()
            if value is None:
                raise HTTPException(404, 'Workspace not found')
            return value
    try:
        workspace = await run_in_threadpool(resolve)
    except HTTPException as exc:
        return await deny(ws, exc.status_code, exc.detail)
    except Exception:
        return await deny(ws, 503, 'Lookup failed')
    token = ws.cookies.get('workpal_auth')
    def check():
        try:
            with ws.app.state.database.transaction() as session:
                claims, user = validate_session(session, ws.app.state.settings, token)
                if not session.execute(select(members.c.id).where(
                    members.c.workspace_id == workspace, members.c.user_id == user['id'])).first():
                    raise HTTPException(403, 'Forbidden')
                return claims, user
        except (InvalidTokenError, ValueError):
            raise HTTPException(401, 'Unauthorized; PAT authentication unsupported')
    accepted = False
    connection = None
    receiver = None
    try:
        if not token:
            await ws.accept()
            accepted = True
            message = await asyncio.wait_for(ws.receive(), 10)
            raw = message.get('text') or message.get('bytes') or b''
            if len(raw.encode() if isinstance(raw, str) else raw) > MAX_FRAME_BYTES:
                await ws.close(code=1009)
                return
            if message['type'] != 'websocket.receive' or message.get('bytes') is not None:
                raise ValueError('text authentication required')
            frame = json.loads(raw)
            token = frame.get('payload', {}).get('token') if frame.get('type') == 'auth' else None
        claims, user = await authorize(check)
        if not accepted:
            await ws.accept()
        connection = Connection(ws, check, workspace, user['id'])
        ws.app.state.realtime.connections.add(connection)
        if accepted:
            await connection.send({'type': 'auth_ack'})
        receiver = asyncio.create_task(ws.receive())
        while not connection.closed:
            done, _ = await asyncio.wait({receiver}, timeout=min(0.5, max(0.001, claims['exp'] - __import__('time').time())))
            await authorize(check)
            if not done:
                continue
            message = receiver.result()
            if message['type'] == 'websocket.disconnect':
                break
            raw = message.get('text') or message.get('bytes') or b''
            result = parse_frame(raw, workspace, user['id'])
            if result.close_code:
                await ws.close(code=result.close_code)
                break
            if result.action:
                kind, scope, room = result.action
                if kind == 'subscribe': connection.rooms.add((scope, room))
                else: connection.rooms.discard((scope, room))
            if result.reply:
                await connection.send(result.reply)
            receiver = asyncio.create_task(ws.receive())
    except Exception as exc:
        if connection is None:
            if accepted:
                try:
                    await asyncio.wait_for(ws.send_json({'error': getattr(exc, 'detail', 'Authentication failed')}), 1)
                    await ws.close(code=1008)
                except (RuntimeError, OSError, asyncio.TimeoutError):
                    pass
            else:
                await deny(ws, getattr(exc, 'status_code', 503), getattr(exc, 'detail', 'Lookup failed'))
    finally:
        # Unregister synchronously: cancellation must never retain an audience.
        if connection:
            ws.app.state.realtime.connections.discard(connection)
        with anyio.CancelScope(shield=True):
            if receiver:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
            if connection:
                await connection.close()
