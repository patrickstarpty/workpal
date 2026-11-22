"""Fixed-shard stream naming, FNV routing and Go retention configuration."""
from dataclasses import dataclass, replace
from .stream_retention import RetentionConfig, SECOND, _subinterval


def signed_duration(value):
    return (value + (1 << 63)) % (1 << 64) - (1 << 63)


def duration_text(value):
    negative = value < 0
    value = abs(value)
    if value == 0:
        return '0s'
    if value < SECOND:
        unit, scale = ('ns', 1) if value < 1000 else ('µs', 1000) if value < 1_000_000 else ('ms', 1_000_000)
        whole, remainder = divmod(value, scale)
        fraction = ('.' + str(remainder).zfill(len(str(scale)) - 1).rstrip('0')) if remainder else ''
        result = str(whole) + fraction + unit
    else:
        hours, value = divmod(value, 3600 * SECOND)
        minutes, value = divmod(value, 60 * SECOND)
        seconds, nanos = divmod(value, SECOND)
        result = str(seconds) + ('.' + f'{nanos:09}'.rstrip('0') if nanos else '') + 's'
        if hours:
            result = f'{hours}h{minutes}m' + result
        elif minutes:
            result = f'{minutes}m' + result
    return ('-' if negative else '') + result


def sharded_stream_key(shard):
    return f'ws:relay:shard:{shard}'


def shard_for(scope, identity, shards):
    value = 2166136261
    data = scope.encode('utf-8', errors='surrogateescape') + b'\0' + identity.encode('utf-8', errors='surrogateescape')
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value % (shards & 0xffffffff)


@dataclass(frozen=True)
class ShardedConfig:
    shards: int = 0
    max_len: int = 0
    read_count: int = 0
    read_block_ns: int = 0
    replay_ns: int = 0
    trim_ns: int = 0
    ttl_ns: int = 0
    refresh_ns: int = 0
    maintenance_ns: int = 0
    enabled: bool = False

    def with_defaults(self):
        replay = self.replay_ns if self.replay_ns > 0 else 300 * SECOND
        trim = signed_duration(2 * replay) if self.trim_ns <= replay else self.trim_ns
        ttl = signed_duration(trim + replay) if self.ttl_ns < trim else self.ttl_ns
        return replace(self, shards=self.shards if self.shards > 0 else 8,
                       max_len=self.max_len if self.max_len > 0 else 2000,
                       read_count=self.read_count if self.read_count > 0 else 128,
                       read_block_ns=self.read_block_ns if self.read_block_ns > 0 else 5 * SECOND,
                       replay_ns=replay, trim_ns=trim, ttl_ns=ttl,
                       refresh_ns=self.refresh_ns if 0 < self.refresh_ns < ttl else _subinterval(ttl, 30 * SECOND),
                       maintenance_ns=self.maintenance_ns if 0 < self.maintenance_ns < ttl else _subinterval(ttl, 60 * SECOND))

    def retention_config(self):
        c = self.with_defaults()
        return RetentionConfig(max_len=c.max_len, trim_ns=c.trim_ns, ttl_ns=c.ttl_ns,
                               refresh_ns=c.refresh_ns, maintenance_ns=c.maintenance_ns, enabled=c.enabled)

    def validate(self):
        text = duration_text
        if self.replay_ns <= 0:
            raise ValueError('ReplayGrace must be positive')
        if self.trim_ns <= self.replay_ns:
            raise ValueError(f'TrimHorizon ({text(self.trim_ns)}) must be greater than ReplayGrace ({text(self.replay_ns)})')
        if self.ttl_ns < self.trim_ns:
            raise ValueError(f'StreamTTL ({text(self.ttl_ns)}) must be at least TrimHorizon ({text(self.trim_ns)})')
        if not 0 < self.refresh_ns < self.ttl_ns:
            raise ValueError(f'TTLRefreshInterval ({text(self.refresh_ns)}) must be positive and less than StreamTTL ({text(self.ttl_ns)})')
        if not 0 < self.maintenance_ns < self.ttl_ns:
            raise ValueError(f'MaintenanceInterval ({text(self.maintenance_ns)}) must be positive and less than StreamTTL ({text(self.ttl_ns)})')
