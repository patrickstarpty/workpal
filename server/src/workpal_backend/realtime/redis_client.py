"""Redis read boundaries for the pinned Go relay client's default options.

Go ignores context cancellation/deadlines once socket IO is in progress and
uses BLOCK+10 seconds for XREAD/XREADGROUP. This adapter covers those reads;
connection acquisition, retries and non-read command budgets need separate
transport parity coverage before application activation.
"""
from functools import lru_cache
from workpal_backend.infrastructure.redis_cancellation import Redis


class RelayReadTimeout:
    async def send_command(self, *args, **kwargs):
        await super().send_command(*args, **kwargs)
        def keyword(value):
            return value.upper() if isinstance(value, bytes) else str(value).upper().encode()
        if args and keyword(args[0]) in (b'XREAD', b'XREADGROUP'):
            for index, arg in enumerate(args[1:], 1):
                if keyword(arg) == b'BLOCK':
                    block = int(args[index + 1])
                    self._relay_previous_timeout = self.socket_timeout
                    self.socket_timeout = block / 1000 + 10 if block else None
                    break

    async def read_response(self, *args, **kwargs):
        try:
            return await super().read_response(*args, **kwargs)
        finally:
            if hasattr(self, '_relay_previous_timeout'):
                self.socket_timeout = self._relay_previous_timeout
                del self._relay_previous_timeout


@lru_cache(maxsize=None)
def _connection_type(base):
    return type('Relay' + base.__name__, (RelayReadTimeout, base), {})


class RelayRedis(Redis):
    def __init__(self, *args, **kwargs):
        # Go's default socket read/write timeout is 3s for ordinary commands.
        kwargs.setdefault('socket_timeout', 3)
        super().__init__(*args, **kwargs)
        self.connection_pool.connection_class = _connection_type(self.connection_pool.connection_class)

    async def relay_read(self, method, stop, timeout, *args, **kwargs):
        from .relay_consumer import _Stopped
        if stop.is_set():
            raise _Stopped()
        if timeout <= 0:
            raise TimeoutError('context deadline exceeded')
        return await getattr(self, method)(*args, **kwargs)


async def read_with_context(client, method, stop, timeout, *args, **kwargs):
    from .relay_consumer import _operation
    read = getattr(client, 'relay_read', None)
    if read is not None:
        return await read(method, stop, timeout, *args, **kwargs)
    return await _operation(getattr(client, method)(*args, **kwargs), stop, timeout)
