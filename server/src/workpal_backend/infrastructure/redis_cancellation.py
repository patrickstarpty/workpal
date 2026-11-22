"""Preserve operation cancellation across redis-py's buffered write boundary.

Python 3.11 wait_for can return a just-completed write after swallowing its
caller's cancellation. A canceled Redis command must not then enter a blocking
read. Guard only that boundary, leaving dependency cleanup free to finish.
"""
import asyncio
from functools import lru_cache
from redis.asyncio import Redis as BaseRedis


class CancellationWriteGuard:
    async def send_packed_command(self, *args, **kwargs):
        task = asyncio.current_task()
        cancellations = task.cancelling() if task is not None else 0
        result = await super().send_packed_command(*args, **kwargs)
        if task is not None and task.cancelling() > cancellations:
            try:
                await self.disconnect(nowait=True)
            finally:
                raise asyncio.CancelledError()
        return result


@lru_cache(maxsize=None)
def _guarded_connection_class(connection_class):
    if issubclass(connection_class, CancellationWriteGuard):
        return connection_class
    return type('CancellationSafe' + connection_class.__name__,
                (CancellationWriteGuard, connection_class), {})


class Redis(BaseRedis):
    """Configure cancellation-safe connections before this client's first IO.

Create a fresh client/pool; an already-open externally supplied pool is not
retrofitted. URL factories retain redis-py's SSL/Unix connection selection.
"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_pool.connection_class = _guarded_connection_class(self.connection_pool.connection_class)
