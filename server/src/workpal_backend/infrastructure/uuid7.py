"""UUIDv7 layout and monotonic clock from github.com/google/uuid v1.6.0.

Adapted under the BSD license in GOOGLE_UUID_LICENSE.txt. Entropy is obtained
before the time lock, matching NewV7/NewRandom's ordering.
"""
import secrets
import threading
import time
from uuid import UUID


def _int64(value):
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


class UUID7Generator:
    def __init__(self, *, clock_ns=time.time_ns, random_bytes=secrets.token_bytes):
        self._clock = clock_ns
        self._random = random_bytes
        self._lock = threading.Lock()
        self._last = 0

    def __call__(self):
        data = bytearray(self._random(16))
        if len(data) != 16:
            raise OSError('short UUID entropy read')
        data[8] = (data[8] & 0x3f) | 0x80
        with self._lock:
            nano = _int64(self._clock())
            milli = abs(nano) // 1_000_000 * (-1 if nano < 0 else 1)
            sequence = (nano - milli * 1_000_000) >> 8
            now = _int64((milli << 12) + sequence)
            if now <= self._last:
                now = _int64(self._last + 1)
                milli, sequence = now >> 12, now & 0xfff
            self._last = now
        data[:6] = (milli & ((1 << 48) - 1)).to_bytes(6, 'big')
        data[6] = 0x70 | ((sequence >> 8) & 0xf)
        data[7] = sequence & 0xff
        return str(UUID(bytes=bytes(data)))


uuid7 = UUID7Generator()
