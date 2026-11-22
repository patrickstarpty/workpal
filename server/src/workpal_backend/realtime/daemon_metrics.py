"""Daemon WebSocket operational counters; producers share this state."""
from dataclasses import asdict, dataclass, fields


@dataclass
class DaemonMetrics:
    connects_total: int = 0
    disconnects_total: int = 0
    active_connections: int = 0
    slow_evictions_total: int = 0
    wakeup_published_total: int = 0
    wakeup_publish_errors: int = 0
    wakeup_received_total: int = 0
    wakeup_delivered_hit_total: int = 0
    wakeup_delivered_miss_total: int = 0
    runtime_gone_delivered_hit_total: int = 0
    runtime_gone_delivered_miss_total: int = 0
    runtime_gone_published_total: int = 0
    runtime_gone_publish_errors: int = 0
    runtime_gone_received_total: int = 0

    def snapshot(self):
        return asdict(self)

    def reset(self):
        for f in fields(self):
            setattr(self, f.name, 0)
