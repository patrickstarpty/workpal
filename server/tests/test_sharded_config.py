import pytest


def test_sharded_defaults_and_small_replay_retention_relationships():
    from workpal_backend.realtime.sharded_config import ShardedConfig
    c=ShardedConfig().with_defaults()
    assert (c.shards,c.read_count,c.read_block_ns,c.replay_ns,c.trim_ns,c.ttl_ns)==(8,128,5_000_000_000,300_000_000_000,600_000_000_000,900_000_000_000)
    c.validate()
    c=ShardedConfig(replay_ns=3,trim_ns=3,ttl_ns=2).with_defaults()
    assert (c.trim_ns,c.ttl_ns,c.refresh_ns,c.maintenance_ns)==(6,9,3,3)
    assert c.retention_config().enabled is False
    c.validate()


def test_validation_uses_go_duration_text_and_signed_overflow():
    from workpal_backend.realtime.sharded_config import ShardedConfig,duration_text
    assert duration_text(3_723_000_000_004)=='1h2m3.000000004s'
    assert duration_text(-1500)=='-1.5µs'
    assert duration_text(-(1<<63))=='-2562047h47m16.854775808s'
    with pytest.raises(ValueError,match='ReplayGrace must be positive'):
        ShardedConfig().validate()
    with pytest.raises(ValueError,match=r'TrimHorizon \(3ns\) must be greater than ReplayGrace \(3ns\)'):
        ShardedConfig(replay_ns=3,trim_ns=3).validate()
    c=ShardedConfig(replay_ns=1<<62).with_defaults()
    assert c.trim_ns==-(1<<63) and c.ttl_ns==0


def test_shard_hash_uses_scope_separator_and_preserves_invalid_utf8_bytes():
    from workpal_backend.realtime.sharded_config import shard_for,sharded_stream_key
    assert shard_for('ab','c',(1<<32)-1)!=shard_for('a','bc',(1<<32)-1)
    assert 0<=shard_for('workspace','中文',8)<8
    assert shard_for('scope','\udcff',8)==shard_for('scope','\udcff',8)
    assert sharded_stream_key(3)=='ws:relay:shard:3'
