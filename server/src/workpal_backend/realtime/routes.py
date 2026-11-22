"""JWT/PAT handshake with independent workspace membership checks."""
import asyncio
import anyio
from fastapi import APIRouter, WebSocket, HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from ..auth.dependencies import authenticate_token
from ..auth.errors import authentication_error
from ..workspaces.models import members, workspaces
from .hub import Connection, authorize
from .protocol import parse_frame
from .first_message_auth import read_first_auth, send_auth_error, abort_socket
from .scope_authorizer import ScopeAuthorizer
from .request_values import query_value, first_cookie
from ..projects.queries import ProjectQueries

router = APIRouter()

def origin_allowed(ws):
    def header(name):
        return ws.headers.get(name, '').encode('latin1').decode('utf-8', errors='surrogateescape')
    peer = ws.scope.get('workpal.peer', ws.scope.get('client'))
    remote = ''
    if peer:
        host, port = peer
        remote = f'[{host}]:{port}' if ':' in host else f'{host}:{port}'
    return ws.app.state.ws_origin_policy.allowed(header('origin'), header('host'), remote,
                                                header('x-forwarded-host'))


async def deny_origin(ws):
    if 'websocket.http.response' in ws.scope.get('extensions', {}):
        from starlette.responses import Response
        await ws.send_denial_response(Response('Forbidden\n', status_code=403, media_type='text/plain',
            headers={'X-Content-Type-Options':'nosniff', 'Sec-WebSocket-Version':'13'}))
    else:
        await ws.close(code=1008)

async def deny(ws, status, message):
    if 'websocket.http.response' in ws.scope.get('extensions', {}):
        await ws.send_denial_response(await authentication_error(None, HTTPException(status, message)))
    else:
        await ws.close(code=1008)

@router.websocket('/ws')
async def websocket(ws: WebSocket):
    workspace = query_value(ws.scope['query_string'], 'workspace_id')
    slug = query_value(ws.scope['query_string'], 'workspace_slug')
    if not workspace and not slug:
        return await deny(ws, 400, 'workspace_id or workspace_slug required')
    def resolve():
        if workspace:
            return workspace
        with ws.app.state.database.transaction() as session:
            value = session.execute(select(workspaces.c.id).where(workspaces.c.slug == slug)).scalar()
            if value is None:
                raise HTTPException(404, 'workspace not found')
            return value
    try:
        workspace = await run_in_threadpool(resolve)
    except HTTPException as exc:
        return await deny(ws, exc.status_code, exc.detail)
    except Exception:
        return await deny(ws, 404, 'workspace not found')
    token = first_cookie(ws.headers.getlist('cookie'), 'workpal_auth')
    user_id = None
    def authenticate():
        return authenticate_token(ws.app.state.settings, ws.app.state.database, token)[0].user_id

    def check():
        try:
            with ws.app.state.database.transaction() as session:
                present = session.execute(select(members.c.id).where(
                    members.c.workspace_id == workspace, members.c.user_id == user_id)).first()
        except Exception as exc:
            raise HTTPException(503, 'membership lookup failed') from exc
        if not present:
            raise HTTPException(403, 'not a member of this workspace')
    async def authorize_membership():
        try:
            await authorize(check, timeout=2)
        except TimeoutError as exc:
            raise HTTPException(503, 'membership lookup failed') from exc
    def scope_authorizer(user,workspace,scope,identity):
        with ws.app.state.database.transaction() as session:
            return ScopeAuthorizer(ProjectQueries(session))(user,workspace,scope,identity)
    accepted = False
    writing_ack = False
    connection = None
    receiver = None
    closing = None
    try:
        if token:
            user_id = await authorize(authenticate)
            await authorize_membership()
        if not origin_allowed(ws):
            return await deny_origin(ws)
        if not token:
            await ws.accept()
            accepted = True
            def too_large():
                ws.app.state.realtime.metrics.inbound_too_large_total += 1
            token, error, closed = await read_first_auth(ws, too_large)
            if closed:
                return
            if error:
                raise HTTPException(401, error)
            user_id = await authorize(authenticate)
            await authorize_membership()
        if not accepted:
            await ws.accept()
        else:
            writing_ack = True
            await ws.send_text('{"type":"auth_ack"}')
            writing_ack = False
        connection = Connection(ws, check, workspace, user_id)
        ws.app.state.realtime.register(connection)
        await connection.start_session()
        receiver = asyncio.create_task(ws.receive())
        closing = asyncio.create_task(connection.wait_closed())
        while not connection.closed:
            done, _ = await asyncio.wait({receiver, closing}, return_when=asyncio.FIRST_COMPLETED)
            if closing in done:
                break
            message = receiver.result()
            if message['type'] == 'websocket.disconnect':
                if message.get('workpal.too_large'):
                    ws.app.state.realtime.metrics.inbound_too_large_total += 1
                break
            raw = message.get('text') or message.get('bytes') or b''
            result = await run_in_threadpool(parse_frame, raw, workspace, user_id, authorizer=scope_authorizer)
            if result.close_code:
                if result.close_code == 1009:
                    ws.app.state.realtime.metrics.inbound_too_large_total += 1
                await ws.close(code=result.close_code)
                break
            if result.action:
                kind, scope, room = result.action
                if kind == 'subscribe': ws.app.state.realtime.subscribe(connection, scope, room)
                else: ws.app.state.realtime.unsubscribe(connection, scope, room)
            if result.reply:
                if result.reply['type'] == 'subscribe_error' and result.reply['payload']['error'] != 'invalid payload':
                    ws.app.state.realtime.metrics.add_scope('subscribe_denied_total', result.reply['payload']['scope'], 1)
                connection.enqueue(result.reply)
            receiver = asyncio.create_task(ws.receive())
    except Exception as exc:
        if connection is None:
            if accepted:
                try:
                    if writing_ack:
                        await abort_socket(ws)
                    else:
                        await send_auth_error(ws, getattr(exc, 'detail', 'Authentication failed'))
                except (RuntimeError, OSError, asyncio.TimeoutError):
                    pass
            else:
                await deny(ws, getattr(exc, 'status_code', 503), getattr(exc, 'detail', 'Lookup failed'))
    finally:
        # Unregister synchronously: cancellation must never retain an audience.
        if connection:
            ws.app.state.realtime.unregister(connection)
        with anyio.CancelScope(shield=True):
            pending = [task for task in (receiver, closing) if task is not None]
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if connection:
                await connection.close()
