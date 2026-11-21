"""Bounded local fanout seam; deliberately has no internal stream consumer."""
import asyncio
import anyio
from starlette.websockets import WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

async def authorize(check):
    with anyio.fail_after(1):
        return await anyio.to_thread.run_sync(check, abandon_on_cancel=True)
from .protocol import project_event, resolve_audience

class Hub:
    def __init__(self):
        self.connections = set()

    async def publish(self, event):
        frame = project_event(event, event.get('workspaceID'))
        audience = resolve_audience(event)
        def receives(connection):
            if isinstance(audience, frozenset):
                # Go personal fallback excludes the bound workspace, even after
                # that connection explicitly unsubscribes its workspace room.
                return any(room in connection.rooms and
                           (room[0] == 'workspace' or connection.workspace_id != event['workspaceID'])
                           for room in audience)
            return audience is not None and audience in connection.rooms

        await asyncio.gather(*(c.send(frame) for c in tuple(self.connections) if receives(c)))

    async def close(self):
        await asyncio.gather(*(c.close() for c in tuple(self.connections)))

class Connection:
    def __init__(self, ws, check, workspace, user):
        self.ws, self.check = ws, check
        self._workspace_id = workspace
        self.rooms = {('workspace', workspace), ('user', user)}
        self.lock = asyncio.Lock()
        self.closed = False

    @property
    def workspace_id(self):
        return self._workspace_id

    async def close(self):
        if not self.closed:
            self.closed = True
            try:
                await asyncio.wait_for(self.ws.close(code=1008), 1)
            except (WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError, anyio.ClosedResourceError, anyio.BrokenResourceError):
                pass

    async def send(self, frame):
        async with self.lock:
            if self.closed:
                return
            try:
                await authorize(self.check)
                await asyncio.wait_for(self.ws.send_json(frame), 1)
            except Exception:
                await self.close()
