"""Environment parsing for the Go-compatible realtime relay modes."""
import logging
import os
import re
from dataclasses import replace

from ..auth.profile_decode import go_trim_space
from .sharded_config import ShardedConfig, signed_duration

log = logging.getLogger(__name__)
_UNITS = {'ns': 1, 'us': 1000, 'µs': 1000, 'μs': 1000, 'ms': 1_000_000,
          's': 1_000_000_000, 'm': 60_000_000_000, 'h': 3600_000_000_000}
_PART = re.compile(r'([0-9]*)(?:\.([0-9]*))?([^0-9.]+)')


def parse_duration(raw):
    """Parse signed nanoseconds, including Go's fractional float64 rounding.

    Callers use fallback values on invalid input; error wording is not exposed
    as Go ParseDuration's public error interface.
    """
    negative = raw.startswith('-')
    source = raw[1:] if raw.startswith(('-', '+')) else raw
    if source == '0':
        return 0
    total = position = 0
    if not source:
        raise ValueError('invalid duration')
    while position < len(source):
        part = _PART.match(source, position)
        if part is None:
            raise ValueError('invalid duration')
        integer, fraction, unit_name = part.groups()
        if not integer and not fraction:
            raise ValueError('invalid duration')
        unit = _UNITS.get(unit_name)
        if unit is None:
            raise ValueError('invalid duration unit')
        value = 0
        for digit in integer:
            value = value * 10 + ord(digit) - 48
            if value > 1 << 63:
                raise ValueError('duration overflow')
        value *= unit
        if value > 1 << 63:
            raise ValueError('duration overflow')
        digits, scale = 0, 1.0
        for digit in fraction or '':
            if digits > ((1 << 63) - 1) // 10:
                break
            candidate = digits * 10 + ord(digit) - 48
            if candidate > 1 << 63:
                break
            digits = candidate
            scale *= 10
        value += int(float(digits) * (float(unit) / scale))
        total += value
        if total > 1 << 63:
            raise ValueError('duration overflow')
        position = part.end()
    if not negative and total >= 1 << 63:
        raise ValueError('duration overflow')
    return -total if negative else total


def relay_config_from_env(environment=None, *, cluster_mode=False):
    env = os.environ if environment is None else environment
    mode = go_trim_space(env.get('REALTIME_RELAY_MODE', '')).lower() or 'sharded'
    if mode not in ('sharded', 'dual', 'legacy'):
        log.warning('invalid REALTIME_RELAY_MODE; using sharded')
        mode = 'sharded'
    if cluster_mode and mode != 'sharded':
        raise ValueError(f'REALTIME_RELAY_MODE={mode} is incompatible with REDIS_CLUSTER_MODE=true; use sharded mode')

    def read(name, default, parse):
        raw = env.get('REALTIME_RELAY_' + name, '')
        if raw == '':
            return default
        try:
            return parse(raw)
        except (ValueError, OverflowError):
            log.warning('invalid REALTIME_RELAY_%s; using default', name)
            return default

    def positive_integer(raw):
        if not re.fullmatch(r'[+-]?[0-9]+', raw):
            raise ValueError('invalid integer')
        value = int(raw)
        if not 0 < value < 1 << 63:
            raise ValueError('invalid positive integer')
        return value

    def positive_duration(raw):
        value = parse_duration(raw)
        if value <= 0:
            raise ValueError('invalid positive duration')
        return value

    def boolean(raw):
        if raw in ('1', 't', 'T', 'TRUE', 'true', 'True'):
            return True
        if raw in ('0', 'f', 'F', 'FALSE', 'false', 'False'):
            return False
        raise ValueError('invalid boolean')

    config = ShardedConfig().with_defaults()
    replay = read('REPLAY_GRACE', config.replay_ns, positive_duration)
    trim = read('TRIM_HORIZON', signed_duration(2 * replay), positive_duration)
    ttl = read('STREAM_TTL', signed_duration(trim + replay), positive_duration)
    config = replace(config,
        shards=read('SHARDS', config.shards, positive_integer),
        max_len=read('STREAM_MAXLEN', config.max_len, positive_integer),
        read_count=read('XREAD_COUNT', config.read_count, positive_integer),
        read_block_ns=read('XREAD_BLOCK', config.read_block_ns, positive_duration),
        replay_ns=replay, trim_ns=trim, ttl_ns=ttl,
        refresh_ns=read('TTL_REFRESH_INTERVAL', config.refresh_ns, positive_duration),
        maintenance_ns=read('MAINTENANCE_INTERVAL', config.maintenance_ns, positive_duration),
        enabled=read('STREAM_TTL_ENABLED', False, boolean))
    try:
        config.validate()
    except ValueError:
        log.warning('invalid realtime relay retention config; normalizing values')
    return mode, config.with_defaults()
