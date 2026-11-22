import asyncio
import pytest


def test_sharded_publish_marks_presence_only_after_write_and_keeps_ttl_failure_nonfatal():
    from workpal_backend.realtime.sharded_publisher import ShardedPublisher
    from workpal_backend.realtime.sharded_config import ShardedConfig, shard_for, sharded_stream_key
    from workpal_backend.realtime.relay_metrics import RedisMetrics

    async def run():
        seen = [False] * 8
        calls = []
        class Client:
            fail = True
            async def xadd(self, key, values, **kwargs):
                calls.append((key, values, kwargs))
                if self.fail:
                    raise OSError('write failed')
            async def pexpire(self, key, milliseconds):
                assert seen[shard_for('user', 'u', 8)]
                raise OSError('expiry failed')
        client = Client()
        metrics = RedisMetrics()
        publisher = ShardedPublisher(client, 'node', config=ShardedConfig(enabled=True),
                                     metrics=metrics, seen=seen, clock_ns=lambda: 0)
        with pytest.raises(OSError, match='write failed'):
            await publisher.publish_with_id('user', 'u', 'workspace', b'opaque', 'event')
        assert not any(seen)
        client.fail = False
        await publisher.publish_with_id('user', 'u', 'workspace', b'opaque', 'event')
        assert sum(seen) == 1
        assert calls[-1][0] == sharded_stream_key(shard_for('user', 'u', 8))
        assert calls[-1][1]['payload_json'] == b'opaque'
        assert calls[-1][2] == {'maxlen': 2000, 'approximate': True}
        assert (metrics.xadd_total, metrics.xadd_errors, metrics.retention_errors) == (1, 1, 1)
        assert metrics.last_error == 'expiry failed'
    asyncio.run(run())
