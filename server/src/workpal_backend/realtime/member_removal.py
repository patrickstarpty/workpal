"""Advisory member-removal invalidations with bounded asynchronous rechecks."""
import asyncio
from .frame_decode import _typed_layers, _fold
from ..auth.profile_decode import _Object, _replace_surrogates


def removal_candidate(raw):
    return any(prefix in raw for prefix in (b'member:', b'member\\', b'\\u006', b'\\u0072'))


def parse_removal(workspace, raw):
    if not removal_candidate(raw):
        return '', False
    try:
        frame = _typed_layers(_replace_surrogates(raw.decode('utf-8', errors='surrogateescape')))
    except (ValueError, UnicodeError):
        return '', False
    if not isinstance(frame, _Object):
        return '', False
    kind = ''; fields = {'USER_ID': '', 'WORKSPACE_ID': ''}; invalid = False
    for key, value in frame:
        field = _fold(key)
        if field == 'TYPE' and value is not None:
            if isinstance(value, str):kind = _replace_surrogates(value)
            else:invalid = True
        elif field == 'PAYLOAD' and value is not None:
            if not isinstance(value, _Object):
                invalid = True
                continue
            # A concrete struct merges duplicate objects; null preserves it.
            for name, item in value:
                name = _fold(name)
                if name in fields and item is not None:
                    if isinstance(item, str):fields[name] = _replace_surrogates(item)
                    else:invalid = True
    if invalid or kind != 'member:removed':
        return '', False
    if not fields['USER_ID'] or fields['WORKSPACE_ID'] != workspace:
        return '', True
    return fields['USER_ID'], True


class RemovalQueue:
    def __init__(self, snapshot, fanout_peers, stop_client, *, on_drop=None):
        self.snapshot = snapshot
        self.fanout_peers = fanout_peers
        self.stop_client = stop_client
        self.on_drop = on_drop
        self.pending = 0
        self.dropped = 0
        self._queue = asyncio.Queue(maxsize=64)
        self._workers = []
        self._closed = False

    def intercept(self, workspace, raw, event_id):
        user, removal = parse_removal(workspace, raw)
        if not removal:
            return False
        if not user or self._closed:
            return True
        clients, checker = self.snapshot(workspace, user)
        self.fanout_peers(workspace, raw, event_id, user)
        if not clients:
            return True
        if not self._workers:
            self._workers = [asyncio.create_task(self._run()) for _ in range(2)]
        try:
            self._queue.put_nowait((workspace, user, clients, checker, raw))
        except asyncio.QueueFull:
            self.dropped += 1
            if self.on_drop is not None:
                self.on_drop()
        else:
            self.pending += 1
        return True

    async def _run(self):
        while True:
            workspace, user, clients, checker, notice = await self._queue.get()
            try:
                try:
                    async with asyncio.timeout(2):
                        if checker is None:raise RuntimeError('membership checker unavailable')
                        member = await checker(workspace, user)
                except Exception:
                    member = False
                    notice = None
                if not member:
                    deadline = asyncio.get_running_loop().time()+.1
                    for client in clients:
                        await self.stop_client(client, notice, deadline)
            finally:
                self.pending -= 1
                self._queue.task_done()

    async def join(self):
        await self._queue.join()

    async def close(self):
        self._closed = True
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        while not self._queue.empty():
            self._queue.get_nowait()
            self._queue.task_done()
            self.pending -= 1
