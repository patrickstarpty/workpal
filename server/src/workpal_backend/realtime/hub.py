"""Bounded local fanout seam; deliberately has no internal stream consumer."""
import asyncio
from threading import RLock
import anyio
from starlette.websockets import WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

async def authorize(check, timeout=None):
    with anyio.fail_after(timeout):
        return await anyio.to_thread.run_sync(check, abandon_on_cancel=True)
from .protocol import project_event, resolve_audience
from .dedup import SeenEvents
from .writer import QueuedWriter
from .membership_batch import MembershipBatcher
from .member_removal import RemovalQueue
from ..infrastructure.go_response import marshal_map_json

from .metrics import RealtimeMetrics


class Hub:
    def __init__(self, *, membership_lookup=None, membership_check=None, metrics=None):
        self.membership_batcher = MembershipBatcher(membership_lookup) if membership_lookup is not None else None
        self.connections = set()
        self._draining = set()
        self.membership_check = membership_check
        self.metrics = metrics if metrics is not None else RealtimeMetrics()
        self.fanout_metrics = self.metrics.fanout
        self.removals = RemovalQueue(self._removal_snapshot, self._removal_peers, self._stop_removed,
                                     on_drop=self._removal_dropped)
        self._rooms_lock = RLock()
        self._on_first = self._on_last = None

    def set_subscription_callbacks(self, on_first, on_last):
        with self._rooms_lock:
            self._on_first, self._on_last = on_first, on_last

    def local_scopes(self):
        with self._rooms_lock:
            return {room for connection in self.connections for room in connection.rooms}

    def has_local_subscribers(self, scope, identity):
        with self._rooms_lock:
            return any((scope, identity) in c.rooms for c in self.connections)

    def register(self, connection):
        with self._rooms_lock:
            if connection.closed:
                return
            if connection not in self.connections:
                connection.rooms.clear()
            connection._hub = self
            self.connections.add(connection)
        self.metrics.connects_total += 1
        self.metrics.active_connections += 1
        self.subscribe(connection, 'workspace', connection.workspace_id)
        self.subscribe(connection, 'user', connection.user_id)
        if connection.workspace_id and connection.user_id:
            self.subscribe(connection, 'workspace_member', connection.workspace_id+':'+connection.user_id)

    def subscribe(self, connection, scope, identity):
        if not scope or not identity:
            return False
        room = (scope, identity)
        with self._rooms_lock:
            if connection not in self.connections or room in connection.rooms:
                return False
            first = not self.has_local_subscribers(scope, identity)
            connection.rooms.add(room)
            callback = self._on_first
        self.metrics.add_scope('subscribes_total', scope, 1)
        if first:
            self.metrics.add_scope('active_scope_rooms', scope, 1)
            if callback is not None:
                callback(scope, identity)
        return True

    def unsubscribe(self, connection, scope, identity):
        if not scope or not identity:
            return False
        room = (scope, identity)
        with self._rooms_lock:
            if connection not in self.connections or room not in connection.rooms:
                return False
            connection.rooms.remove(room)
            last = not self.has_local_subscribers(scope, identity)
            callback = self._on_last
        self.metrics.add_scope('unsubscribes_total', scope, 1)
        if last:
            self.metrics.add_scope('active_scope_rooms', scope, -1)
            if callback is not None:
                callback(scope, identity)
        return True

    def unregister(self, connection):
        with self._rooms_lock:
            if connection not in self.connections:
                return
            self.connections.remove(connection)
            emptied = [room for room in connection.rooms if not self.has_local_subscribers(*room)]
            connection.rooms.clear()
            callback = self._on_last
        self.metrics.disconnects_total += 1
        self.metrics.active_connections -= 1
        if callback is not None:
            for room in emptied:
                callback(*room)

        for scope, _ in emptied:
            self.metrics.add_scope('active_scope_rooms', scope, -1)

    def _removal_dropped(self):
        self.metrics.membership_removals_dropped_total += 1

    def _removal_snapshot(self, workspace, user):
        with self._rooms_lock:
            clients = tuple(c for c in self.connections if c.workspace_id == workspace and c.user_id == user)
            return clients, self.membership_check

    def _removal_peers(self, workspace, raw, event_id, user):
        self._fanout_scope('workspace', workspace, raw, event_id, user)

    async def _stop_removed(self, client, notice, deadline):
        await client.stop_with_notice(notice, deadline)

    def _fanout(self, raw, event_id, receives):
        slow = []
        with self._rooms_lock:
            for connection in self.connections:
                if not receives(connection) or not connection.mark_seen(event_id):
                    continue
                if connection.try_send(raw):
                    self.fanout_metrics.messages_sent += 1
                else:
                    slow.append(connection)
        if slow:
            self._evict_slow(slow)

    def _evict_slow(self, clients):
        self.fanout_metrics.messages_dropped += len(clients)
        self.fanout_metrics.slow_evictions += len(clients)
        emptied = []
        evicted = 0
        with self._rooms_lock:
            for connection in clients:
                if connection not in self.connections:
                    continue
                self.connections.remove(connection)
                evicted += 1
                emptied.extend(room for room in connection.rooms if not self.has_local_subscribers(*room))
                connection.rooms.clear()
                self._draining.add(connection)
                connection.finish()
            callback = self._on_last
        self.metrics.active_connections -= evicted
        self.metrics.disconnects_total += evicted
        for scope, _ in emptied:
            self.metrics.add_scope('active_scope_rooms', scope, -1)
        if callback is not None:
            for room in emptied:
                callback(*room)

    def _fanout_scope(self, scope, identity, raw, event_id, exclude_user=''):
        self._fanout(raw, event_id, lambda c: (scope, identity) in c.rooms and
                     (not exclude_user or c.user_id != exclude_user))

    def broadcast_to_scope(self, scope, identity, raw, event_id=''):
        if not scope or not identity:
            return
        if scope == 'workspace' and self.removals.intercept(identity, raw, event_id):
            return
        self._fanout_scope(scope, identity, raw, event_id)

    def broadcast_all(self, raw, exclude_workspace='', event_id=''):
        self._fanout(raw, event_id, lambda c: not exclude_workspace or c.workspace_id != exclude_workspace)

    def send_to_user(self, user, raw, exclude_workspace='', event_id=''):
        self._fanout(raw, event_id, lambda c: ('user', user) in c.rooms and
                     (not exclude_workspace or c.workspace_id != exclude_workspace))

    async def publish(self, event, *, event_id=""):
        """Explicit relay ID enables per-connection dedup; empty disables it."""
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

        await asyncio.gather(*(c.send(frame) for c in tuple(self.connections) if receives(c) and c.mark_seen(event_id)))

    async def close(self):
        await self.removals.close()
        await asyncio.gather(*(c.close() for c in tuple(self.connections | self._draining)))
        if self.membership_batcher is not None:
            await self.membership_batcher.close()

class Connection:
    def __init__(self, ws, check, workspace, user):
        self.ws, self.check = ws, check
        self._workspace_id = workspace
        self.user_id = user
        self._hub = None
        self.rooms = {room for room in [('workspace', workspace), ('user', user)] if room[1]}
        if workspace and user:
            self.rooms.add(('workspace_member', workspace+':'+user))
        self.lock = asyncio.Lock()
        self.closed = False
        self._closing_task = None
        self._close_complete = asyncio.Event()
        self._seen = SeenEvents()
        self._writer = QueuedWriter(self._authorize_write, self._write_raw, self.close, lock=self.lock, on_drained=self._finish_transport)

    def mark_seen(self,event_id):
        return self._seen.mark(event_id)

    @property
    def workspace_id(self):
        return self._workspace_id

    def finish(self):
        self._writer.finish()

    async def _finish_transport(self):
        # wsproto's enum sentinel emits a close frame with no status payload,
        # matching Go WriteMessage(CloseMessage, []byte{}).
        from wsproto.frame_protocol import CloseReason
        await self.close(code=CloseReason.NO_STATUS_RCVD)

    async def _begin_close(self):
        current = asyncio.current_task()
        if self.closed:
            # An external closer can be waiting for this writer to stop.
            # Never make the writer wait back on that closer.
            if self._closing_task is not None and current not in (self._closing_task, self._writer._task):
                await self._close_complete.wait()
            return False
        self.closed = True
        self._closing_task = current
        if self._hub is not None:
            self._hub.unregister(self)
            self._hub._draining.add(self)
        return True

    async def start_session(self):
        if 'workpal.websocket.session' in getattr(self.ws, 'scope', {}).get('extensions', {}):
            await self.ws.send({'type': 'websocket.send', 'workpal.session': self.lock})

    async def wait_closed(self):
        await self._close_complete.wait()

    async def _complete_close(self, code):
        try:
            await self._close_transport(code)
        finally:
            if self._hub is not None:
                self._hub._draining.discard(self)
            self._close_complete.set()

    async def close(self, *, code=None):
        if not await self._begin_close():
            return
        try:
            await self._writer.stop()
        finally:
            await self._complete_close(code)

    async def stop_with_notice(self, notice, deadline):
        busy = self.lock.locked()
        if not await self._begin_close():
            return
        try:
            await self._writer.stop()
            if notice and not busy and not self.lock.locked() and asyncio.get_running_loop().time() < deadline:
                try:
                    async with self.lock:
                        async with asyncio.timeout_at(deadline):
                            await self._write_raw(notice)
                except Exception:
                    pass
        finally:
            await self._complete_close(None)

    async def _close_transport(self, code):
        try:
            if code is None and 'workpal.websocket.abort' in getattr(self.ws, 'scope', {}).get('extensions', {}):
                await self.ws.send({'type': 'websocket.close', 'workpal.abort': True})
            else:
                # Generic ASGI/TestClient cannot express a TCP-only close.
                # Preserve their policy-close fallback; canonical CLI uses
                # the advertised transport extension above.
                await asyncio.wait_for(self.ws.close(code=1008 if code is None else code), 1)
        except (WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError, anyio.ClosedResourceError, anyio.BrokenResourceError):
            pass

    async def _authorize_write(self):
        if self._hub is not None and self._hub.membership_batcher is not None:
            if not await self._hub.membership_batcher.authorize((self.workspace_id, self.user_id)):
                raise PermissionError('workspace membership unavailable')
            return
        with anyio.fail_after(2):
            await anyio.to_thread.run_sync(self.check, abandon_on_cancel=True)

    async def _write_raw(self, frame):
        if 'workpal.websocket.raw_text' in getattr(self.ws, 'scope', {}).get('extensions', {}):
            await self.ws.send({'type': 'websocket.send', 'bytes': frame, 'workpal.text': True})
        else:
            await self.ws.send_text(frame.decode('utf-8'))

    def try_send(self, frame):
        return not self.closed and self._writer.try_send(frame)

    def enqueue(self, frame):
        try:
            raw = marshal_map_json(frame)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            return False
        return self.try_send(raw)

    async def send(self, frame):
        # The existing internal outbox bridge awaits delivery. WebSocket replies
        # and relay fanout enqueue without waiting for authorization or I/O.
        if self.enqueue(frame):
            await self._writer.flush()
