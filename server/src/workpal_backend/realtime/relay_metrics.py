"""Shared Redis relay counters and detached collection snapshots.

Counter writers run on the owning asyncio loop. Sample maps are protected for
collectors; one instance can be supplied to multiple relay modes on that loop.
"""
from dataclasses import dataclass, field, fields
from threading import RLock


@dataclass
class RedisMetrics:
    connected: bool = False
    node_id: str = ''
    xadd_total: int = 0
    xadd_errors: int = 0
    xread_total: int = 0
    xread_errors: int = 0
    ack_total: int = 0
    last_xadd_lag_micros: int = 0
    mirror_primary_errors: int = 0
    mirror_secondary_errors: int = 0
    mirror_divergence_total: int = 0
    trimmed: int = 0
    stream_missing_total: int = 0
    retention_errors: int = 0
    used_memory_bytes: int = 0
    max_memory_bytes: int = 0
    evicted_keys: int = 0
    last_error: str = ''
    _streams: dict = field(default_factory=dict, repr=False)
    _without_ttl: dict = field(default_factory=dict, repr=False)
    _lock: object = field(default_factory=RLock, repr=False)

    def observe_stream(self, stream, entries, pttl_millis):
        with self._lock:
            self._streams[stream] = {'entries': entries, 'pttl_millis': pttl_millis}

    def set_streams_without_ttl(self, relay, count):
        with self._lock:
            self._without_ttl[relay] = count

    @property
    def streams_without_ttl(self):
        with self._lock:
            return sum(self._without_ttl.values())

    @streams_without_ttl.setter
    def streams_without_ttl(self, count):
        # The legacy maintenance adapter writes its own mode's latest gauge.
        self.set_streams_without_ttl('legacy', count)

    def snapshot(self):
        with self._lock:
            result = {f.name: getattr(self, f.name) for f in fields(self) if not f.name.startswith('_')}
            result['stream_trimmed_total'] = result.pop('trimmed')
            result['streams_without_ttl'] = self.streams_without_ttl
            result['streams'] = {key: dict(value) for key, value in self._streams.items()}
            return result

    def reset(self):
        with self._lock:
            for f in fields(self):
                if not f.name.startswith('_') and f.name != 'node_id':
                    setattr(self, f.name, f.default)
            self._streams.clear()
            self._without_ttl.clear()
