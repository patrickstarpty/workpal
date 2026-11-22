"""Realtime counter state, shared by a Hub and its relay on one event loop."""
from dataclasses import dataclass, field
from threading import RLock
from .relay_metrics import RedisMetrics


@dataclass
class FanoutMetrics:
    messages_sent: int = 0
    messages_dropped: int = 0
    slow_evictions: int = 0


@dataclass
class RealtimeMetrics:
    connects_total: int = 0
    disconnects_total: int = 0
    active_connections: int = 0
    membership_removals_dropped_total: int = 0
    inbound_too_large_total: int = 0
    fanout: FanoutMetrics = field(default_factory=FanoutMetrics)
    redis: RedisMetrics = field(default_factory=RedisMetrics)
    _counters: dict = field(default_factory=lambda: {name: {} for name in (
        'events_sent_by_type', 'subscribes_total', 'unsubscribes_total',
        'subscribe_denied_total', 'active_scope_rooms')}, repr=False)
    _lock: object = field(default_factory=RLock, repr=False)

    def add_scope(self, counter, scope, delta):
        with self._lock:
            values = self._counters[counter]
            values[scope] = values.get(scope, 0) + delta

    def record_event(self, event_type):
        if event_type:
            self.add_scope('events_sent_by_type', event_type, 1)

    def snapshot(self):
        with self._lock:
            return {
                'connects_total': self.connects_total,
                'disconnects_total': self.disconnects_total,
                'active_connections': self.active_connections,
                'slow_evictions_total': self.fanout.slow_evictions,
                'messages_sent_total': self.fanout.messages_sent,
                'messages_dropped_total': self.fanout.messages_dropped,
                'membership_removals_dropped_total': self.membership_removals_dropped_total,
                'inbound_too_large_total': self.inbound_too_large_total,
                **{name: dict(values) for name, values in self._counters.items()},
                'redis': self.redis.snapshot(),
            }

    def reset(self):
        with self._lock:
            self.connects_total = self.disconnects_total = self.active_connections = 0
            self.membership_removals_dropped_total = self.inbound_too_large_total = 0
            self.fanout.messages_sent = self.fanout.messages_dropped = self.fanout.slow_evictions = 0
            for values in self._counters.values():
                values.clear()
            self.redis.reset()
