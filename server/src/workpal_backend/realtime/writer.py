"""Bounded socket writer: freeze each batch before asking for authorization."""
import asyncio


class QueuedWriter:
    def __init__(self, authorize, write, on_failure, *, lock=None, on_drained=None):
        self.authorize = authorize
        self.write = write
        self.on_failure = on_failure
        self.on_drained = on_drained
        self.lock = lock if lock is not None else asyncio.Lock()
        self._queue = asyncio.Queue(maxsize=256)
        self._task = None
        self._stopped = False
        self._finishing = False
        self._wake = asyncio.Event()

    def try_send(self, frame):
        if self._stopped or self._finishing:
            return False
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            return False
        self._wake.set()
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        return True

    def finish(self):
        if self._stopped:
            return
        self._finishing = True
        self._wake.set()
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def _discard(self):
        while not self._queue.empty():
            self._queue.get_nowait()
            self._queue.task_done()

    async def flush(self):
        await self._queue.join()
        if (self._stopped or self._finishing) and self._task is not None and self._task is not asyncio.current_task():
            await asyncio.gather(self._task, return_exceptions=True)

    async def stop(self):
        self._stopped = True
        self._discard()
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self):
        try:
            while not self._stopped:
                while self._queue.empty():
                    if self._finishing:
                        if self.on_drained is not None:
                            await self.on_drained()
                        return
                    await self._wake.wait()
                    self._wake.clear()
                batch = [self._queue.get_nowait()]
                while len(batch) < 32 and not self._queue.empty():
                    batch.append(self._queue.get_nowait())
                try:
                    # No frame arriving after this snapshot can share its lookup.
                    await self.authorize()
                    async with self.lock:
                        async with asyncio.timeout(10):
                            for frame in batch:
                                if self._stopped:
                                    return
                                await self.write(frame)
                finally:
                    for _ in batch:
                        self._queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._stopped = True
            await self.on_failure()
        finally:
            self._stopped = True
            self._discard()
