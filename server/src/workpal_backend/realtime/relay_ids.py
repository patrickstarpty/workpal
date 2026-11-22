"""Process-shared ULIDs for relay node and event identifiers."""
import secrets
from threading import Lock
import time

_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
_MAX_ENTROPY = (1 << 80) - 1


def encode_ulid(milliseconds, entropy):
    if not 0 <= milliseconds < 1 << 48:
        raise ValueError('ulid: time too big')
    if not 0 <= entropy <= _MAX_ENTROPY:
        raise ValueError('ulid: entropy out of range')
    value = (milliseconds << 80) | entropy
    return ''.join(_ALPHABET[(value >> shift) & 31] for shift in range(125, -1, -5))


class ULIDGenerator:
    def __init__(self, *, clock_ms=lambda: time.time_ns() // 1_000_000,
                 entropy=lambda: secrets.randbits(80),
                 increment=lambda: 1 + secrets.randbelow((1 << 32) - 1)):
        self.clock_ms = clock_ms
        self.entropy = entropy
        self.increment = increment
        self._lock = Lock()
        self._milliseconds = None
        self._entropy = 0

    def make(self):
        # Match Go's clock sample before its entropy lock. A backwards clock
        # samples fresh entropy rather than pinning the timestamp to the past.
        milliseconds = self.clock_ms()
        if not 0 <= milliseconds < 1 << 48:
            raise ValueError('ulid: time too big')
        with self._lock:
            if self._entropy != 0 and self._milliseconds == milliseconds:
                value = self._entropy + self.increment()
                self._entropy = value & _MAX_ENTROPY
                if value > _MAX_ENTROPY:
                    raise OverflowError('ulid: monotonic entropy overflow')
            else:
                self._entropy = self.entropy()
                self._milliseconds = milliseconds
            return encode_ulid(milliseconds, self._entropy)


_default = ULIDGenerator()
make_ulid = _default.make
