import pytest


def test_relay_environment_defaults_and_dependent_duration_defaults():
    from workpal_backend.realtime.relay_config import relay_config_from_env
    mode, config = relay_config_from_env({})
    assert mode == 'sharded'
    assert config.shards == 8
    mode, config = relay_config_from_env({'REALTIME_RELAY_MODE':' \u2003DUAL ',
        'REALTIME_RELAY_SHARDS':'+3','REALTIME_RELAY_REPLAY_GRACE':'1.5s',
        'REALTIME_RELAY_STREAM_TTL_ENABLED':'TRUE'})
    assert mode == 'dual'
    assert (config.shards,config.replay_ns,config.trim_ns,config.ttl_ns) == (3,1_500_000_000,3_000_000_000,4_500_000_000)
    assert config.enabled
    assert config.refresh_ns == config.maintenance_ns == 1_500_000_000
    mode,config=relay_config_from_env({'REALTIME_RELAY_MODE':'unknown','REALTIME_RELAY_SHARDS':' 3',
        'REALTIME_RELAY_STREAM_TTL_ENABLED':'yes','REALTIME_RELAY_XREAD_BLOCK':'0'})
    assert mode=='sharded' and config.shards==8 and not config.enabled and config.read_block_ns==5_000_000_000
    with pytest.raises(ValueError,match='incompatible'):
        relay_config_from_env({'REALTIME_RELAY_MODE':'legacy'},cluster_mode=True)


def test_duration_parser_precision_units_and_range():
    from workpal_backend.realtime.relay_config import parse_duration
    assert parse_duration('1h2m3.000000004s') == 3_723_000_000_004
    assert parse_duration('+.5us') == 500
    assert parse_duration('1µs1μs') == 2000
    assert parse_duration('-9223372036854775808ns') == -(1<<63)
    assert parse_duration('0') == 0
    for invalid in ['1',' 1s','1s ','1e3s','.s','9223372036854775808ns','-9223372036854775809ns','１s']:
        with pytest.raises(ValueError): parse_duration(invalid)
